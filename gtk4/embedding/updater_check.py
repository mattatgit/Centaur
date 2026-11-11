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
from check import read,until,target
from integration_check import Bridge
from test_driver import Driver
from updater import Runtime, CACHE, KEY, NIX_FLAGS
from download_progress import DownloadProgress, download_plan, path_info
from PIL import Image
from progress_check import check_progress
from footer_check import check_footer


def download_counter(folder,manifest):
    # The GUI candidate is already in the CI store. Independently fetch a real,
    # signed, reference-free cache object into an EMPTY store to exercise HTTP
    # progress, without deleting anything from the runner's shared store.
    work=folder/'download-progress'; work.mkdir()
    runtime=Runtime(work)
    remote=path_info(json.loads(runtime.nix('path-info','--store',CACHE,'--recursive','--json',manifest['storePath'])))
    leaves=[(p,v) for p,v in remote.items() if not v['references'] and 524288<=v.get('downloadSize',0)<=8000000]
    path,info=min(leaves,key=lambda pair:pair[1]['downloadSize'])
    updates=[]
    tracker=DownloadProgress(CACHE,download_plan(CACHE,{path:info},{}),lambda done,total:updates.append([done,total]))
    runtime.copy_with_progress(['nix',*NIX_FLAGS,'--log-format','internal-json','copy','--from',CACHE,
                               '--to',str(work/'empty-store'),'--extra-trusted-public-keys',KEY,path],tracker)
    assert updates[0]==[0,info['downloadSize']] and updates[-1]==[info['downloadSize']]*2,updates
    assert any(done>0 for done,total in updates),'Real Nix transfer reported no payload bytes'
    (work/'progress.json').write_text(json.dumps({'storePath':path,'updates':updates},indent=2))
    check_progress(driver=Driver(),folder=folder/'visible-download',path=path,info=info)


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
    process=None
    state=lambda:read(report/'shell.json'); new_pid=None; control=None
    summary={'checks':[],'real_nix_profile':True,'signed_cache':True,'production_approved':False}
    try:
        check_footer(driver,folder/'footer-states')
        download_counter(folder,manifest)
        process=subprocess.Popen([str(profile/'bin/centaur-gtk4'),'--data-dir',str(data),'--report-dir',str(report)],env=env)
        summary['checks'].append('real-signed-cache-compressed-byte-counter-into-empty-store')
        summary['checks'].append('throttled-signed-nar-settings-and-footer-advance-before-copy-exit')
        until(lambda:state().get('targets',{}).get('create'),'Old fixture did not map')
        assert state()['branding']=={'appIcon':'org.centaur.Gtk4','fullIcon':True,'symbolicIcon':True},state()['branding']
        desktop=home/'.local/share/applications/org.centaur.Gtk4.desktop'
        assert desktop.is_symlink() and desktop.resolve()==previous/'share/applications/org.centaur.Gtk4.desktop'
        preferences=read(home/'.config/centaur-gtk4/desktop.json')
        assert preferences['dataDir']==str(data) and preferences['environment']['GSK_RENDERER']=='cairo'
        import configparser
        entry=configparser.ConfigParser(interpolation=None); entry.read(desktop)
        assert entry['Desktop Entry']['Icon']=='org.centaur.Gtk4'
        assert entry['Desktop Entry']['StartupWMClass']=='org.centaur.Gtk4'
        for size in (16,24,32,48,64,128,256,512):
            with Image.open(previous/f'share/icons/hicolor/{size}x{size}/apps/org.centaur.Gtk4.png') as image:
                assert image.size==(size,size) and image.mode=='RGBA'
        summary['checks'].append('desktop-id-and-color-symbolic-icons-user-registration-renderer-preservation')
        window=driver.find_window('org.centaur.Gtk4',process.pid)
        def click(name):
            x,y,w,h=target(state,name)
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
        control.send('invite',address='127.0.0.1')
        until(lambda:control.data.get('invitation'),'Fixture collaboration identity was not created')
        time.sleep(.2); control.close(); control=None
        auth=home/'.config/omp/auth.json'; auth.parent.mkdir(parents=True,exist_ok=True); auth.write_text('opaque-test-credentials')
        before={str(p.relative_to(data)):p.read_bytes() for p in data.rglob('*') if p.is_file() and p.suffix in ('.json','.ini','.jsonl','.key','.pem')}
        # Availability must reach the workspace without visiting Settings.
        until(lambda:state().get('updater',{}).get('available'),'Background update check did not detect the published version')
        assert state()['updater']['badgeVisible']
        badge=state()['targets']['update-badge']; assert badge[2:]==[8,8],'Update badge is not 8px'
        version=state()['targets']['update-version']; composer=state()['targets']['composer']
        assert version[0]==composer[0],'Version button is not left aligned with the composer'
        assert state()['updater']['footerLabel']=='Update available'
        driver.screenshot(window,folder/'footer-update-available.png')
        rect=driver.rect(window)
        driver.ipc(f"seat seat0 cursor set {round(rect['x']+version[0]+version[2]/2)} {round(rect['y']+version[1]+version[3]/2)}")
        driver.seat_command('motion 0 0')
        until(lambda:state()['updater']['footerLabel']=='Update app','Version button hover did not show Update app')
        assert state()['targets']['update-version']==version,'Version button shifted or resized on hover'
        driver.screenshot(window,folder/'footer-update-hover.png')
        with Image.open(folder/'footer-update-hover.png') as source:
            pixels=source.convert('RGB'); x,y,w,h=map(round,state()['targets']['update-caption'])
            assert pixels.getpixel((x+4,y+h//2))==(235,235,235),'Version hover has no grey background'
            assert pixels.getpixel((x,y))==(255,255,255),'Version hover corners are not rounded'
            assert w<version[2]-24,'Highlight retained the version width'
            assert pixels.getpixel((x+w+4,y+h//2))!=(235,235,235),'Hover paints reserved label space'
        # Move away and reach the action using native keyboard traversal.
        click('editor')
        for _ in range(6):
            driver.key('Tab'); time.sleep(.25)
            if state()['updater']['footerFocused']: break
        assert state()['updater']['footerFocused'] and state()['updater']['footerLabel']=='Update app','Footer action is not keyboard accessible'
        click('nav-projects'); click('nav-settings')
        assert state()['updater']['version'].endswith('+0000000'),'Settings reported the wrong installed version'
        driver.screenshot(window,folder/'update-available.png')
        click('nav-projects'); click('open-'+project_id)
        until(lambda:(state().get('child') or {}).get('ready'),'Workspace did not reopen for footer update')
        click('update-version')
        work=Path(until(lambda:state().get('updater',{}).get('work'),'Detached updater did not start'))
        until(lambda:not state()['updater']['footerSensitive'],'Footer allowed a second update while one was active')
        driver.screenshot(window,folder/'footer-update-running.png')
        samples=[]
        def exited():
            data=state()
            if data.get('updater',{}).get('running'):
                assert data['page']=='workspace','Footer update navigated away from chat'
                assert data['updater']['footerLabel']=='Updating…','Running update did not replace action label'
                assert data['updater']['footerStatus']==data['updater']['status'],'Footer did not mirror live update status'
                text=data['updater']['footerStatus']
                if not samples or text!=samples[-1]: samples.append(text)
            return process.poll() is not None
        until(exited,'Old Centaur did not exit for its update',timeout=180)
        (folder/'footer-status-samples.json').write_text(json.dumps(samples,indent=2))
        until(lambda:read(work/'status.json').get('phase') in ('complete','recovered','failed','recovery-required'),
              'Update did not finish',timeout=90)
        receipt=read(work/'status.json')
        assert receipt['phase']=='complete',receipt
        ready=read(work/'ready.json'); new_pid=ready['pid']
        until(lambda:state().get('pid')==new_pid and state().get('project',{}).get('id')==project_id,'New GTK window did not restore the project')
        assert profile.resolve()==Path(manifest['storePath'])
        assert desktop.resolve()==profile.resolve()/'share/applications/org.centaur.Gtk4.desktop','Desktop entry pinned the old package'
        assert state()['updater']['version']==manifest['version'].removeprefix('Centaur GTK4 ')
        assert state()['page']=='workspace','Footer update did not restore the workspace'
        until(lambda:not state()['updater']['badgeVisible'],'Updated version retained its availability badge')
        assert any(m.get('text')=='Keep this conversation' for m in state()['project']['messages'])
        for name,content in before.items(): assert (data/name).read_bytes()==content,'Updater modified project/configuration '+name
        assert qt.resolve()==previous and (qt_data/'keep').read_text()=='preserved Qt data'
        assert auth.read_text()=='opaque-test-credentials','Updater changed existing OMP credentials'
        new_window=driver.find_window('org.centaur.Gtk4',new_pid); driver.screenshot(new_window,folder/'updated-app.png')
        until(lambda:state()['updater']['footerLabel']=='v'+state()['updater']['version'],'Restart did not restore installed version')
        x,y,w,h=target(state,'update-version'); driver.click(new_window,round(x+w/2),round(y+h/2))
        until(lambda:state()['updater']['footerStatus']=='Up to date','Real no-update check did not show transient notice')
        assert state()['updater']['footerLabel']=='v'+state()['updater']['version'],'Stationary pointer kept action after real no-update check'
        driver.screenshot(new_window,folder/'footer-up-to-date.png')
        until(lambda:state()['updater']['footerStatus']=='','Real no-update notice did not clear')
        assert state()['updater']['footerLabel']=='v'+state()['updater']['version']
        summary['checks']+=['settings-version-and-published-update','footer-background-availability-8px-badge-alignment-hover-and-keyboard',
                            'footer-natural-width-paint-stable-geometry-pointer-and-focus-rearm-transient-no-update',
                            'footer-click-live-status-detached-download-signature-verification',
                            'real-nix-profile-switch-and-gtk-restart','project-chat-preferences-identities-preserved',
                            'qt-profile-and-data-preserved']
        maintenance(folder,env); summary['checks'].append('real-host-maintenance-gate-and-busy-agent-refusal')
        summary['passed']=True
    finally:
        if control: control.close()
        if process:
            if process.poll() is None: process.terminate()
            process.wait(timeout=10)
        if new_pid:
            try: os.kill(new_pid,signal.SIGTERM)
            except ProcessLookupError: pass
            until(lambda:not Path(f'/proc/{new_pid}').exists() or Path(f'/proc/{new_pid}/stat').read_text().split()[2]=='Z','Updated window did not close')
        subprocess.run([str(previous/'bin/centaur-host'),'--stop','--data-dir',str(data)],env=env,timeout=10,check=True)
        # Upload only diagnostics, never the temporary home's identity keys.
        import shutil
        diagnostics=folder/'transaction'; diagnostics.mkdir(exist_ok=True)
        for work in (home/'.local/state/centaur-gtk4-updater').glob('run-*'):
            for name in ('status.json','ready.json','request.json','resume.json','helper.log','application.log'):
                if (work/name).is_file(): shutil.copyfile(work/name,diagnostics/name)
        (folder/'summary.json').write_text(json.dumps(summary,indent=2))
        print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
