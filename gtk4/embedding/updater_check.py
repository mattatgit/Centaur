"""Real Settings click -> signed cache -> Nix profile -> GTK restart, in CI only.

The previous-version fixture alone redirects discovery to a local release JSON.
The candidate is the real published package, and its pinned Cachix verification,
detached helper, host gate, profile switch and startup acknowledgement are real.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from check import read,until
from integration_check import Bridge
from test_driver import Driver


def maintenance(folder,env):
    root=folder/'maintenance'; root.mkdir()
    agent=folder/'waiting-agent'
    agent.write_text('#!'+sys.executable+'\nimport sys,time\nsys.stdin.read()\ntime.sleep(30)\n')
    agent.chmod(0o700)
    held=dict(env,CENTAUR_UPDATE_STARTING='native-updater-check',CENTAUR_AGENT=str(agent))
    host=subprocess.Popen([env['CENTAUR_GTK_HOST'],'--data-dir',str(root)],env=held)
    control=None
    try:
        # Opening the bridge also waits for the host's socket to become ready.
        time.sleep(.2); control=Bridge(root,env)
        until(lambda:control.data.get('updateHeld'),'New host did not hold work during activation')
        control.send('create',name='must wait',description='')
        time.sleep(.2); assert not control.data.get('projects'),'Held host accepted a new project'
        def command(*args):
            return subprocess.run([env['CENTAUR_GTK_HOST'],'--data-dir',str(root),*args],env=env,timeout=10).returncode
        assert command('--finish-update','wrong-token')==3,'Host accepted another transaction’s token'
        assert command('--finish-update','native-updater-check')==0
        until(lambda:not control.data.get('updateHeld'),'Host did not release its startup gate')
        assert command('--stop-if-idle')==3 and host.poll() is None,'Update interrupted another local window'
        control.send('create',name='busy project',description='')
        until(lambda:control.data.get('project',{}).get('id'),'Test project did not open')
        control.send('message',text='@centaur Wait for the test')
        until(lambda:control.data.get('updateBlocked'),'Agent activity was not exposed to the updater')
        control.close(); control=None
        assert command('--stop-if-idle')==3 and host.poll() is None,'Update interrupted a running agent'
    finally:
        if control: control.close()
        subprocess.run([env['CENTAUR_GTK_HOST'],'--stop','--data-dir',str(root)],env=env,timeout=10,check=True)
        host.wait(timeout=5)


def main():
    previous=Path(sys.argv[1]).resolve(); manifest=read(Path(sys.argv[2])); folder=Path(sys.argv[3]).resolve()
    folder.mkdir(parents=True,exist_ok=False)
    driver=Driver(); home=folder/'home'; home.mkdir()
    env=dict(os.environ,HOME=str(home),XDG_STATE_HOME=str(home/'.local/state'),
             XDG_DATA_HOME=str(home/'.local/share'),XDG_CONFIG_HOME=str(home/'.config'))
    # The real updater is production code. Only the old CI fixture's generated
    # launcher reads this variable; the released package has no feed override.
    feed=folder/'release.json'; feed.write_text(json.dumps({'tag_name':'gtk4-preview','draft':False,'prerelease':True,'body':json.dumps(manifest)}))
    env['CENTAUR_UPDATER_FIXTURE_FEED']=feed.as_uri()
    agent=folder/'agent'; agent.write_text('#!'+sys.executable+'\nprint(\'{"kind":"question","message":"Updater connection test"}\')\n'); agent.chmod(0o700)
    env['CENTAUR_AGENT']=str(agent)
    profile=home/'.local/state/nix/profiles/centaur-gtk4'; profile.parent.mkdir(parents=True)
    nix=['nix','--extra-experimental-features','nix-command flakes','--max-jobs','0','--builders','','--option','fallback','false']
    subprocess.run([*nix,'build','--offline','--no-link','--profile',str(profile),str(previous)],env=env,check=True)
    qt=home/'.local/state/nix/profiles/centaur'; qt.symlink_to(previous)  # sentinel only; never launched
    qt_data=home/'.local/share/Centaur/Centaur'; qt_data.mkdir(parents=True); (qt_data/'keep').write_text('preserved Qt data')
    data=home/'.local/share/Centaur/GTK4'; report=folder/'report'
    process=subprocess.Popen([str(profile/'bin/centaur-gtk4'),'--data-dir',str(data),'--report-dir',str(report)],env=env)
    state=lambda:read(report/'shell.json'); new_pid=None; control=None
    summary={'checks':[],'real_nix_profile':True,'signed_cache':True,'production_approved':False}
    try:
        until(lambda:state().get('targets',{}).get('create'),'Old fixture did not map')
        window=driver.find_window('org.centaur.Gtk4',process.pid)
        def click(name):
            x,y,w,h=until(lambda:state().get('targets',{}).get(name),'Missing updater UI control '+name)
            driver.click(window,round(x+w/2),round(y+h/2)); time.sleep(.15)
        click('create'); until(lambda:state().get('form'),'Project form did not open')
        driver.type('Keep this project'); driver.key('Return')
        until(lambda:(state().get('child') or {}).get('ready'),'Old project did not embed')
        project_id=state()['project']['id']
        control=Bridge(data,dict(env,CENTAUR_GTK_BRIDGE=str(previous/'bin/centaur-gtk4-bridge')))
        until(lambda:control.data.get('projects'),'Fixture bridge unavailable')
        control.send('open',projectId=project_id)
        until(lambda:control.data.get('project',{}).get('id')==project_id,'Project did not reopen')
        control.send('message',text='Keep this conversation')
        until(lambda:any(m.get('text')=='Keep this conversation' for m in state()['project'].get('messages',[])),'Fixture chat did not persist')
        control.send('grid',enabled=True,size=16,opacity=40,color='#BAE6FF')
        time.sleep(.2); control.close(); control=None
        before={str(p.relative_to(data)):p.read_bytes() for p in data.rglob('*') if p.is_file() and p.suffix in ('.json','.ini','.jsonl','.key')}
        click('nav-projects'); click('nav-settings')
        until(lambda:state().get('updater',{}).get('available'),'Published update was not detected')
        assert state()['updater']['version'].endswith('+0000000'),'Settings reported the wrong installed version'
        driver.screenshot(window,folder/'update-available.png')
        click('update-app')
        work=Path(until(lambda:state().get('updater',{}).get('work'),'Detached updater did not start'))
        until(lambda:process.poll() is not None,'Old Centaur did not exit for its update',timeout=180)
        until(lambda:read(work/'status.json').get('phase') in ('complete','recovered','failed','recovery-required'),
              'Update did not finish',timeout=90)
        receipt=read(work/'status.json')
        assert receipt['phase']=='complete',receipt
        ready=read(work/'ready.json'); new_pid=ready['pid']
        until(lambda:state().get('pid')==new_pid and state().get('project',{}).get('id')==project_id,'New GTK window did not restore the project')
        assert profile.resolve()==Path(manifest['storePath'])
        assert state()['updater']['version']==manifest['version'].removeprefix('Centaur GTK4 ')
        assert any(m.get('text')=='Keep this conversation' for m in state()['project']['messages'])
        for name,content in before.items(): assert (data/name).read_bytes()==content,'Updater modified project/configuration '+name
        assert qt.resolve()==previous and (qt_data/'keep').read_text()=='preserved Qt data'
        new_window=driver.find_window('org.centaur.Gtk4',new_pid); driver.screenshot(new_window,folder/'updated-app.png')
        summary['checks']+=['settings-version-and-published-update','settings-click-detached-download-signature-verification',
                            'real-nix-profile-switch-and-gtk-restart','project-chat-preferences-identities-preserved',
                            'qt-profile-and-data-preserved']
        maintenance(folder,env); summary['checks'].append('real-host-maintenance-gate-and-busy-agent-refusal')
        summary['passed']=True
    finally:
        if control: control.close()
        if process.poll() is None: process.terminate()
        process.wait(timeout=10)
        if new_pid:
            try: os.kill(new_pid,signal.SIGTERM)
            except ProcessLookupError: pass
            until(lambda:not Path(f'/proc/{new_pid}').exists() or Path(f'/proc/{new_pid}/stat').read_text().split()[2]=='Z','Updated window did not close')
        subprocess.run([str(previous/'bin/centaur-host'),'--stop','--data-dir',str(data)],env=env,timeout=10,check=True)
        (folder/'summary.json').write_text(json.dumps(summary,indent=2))
        print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
