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
from ink_check import check_ink, assert_capture,place_agent_pointer
from window_controls_check import check_window_controls
from import_check import check_imports


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
    request_record=folder/'agent-request.txt'
    agent.write_text('#!'+sys.executable+'\nimport pathlib,sys,json\nfor arg in sys.argv[1:]:\n if arg.startswith("@") and arg.endswith(".txt"): pathlib.Path('+repr(str(request_record))+').write_text(pathlib.Path(arg[1:]).read_text())\np=pathlib.Path('+repr(str(reply_file))+')\nanswer=p.read_text()\nprint(answer)\nif json.loads(answer).get("kind")=="inspect": p.write_text(json.dumps({"kind":"question","message":"I checked the imported source."}))\n')
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
        if name in ('create','import','join'): click(state,window,'project-menu')
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
        trigger=target(hs,'project-create-split'); arrow=target(hs,'create-arrow'); caption=target(hs,'create-caption')
        actions=target(hs,'create-actions'); first=target(hs,'create'); second=target(hs,'join')
        assert trigger[2:]==[80,32] and actions[2:]==[104,72],(trigger,actions)
        assert first[2:]==second[2:]==[104,24] and second[1]-first[1]==48,(first,second)
        assert target(hs,'import')[1]-first[1]==24
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
        click(hs,hw,'create-main'); until(lambda:hs().get('form')=='Make something together','Split button main action did not create directly')
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
        toolbar=target(hs,'build-tools'); assert toolbar[2:]==[128,48],toolbar
        toolbar_metrics={'frame':toolbar,'buttons':{},'icons':{}}
        for index,key in enumerate(('tool-draw','tool-comment','undo')):
            bounds=target(hs,key); icon=target(hs,key+'-icon')
            assert bounds[2:]==[32,32] and icon[2:]==[16,16],(key,bounds,icon)
            assert bounds[0]-toolbar[0]==8+index*40 and bounds[1]-toolbar[1]==8,(key,bounds,toolbar)
            assert icon[0]-bounds[0]==8 and icon[1]-bounds[1]==8,(key,icon,bounds)
            toolbar_metrics['buttons'][key]=bounds; toolbar_metrics['icons'][key]=icon
        driver.screenshot(hw,folder/'ui-toolbar-active.png')
        hover=toolbar_metrics['buttons']['tool-comment']; rect=driver.rect(hw)
        driver.ipc(f"seat seat0 cursor set {round(rect['x']+hover[0]+16)} {round(rect['y']+hover[1]+16)}")
        driver.seat_command('motion 0 0'); time.sleep(.2)
        driver.screenshot(hw,folder/'ui-toolbar-hover.png')
        with Image.open(folder/'ui-toolbar-hover.png') as toolbar_image:
            image=toolbar_image.convert('RGB'); draw=toolbar_metrics['buttons']['tool-draw']
            assert image.getpixel((round(hover[0]+4),round(hover[1]+16)))==(243,243,243),'Toolbar hover must use F3F3F3'
            assert image.getpixel((round(draw[0]+4),round(draw[1]+16)))==(19,142,213),'Selected tool must use blue'
        (folder/'figma-toolbar-metrics.json').write_text(json.dumps(toolbar_metrics,indent=2))
        click(hs,hw,'tool-comment'); until(lambda:hs()['commentPointer']['phase']=='following','Comment did not activate')
        driver.key('Escape'); until(lambda:hs()['commentPointer']['phase']=='idle','Escape did not cancel the pointer')
        click(hs,hw,'tool-comment'); click(hs,hw,'undo')
        until(lambda:hs()['commentPointer']['phase']=='idle','Undo did not cancel the draft pointer')
        click(hs,hw,'tool-draw')
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
        summary['checks'].append('cross-app-draw-and-temporary-connected-comment-at-six-zooms-with-placement-focus-send-sync-and-undo')
        capture_geometry=gs()['viewport']
        capture_size=gs()['targets']['canvas'][2:]
        proposal(changed)
        pointer_x,pointer_y,reference=place_agent_pointer(driver,gs,gw,click)
        message(gs,gw,'@centaur Change the application title to Family Planner.')
        until(lambda:(hs().get('child') or {}).get('title')=='Family Planner' and (gs().get('child') or {}).get('title')=='Family Planner','Agent change did not reach both native apps',timeout=20)
        assert len(hs()['projects'])==1 and len(gs()['projects'])==1,'App changes duplicated a project'
        assert not hs()['project'].get('proposal'),'Compatible request required author approval'
        until(lambda:gs()['commentPointer']['phase']=='idle','Agent comment arrow was not cleared after send')
        request=json.loads(request_record.read_text().split('PROJECT AND CONVERSATION:\n',1)[1].split('\n\nCURRENT ',1)[0])
        assert request['requestComment']==reference,'Agent did not receive the comment target'
        summary['checks'].append('guest-agent-request-native-validation-and-live-update-without-approval-or-duplicates')
        assert list((source.parent/'.centaur').glob('remote-*.png')), 'Guest canvas image did not reach the host'
        with Image.open(next((source.parent/'.centaur').glob('remote-*.png'))) as context:
            assert context.size==tuple(map(round,capture_size)),'Comment capture exceeded the canvas and included UI'
            assert_capture(context,capture_geometry)
            assert any(r>200 and g<170 and b<170 and r-g>60 for r,g,b in context.convert('RGB').crop((round(pointer_x)-4,round(pointer_y)-4,round(pointer_x)+4,round(pointer_y)+4)).getdata()),'Agent capture lost the placed arrowhead'
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
        summary['checks']+=check_imports(driver,folder,hs,hw,click,message,roots[0],original,reply_file,request_record)
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
