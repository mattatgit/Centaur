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
from check import until, read
from test_driver import Driver


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
    driver=Driver(); processes=[]; roots=[]; control=None; child_pids=[]
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
        until(lambda:state().get('targets',{}).get('create'), 'GTK shell did not map')
        window=driver.find_window('org.centaur.Gtk4',state()['pid']); driver.resize(window,1200,860)
        return process,state,window
    def click(state,window,name):
        x,y,w,h=until(lambda:state().get('targets',{}).get(name),'Missing GTK control '+name)
        driver.click(window,round(x+w/2),round(y+h/2))
        time.sleep(.15)
    def message(state,window,text):
        click(state,window,'editor'); driver.type(text); driver.key('Return')
        until(lambda:any(m.get('text')==text for m in state()['project'].get('messages',[])), 'Chat submission failed')
    def proposal(bundle,conflict=None):
        reply_file.write_text(json.dumps({'kind':'proposal','message':'Update the native app','conflict':conflict,'gtk':bundle}))
    try:
        host,hs,hw=launch('host')
        click(hs,hw,'create'); driver.type('Family test'); driver.key('Return')
        until(lambda:(hs().get('child') or {}).get('ready'),'GTK project did not launch')
        project=hs()['project']; project_id=project['id']
        source=roots[0]/'projects'/project_id/'App.gtk.json'
        original=json.loads(source.read_text()); changed=json.loads(source.read_text())
        changed['files']['app.ui']=changed['files']['app.ui'].replace('Family board','Family Planner')
        checkpoint=subprocess.check_output(['git','-C',str(source.parent),'rev-parse','HEAD'],text=True).strip()
        driver.screenshot(hw,folder/'gtk4-workspace.png')
        with Image.open(folder/'gtk4-workspace.png') as image:
            assert sum(abs(r-250)<2 and abs(g-251)<2 and abs(b-247)<2 for r,g,b in image.convert('RGB').getdata())>5000, 'Native sample was not rendered inside the GTK workspace'
        summary['checks'].append('native-project-create-and-embedded-gtk-app')
        original_pid=hs()['childPid']
        message(hs,hw,'Hello from Matt')
        assert hs()['childPid']==original_pid,'Ordinary chat restarted the app'
        control=Bridge(roots[0],env)
        until(lambda:control.data.get('projects'),'Service bridge did not connect')
        control.send('open',projectId=project_id)
        until(lambda:control.data.get('project',{}).get('id')==project_id,'Could not open shared project')
        control.send('invite',address='127.0.0.1')
        code=until(lambda:control.data.get('invitation'),'LAN invitation failed')
        control.close(); control=None
        guest,gs,gw=launch('guest')
        click(gs,gw,'join'); driver.key('ctrl+a'); driver.type('Guest'); driver.key('Tab'); driver.type(code); driver.key('Return')
        until(lambda:(gs().get('child') or {}).get('ready'),'Guest did not join and embed the GTK app')
        assert gs()['status']=='Guest connected'
        message(gs,gw,'Hello from Guest')
        until(lambda:any(m.get('text')=='Hello from Guest' and m.get('author')=='Guest' for m in hs()['project']['messages']),'Host did not receive attributed guest chat')
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
        proposal(changed)
        message(gs,gw,'@centaur Change the application title to Family Planner.')
        until(lambda:(hs().get('child') or {}).get('title')=='Family Planner' and (gs().get('child') or {}).get('title')=='Family Planner','Agent change did not reach both native apps',timeout=20)
        assert len(hs()['projects'])==1 and len(gs()['projects'])==1,'App changes duplicated a project'
        assert not hs()['project'].get('proposal'),'Compatible request required author approval'
        summary['checks'].append('guest-agent-request-native-validation-and-live-update-without-approval-or-duplicates')
        assert list((source.parent/'.centaur').glob('remote-*.png')), 'Guest canvas image did not reach the host'
        summary['checks'].append('canvas-image-attached-from-guest-without-chat')
        revision=hs()['project']['revision']
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
