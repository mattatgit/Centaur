"""Disposable native GTK product flow, with real services and a fixture agent."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from PIL import Image
from check import until, read, target
from test_driver import Driver
from ink_check import check_ink, assert_capture
from window_controls_check import check_window_controls


class Bridge:
    def __init__(self,root,env):
        self.data={}
        self.process=subprocess.Popen([env['CENTAUR_GTK_BRIDGE'],'--data-dir',str(root)],env=env,
                                      stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        def receive():
            for line in self.process.stdout:
                value=json.loads(line)
                if value.get('type')=='snapshot': self.data=value
        self.reader=threading.Thread(target=receive,daemon=True); self.reader.start()
    def send(self,kind,**fields):
        self.process.stdin.write(json.dumps({'type':kind,**fields})+'\n'); self.process.stdin.flush()
    def close(self):
        self.process.stdin.close(); self.process.wait(timeout=3); self.process.stdout.close()


def main():
    folder=Path(sys.argv[1]).resolve(); folder.mkdir(parents=True,exist_ok=False)
    executable=Path(sys.argv[0]).resolve().parent/'centaur-gtk4'
    driver=Driver(); driver.ipc('output HEADLESS-1 mode 2560x1000'); processes=[]; roots=[]; control=None; child_pids=[]
    summary={'checks':[],'production_approved':False}
    reply_file=folder/'reply.json'
    agent=folder/'agent'
    agent.write_text('#!'+sys.executable+'\nimport pathlib\nprint(pathlib.Path('+repr(str(reply_file))+').read_text())\n')
    agent.chmod(0o700)
    env=dict(os.environ,CENTAUR_AGENT=str(agent),CENTAUR_AUTHOR='Matt')
    def launch(name):
        root=folder/(name+'-data'); report=folder/(name+'-report'); roots.append(root)
        process=subprocess.Popen([str(executable),'--data-dir',str(root),'--report-dir',str(report)],env=env)
        processes.append(process)
        state=lambda:read(report/'shell.json')
        until(lambda:state().get('targets',{}).get('project-menu'), 'GTK shell did not map')
        window=driver.find_window('org.centaur.Gtk4',state()['pid']); driver.resize(window,1200,860)
        until(lambda:state().get('windowSize')==[1200,860], 'GTK did not report its resized allocation')
        driver.ipc(f'[con_id={window}] move position {40 if name=="host" else 1280} px 60 px')
        return process,state,window
    def click(state,window,name):
        if name in ('create','join'): click(state,window,'project-menu')
        x,y,w,h=target(state,name)
        driver.click(window,round(x+w/2),round(y+h/2))
        time.sleep(.15)
    def message(state,window,text):
        click(state,window,'editor'); driver.type(text); driver.key('Return')
        until(lambda:any(m.get('text')==text for m in state()['project'].get('messages',[])), 'Chat submission failed')
    def proposal(bundle,conflict=None):
        reply_file.write_text(json.dumps({'kind':'proposal','message':'Update the native app','conflict':conflict,'gtk':bundle}))
    try:
        check_window_controls(driver,folder/'window-controls')
        summary['checks'].append('native-decorated-close-button-geometry-pointer-states-and-window-management')
        host,hs,hw=launch('host')
        def resize_host(width,height):
            driver.resize(hw,width,height)
            until(lambda:hs().get('windowSize')==[width,height],'UI audit resize did not settle')
            driver.ipc(f'[con_id={hw}] move position 0 px 0 px'); time.sleep(.3)
        resize_host(1440,944)
        driver.screenshot(hw,folder/'ui-projects-empty.png')
        click(hs,hw,'nav-systems'); driver.screenshot(hw,folder/'ui-design-systems.png')
        click(hs,hw,'nav-settings'); driver.screenshot(hw,folder/'ui-settings.png')
        click(hs,hw,'nav-projects')
        click(hs,hw,'project-menu'); driver.screenshot(hw,folder/'ui-create-dropdown.png',focus=False)
        trigger=target(hs,'project-menu'); arrow=target(hs,'create-arrow'); caption=target(hs,'create-caption')
        actions=target(hs,'create-actions'); first=target(hs,'create'); second=target(hs,'join')
        assert trigger[2:]==[80,32] and actions[2:]==[104,48],(trigger,actions)
        assert first[2:]==second[2:]==[104,24] and second[1]-first[1]==24,(first,second)
        assert caption[0]-trigger[0]==12 and arrow[0]-trigger[0]==51 and arrow[2:]==[24,24],(caption,arrow,trigger)
        assert actions[0]+104+8==trigger[0]+80 and actions[1]-trigger[1]==40,(actions,trigger)
        assert target(hs,'create-option-caption')[0]-first[0]==8
        rect=driver.rect(hw)
        driver.ipc(f"seat seat0 cursor set {round(rect['x']+first[0]+first[2]/2)} {round(rect['y']+first[1]+first[3]/2)}")
        driver.seat_command('motion 0 0'); time.sleep(.2)
        driver.screenshot(hw,folder/'ui-create-dropdown-hover.png',focus=False)
        with Image.open(folder/'ui-create-dropdown-hover.png') as source:
            pixels=source.convert('RGB'); x,y,w,h=map(round,first)
            assert pixels.getpixel((x+4,y+h//2))==(248,248,248),'Dropdown hover must use F8F8F8'
            assert pixels.getpixel((x,y))==(255,255,255),'Dropdown hover must have rounded corners'
        (folder/'figma-create-metrics.json').write_text(json.dumps({'trigger':trigger,'caption':caption,'arrow':arrow,'actions':actions,'create':first,'join':second},indent=2))
        driver.key('Escape')
        click(hs,hw,'create'); until(lambda:hs().get('form')=='Make something together','New project form did not open')
        dialog=until(lambda:hs()['targets'].get('dialog-card'),'Modal did not allocate inside Centaur')
        assert dialog[2]==464 and abs(dialog[0]+dialog[2]/2-720)<=1 and abs(dialog[1]+dialog[3]/2-472)<=1,'Project dialog is not centred in Centaur'
        driver.screenshot(hw,folder/'ui-new-project.png',focus=False)
        driver.key('ISO_Left_Tab','Tab')  # Wrap through the modal, not the page behind it.
        driver.type('Family test'); driver.key('Return')
        until(lambda:(hs().get('child') or {}).get('ready'),'GTK project did not launch')
        project=hs()['project']; project_id=project['id']
        source=roots[0]/'projects'/project_id/'App.gtk.json'
        original=json.loads(source.read_text()); changed=json.loads(source.read_text())
        changed['files']['app.ui']=changed['files']['app.ui'].replace('Family board','Family Planner')
        checkpoint=subprocess.check_output(['git','-C',str(source.parent),'rev-parse','HEAD'],text=True).strip()
        rect=driver.rect(hw)
        driver.ipc(f"seat seat0 cursor set {rect['x']+64} {rect['y']+200}")
        driver.seat_command('motion 0 0')
        until(lambda:hs()['targets'].get('invite',[0]*4)[2:]==hs()['targets'].get('deploy',[0]*4)[2:]==[88,32],
              'Invite and Deploy must share their size outside hover')
        driver.screenshot(hw,folder/'gtk4-workspace.png')
        until(lambda:hs().get('targets',{}).get('chat-panel',[0,0,0])[2]==432,'Reference chat width was not preserved')
        workspace=hs(); mode=workspace['targets']['mode-switch']
        assert mode[2:]==[240,48] and abs(mode[0]+mode[2]/2-720)<=1,'Mode switch is not centred at its reference size'
        assert not workspace['layout']['sidebarVisible'],'Workspace retained a sidebar absent from the Qt reference'
        assert workspace['targets']['composer'][3]==104,'Composer is not on the agreed grid'
        assert workspace['targets']['invite'][2:]==workspace['targets']['deploy'][2:]==[88,32],'Invite and Deploy must share their size'
        driver.screenshot(hw,folder/'ui-interact.png')
        click(hs,hw,'mode-Build'); driver.screenshot(hw,folder/'ui-build.png'); click(hs,hw,'mode-Interact')
        (folder/'ui-workspace-metrics.json').write_text(json.dumps(workspace,indent=2))
        with Image.open(folder/'gtk4-workspace.png') as image:
            assert sum(abs(r-250)<2 and abs(g-251)<2 and abs(b-247)<2 for r,g,b in image.convert('RGB').getdata())>5000, 'Native sample was not rendered inside the GTK workspace'
        summary['checks'].append('native-project-create-and-embedded-gtk-app')
        summary['checks'].append('qt-reference-workspace-layout-typography-assets-and-8px-controls')
        resize_host(1200,860); driver.ipc(f'[con_id={hw}] move position 40 px 60 px')
        original_pid=hs()['childPid']
        message(hs,hw,'Hello from Matt')
        until(lambda:hs()['layout']['bodyFont']=='Inter 14px','Chat body did not use the redline Inter style')
        assert hs()['targets']['chat-avatar'][2:]==[32,32]
        assert hs()['layout']['statusFont']=='Inter 14px'
        assert hs()['childPid']==original_pid,'Ordinary chat restarted the app'
        control=Bridge(roots[0],env)
        until(lambda:control.data.get('projects'),'Service bridge did not connect')
        control.send('open',projectId=project_id)
        until(lambda:control.data.get('project',{}).get('id')==project_id,'Could not open shared project')
        control.send('invite',address='127.0.0.1')
        code=until(lambda:control.data.get('invitation'),'LAN invitation failed')
        control.close(); control=None
        guest,gs,gw=launch('guest')
        click(gs,gw,'join'); until(lambda:gs().get('form')=='Join project','Join form did not open')
        driver.key('ctrl+a'); driver.type('Guest'); driver.key('Tab')
        until(lambda:gs().get('focus')=='GtkTextView','Tab did not enter the invitation field')
        driver.type(code); driver.key('Return')
        until(lambda:(gs().get('child') or {}).get('ready'),'Guest did not join and embed the GTK app')
        assert gs()['status']=='Guest connected'
        message(gs,gw,'Hello from Guest')
        until(lambda:any(m.get('text')=='Hello from Guest' and m.get('author')=='Guest' for m in hs()['project']['messages']),'Host did not receive attributed guest chat')
        rows=until(lambda:hs().get('chatRows') if len(hs().get('chatRows',[]))==2 else None,'Chat rows did not allocate')
        assert abs(rows[1]['name']['baselines'][0]-rows[0]['body']['baselines'][-1]-36)<.1,rows
        assert abs(rows[0]['body']['baselines'][0]-(rows[0]['avatar']['bounds'][1]+32))<.2,rows
        chat=hs()['targets']['chat-panel']; bar=hs()['targets']['chat-scrollbar']
        assert bar[2]==24 and bar[0]+24==chat[0]+chat[2],'Scrollbar gutter is not 24px at the chat edge'
        assert not hs()['chatScroll']['scrollable'],'Short chat should not show a full-height thumb'
        driver.screenshot(hw,folder/'ui-chat-redline.png')
        (folder/'ui-chat-redline.json').write_text(json.dumps({'rows':rows,'chat':chat,'scrollbar':bar},indent=2))
        summary['checks'].append('two-independent-profiles-invite-join-and-attributed-chat')
        click(hs,hw,'mode-Build')
        until(lambda:hs().get('mode')=='Build','Build mode did not switch')
        assert 'editor' in hs()['targets'],'Build mode hid chat'
        cx,cy,cw,ch=hs()['targets']['canvas']; view=hs()['viewport']
        driver.drag(hw,round(cx+view['app_x']+60*view['scale']),round(cy+view['app_y']+80*view['scale']),50,30,button=1)
        until(lambda:len(gs()['project'].get('annotations',[]))==1,'Drawing did not synchronise to guest')
        click(hs,hw,'undo')
        until(lambda:not gs()['project'].get('annotations'),'Undo did not synchronise')
        message(hs,hw,'We can still chat in Build')
        click(hs,hw,'mode-Interact')
        summary['checks'].append('build-mode-keeps-chat-visible-and-drawing-undo-synchronise')
        check_ink(driver,folder,hs,hw,gs,gw,click,resize_host,project_id)
        summary['checks'].append('cross-app-draw-and-arrow-at-six-zooms-host-guest-render-sync-undo-reopen-resize-and-pan')
        capture_geometry=gs()['viewport']
        proposal(changed)
        message(gs,gw,'@centaur Change the application title to Family Planner.')
        until(lambda:(hs().get('child') or {}).get('title')=='Family Planner' and (gs().get('child') or {}).get('title')=='Family Planner','Agent change did not reach both native apps',timeout=20)
        assert len(hs()['projects'])==1 and len(gs()['projects'])==1,'App changes duplicated a project'
        assert not hs()['project'].get('proposal'),'Compatible request required author approval'
        summary['checks'].append('guest-agent-request-native-validation-and-live-update-without-approval-or-duplicates')
        assert list((source.parent/'.centaur').glob('remote-*.png')), 'Guest canvas image did not reach the host'
        with Image.open(next((source.parent/'.centaur').glob('remote-*.png'))) as context:
            assert_capture(context,capture_geometry)
            # The centred sample leaves this corner clear. Zoom/restart controls
            # float here in Centaur but must not be sent as part of the app.
            corner=context.convert('RGB').crop((context.width-40,8,context.width-8,40))
            assert all(low==high==255 for low,high in corner.getextrema()),'Centaur canvas controls leaked into agent context'
        summary['checks'].append('canvas-image-attached-from-guest-includes-outside-ink-without-chat-or-controls')
        revision=hs()['project']['revision']
        def at_bottom():
            scroll=hs()['chatScroll']
            return abs(scroll['upper']-scroll['pageSize']-scroll['value'])<1
        until(at_bottom,'Chat did not follow the latest message after layout')
        driver.screenshot(hw,folder/'ui-chat-agent.png')
        avatar=target(hs,'chat-agent-avatar'); mark=target(hs,'chat-agent-mark')
        assert avatar[2:]==[32,32] and mark[2:]==[16,16],(avatar,mark)
        assert mark[0]-avatar[0]==8 and mark[1]-avatar[1]==8,(avatar,mark)
        (folder/'figma-avatar-metrics.json').write_text(json.dumps({'avatar':avatar,'markViewport':mark,'silhouette':[15,16]},indent=2))
        invalid=json.loads(json.dumps(changed)); invalid['files']['style.css']='window { made-up-property: broken; }'
        proposal(invalid)
        message(hs,hw,'@centaur Test a malformed change')
        until(lambda:any('did not pass its native check' in m.get('text','') for m in hs()['project']['messages']),'Invalid GTK app was not rejected',timeout=20)
        assert hs()['project']['revision']==revision and json.loads(source.read_text())==changed
        assert hs()['child']['title']=='Family Planner' and gs()['child']['title']=='Family Planner'
        summary['checks'].append('invalid-css-leaves-current-source-and-both-previews-intact')
        compromise=json.loads(json.dumps(changed)); compromise['files']['app.ui']=compromise['files']['app.ui'].replace('Family Planner','Together Planner')
        proposal(compromise,{'reason':'Matt and Guest have incompatible title requirements','authors':['Matt','Guest']})
        message(hs,hw,'@centaur Resolve our conflicting title requirements')
        until(lambda:hs()['project'].get('proposal',{}).get('conflict'),'Conflict was not offered for agreement')
        assert hs()['project']['revision']==revision
        click(hs,hw,'accept')
        until(lambda:'Matt' in hs()['project']['proposal'].get('accepted',[]),'Host agreement was not recorded')
        assert hs()['project']['revision']==revision
        click(gs,gw,'accept')
        until(lambda:(hs().get('child') or {}).get('title')=='Together Planner' and (gs().get('child') or {}).get('title')=='Together Planner','Agreed GTK change was not applied',timeout=20)
        summary['checks'].append('only-genuine-conflict-waits-for-both-affected-authors')
        reply_file.write_text(json.dumps({'kind':'restore','message':'Return to the starting app','conflict':None,'checkpoint':checkpoint}))
        message(gs,gw,'@centaur Restore the starting app')
        until(lambda:(hs().get('child') or {}).get('title')=='Family board' and (gs().get('child') or {}).get('title')=='Family board','Exact GTK history restoration failed',timeout=20)
        assert json.loads(source.read_text())==original
        summary['checks'].append('exact-history-restore-propagates-to-both-profiles')
        old_child=hs()['childPid']
        click(hs,hw,'nav-projects')
        until(lambda:hs().get('page')=='projects' and hs().get('childPid') is None,'Leaving workspace did not stop the preview')
        click(hs,hw,'open-'+project_id)
        until(lambda:(hs().get('child') or {}).get('ready') and hs().get('childPid')!=old_child,'Reopening the same project did not start its preview')
        summary['checks'].append('project-navigation-stops-preview-and-reopens-same-project')
        click(hs,hw,'nav-projects'); resize_host(1440,944)
        driver.screenshot(hw,folder/'ui-project-cards.png')
        card=hs()['targets']['open-'+project_id]
        assert card[3]==256 and hs()['layout']['tileColumns']==3,'Project grid did not retain reference card geometry'
        click(hs,hw,'menu-'+project_id); driver.screenshot(hw,folder/'ui-project-menu.png')
        click(hs,hw,'menu-rename-'+project_id); until(lambda:hs().get('form')=='Rename project','Rename did not open')
        driver.screenshot(hw,folder/'ui-rename.png',focus=False); driver.key('Escape')
        click(hs,hw,'menu-'+project_id); click(hs,hw,'menu-delete-'+project_id)
        until(lambda:hs().get('form')=='Delete project?','Delete confirmation did not open')
        driver.screenshot(hw,folder/'ui-delete-confirmation.png',focus=False); driver.key('Escape')
        assert len(hs()['projects'])==1,'Cancelling deletion removed a project'
        control=Bridge(roots[0],env)
        for number in range(2,6):
            control.send('create',name='Family idea '+str(number),description='An idea to make together.')
            until(lambda:len(hs()['projects'])==number,'Grid audit project did not appear')
        control.close(); control=None
        for width,count in [(560,1),(1080,2),(1440,3),(1744,4),(2048,5)]:
            resize_host(width,944)
            until(lambda:hs()['layout']['tileColumns']==count,'Project grid column breakpoint failed')
            assert hs()['layout']['sidebarWidth']==(72 if width<760 else 216)
            tiles=[value for key,value in hs()['targets'].items() if key.startswith('open-')]
            assert len({round(tile[0]) for tile in tiles})==count,'Native cards did not use the reported columns'
            assert all(tile[2]%8==0 and tile[3]==256 for tile in tiles),'Responsive tiles left the 8px component grid'
            driver.screenshot(hw,folder/('ui-projects-'+str(count)+'-columns.png'))
        click(hs,hw,'open-'+project_id); until(lambda:(hs().get('child') or {}).get('ready'),'UI audit did not reopen app')
        resize_host(1200,860); driver.ipc(f'[con_id={hw}] move position 40 px 60 px')
        summary['checks'].append('responsive-project-grid-original-menu-rename-and-cancelled-delete')
        driver.screenshot(hw,folder/'gtk4-host.png'); driver.screenshot(gw,folder/'gtk4-guest.png')
        child_pids=[hs()['childPid'],gs()['childPid']]
        summary['passed']=True
    finally:
        for name in ('host','guest'):
            try:
                window=hw if name=='host' else gw
                driver.screenshot(window,folder/('final-'+name+'.png'))
            except (UnboundLocalError,subprocess.SubprocessError,StopIteration): pass
        if control: control.close()
        for process in processes:
            if process.poll() is None: process.send_signal(signal.SIGTERM)
            process.wait(timeout=5)
            assert process.returncode==0,'GTK frontend did not close cleanly'
        for root in roots:
            subprocess.run([str(executable),'--stop-host','--data-dir',str(root)],env=env,check=True,timeout=10)
        import shutil
        for root in roots: shutil.rmtree(root,ignore_errors=True)
        for pid in child_pids:
            try: os.kill(pid,0)
            except ProcessLookupError: continue
            raise AssertionError('An embedded GTK app remains after closing')
        summary['checks'].append('clean-frontend-child-and-test-host-shutdown')
        (folder/'summary.json').write_text(json.dumps(summary,indent=2))
        print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__': main()
