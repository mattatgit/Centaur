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
    driver=Driver(); driver.ipc('output HEADLESS-1 mode 1920x1200')
    home=folder/'home'; home.mkdir()
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
        download_counter(folder,manifest)
        process=subprocess.Popen([str(profile/'bin/centaur-gtk4'),'--data-dir',str(data),'--report-dir',str(report)],env=env)
        summary['checks'].append('real-signed-cache-compressed-byte-counter-into-empty-store')
        summary['checks'].append('throttled-signed-nar-settings-and-footer-advance-before-copy-exit')
        until(lambda:state().get('targets',{}).get('project-menu'),'Old fixture did not map')
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
        driver.track_native(window,state); driver.resize(window,1440,1024)
        until(lambda:state().get('windowSize')==[1440,1024],'Update fixture did not allocate its native window')
        driver.ipc(f'[con_id={window}] move position 0 px 0 px')
        def reach(name):
            for _ in range(24):
                x,y,w,h=target(state,name)
                if name!='update-app' or 80<=y and y+h<=state()['windowSize'][1]-16: return x,y,w,h
                # App is below the fold in the full Settings page. Exercise
                # native scrolling instead of clicking an off-window target.
                r=driver.rect(window)
                driver.ipc(f"seat seat0 cursor set {round(r['x']+x+w/2)} {round(r['y']+state()['windowSize'][1]/2)}")
                driver.seat_command('motion 0 0');driver.scroll(up=y<80)
            raise AssertionError('Settings updater could not be scrolled into view')
        def click(name):
            if name in ('create','join'): click('project-menu')
            x,y,w,h=reach(name)
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
        avatar=data/'profile-avatar'; Image.new('RGB',(80,80),(64,128,192)).save(avatar,format='PNG')
        avatar_bytes=avatar.read_bytes()
        before={str(p.relative_to(data)):p.read_bytes() for p in data.rglob('*') if p.is_file() and p.suffix in ('.json','.ini','.jsonl','.key','.pem')}
        # Availability must reach the workspace without visiting Settings.
        until(lambda:state().get('updater',{}).get('available'),'Background update check did not detect the published version')
        assert state()['updater']['iconState']=='available'
        art=state()['targets']['update-art']; assert art[2:]==[16,16],'Original update artwork is not 16px'
        version=state()['targets']['update-icon']; composer=state()['targets']['composer'];chip=state()['targets']['version-chip']
        assert version[0]==composer[0] and abs(chip[0]+chip[2]-composer[0]-composer[2])<=1,'Footer icon/chip differs from the Figma alignment'
        assert state()['updater']['footerLabel']=='Update available'
        driver.screenshot(window,folder/'footer-update-available.png')
        rect=driver.rect(window)
        driver.ipc(f"seat seat0 cursor set {round(rect['x']+version[0]+version[2]/2)} {round(rect['y']+version[1]+version[3]/2)}")
        driver.seat_command('motion 0 0')
        until(lambda:state()['updater']['iconState']=='available','Hover changed update availability')
        assert state()['targets']['update-icon']==version and state()['targets']['version-chip']==chip,'Hover shifted footer layout'
        driver.screenshot(window,folder/'footer-update-hover.png')
        assert any(s['file']=='v2/pass2/d0b9d.svg' and s['bounds'][2:]==[16,16] for s in state()['assetSlots']),'Available icon is not the original Figma export'
        # Move away and reach the action using native keyboard traversal.
        click('editor')
        for _ in range(6):
            driver.key('Tab'); time.sleep(.25)
            if state()['updater']['footerFocused']: break
        assert state()['updater']['footerFocused'] and state()['updater']['iconState']=='available','Footer action is not keyboard accessible'
        click('nav-projects'); click('nav-settings')
        assert state()['updater']['version'].endswith('+0000000'),'Settings reported the wrong installed version'
        driver.screenshot(window,folder/'update-available.png')
        click('update-app');until(lambda:state()['updater']['confirmationVisible'],'Settings did not ask before downloading')
        assert not state()['updater']['work'] and profile.resolve()==previous
        driver.screenshot(window,folder/'settings-restart-warning.png');click('update-cancel')
        assert not state()['updater']['work'] and profile.resolve()==previous,'Not now started an update'
        click('nav-projects'); click('open-'+project_id)
        until(lambda:(state().get('child') or {}).get('ready'),'Workspace did not reopen for footer update')
        click('update-icon');until(lambda:state()['updater']['confirmationVisible'],'Footer did not ask before downloading')
        assert not state()['updater']['work'] and profile.resolve()==previous
        click('update-cancel');assert not state()['updater']['work'] and profile.resolve()==previous
        click('update-icon');until(lambda:state()['updater']['confirmationVisible'],'Footer confirmation did not reopen');click('update-confirm')
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
        until(lambda:state()['updater']['iconState']=='complete','Completed updater did not show the real checkmark')
        assert any(m.get('text')=='Keep this conversation' for m in state()['project']['messages'])
        for name,content in before.items(): assert (data/name).read_bytes()==content,'Updater modified project/configuration '+name
        assert qt.resolve()==previous and (qt_data/'keep').read_text()=='preserved Qt data'
        assert auth.read_text()=='opaque-test-credentials','Updater changed existing OMP credentials'
        assert avatar.read_bytes()==avatar_bytes,'Updater changed the saved avatar'
        new_window=driver.find_window('org.centaur.Gtk4',new_pid)
        driver.track_native(new_window,state); driver.screenshot(new_window,folder/'updated-app.png')
        assert state()['updater']['versionChip']=='v'+state()['updater']['version']
        # Repeat the real transaction from Settings, using only the disposable
        # CI profile and already-built previous-version fixture.
        os.kill(new_pid,signal.SIGTERM)
        until(lambda:not Path(f'/proc/{new_pid}').exists() or Path(f'/proc/{new_pid}/stat').read_text().split()[2]=='Z','First updated window did not close')
        subprocess.run([str(previous/'bin/centaur-host'),'--stop','--data-dir',str(data)],env=env,timeout=10,check=True);new_pid=None
        subprocess.run([*nix,'build','--offline','--no-link','--profile',str(profile),str(previous)],env=env,check=True)
        process=subprocess.Popen([str(profile/'bin/centaur-gtk4'),'--data-dir',str(data),'--report-dir',str(report)],env=env)
        until(lambda:state().get('pid')==process.pid and state()['updater']['version'].endswith('+0000000'),'Settings update fixture did not map')
        window=driver.find_window('org.centaur.Gtk4',process.pid);driver.track_native(window,state)
        click('nav-settings');until(lambda:state()['updater']['available'],'Settings fixture did not discover the signed update')
        click('update-app');until(lambda:state()['updater']['confirmationVisible'],'Settings update bypassed confirmation')
        assert not state()['updater']['work'];click('update-confirm')
        work=Path(until(lambda:state()['updater']['work'],'Confirmed Settings updater did not start'))
        until(lambda:process.poll() is not None,'Settings updater did not exit for restart',timeout=180)
        until(lambda:read(work/'status.json').get('phase') in ('complete','recovered','failed','recovery-required'),'Settings update did not finish',timeout=90)
        assert read(work/'status.json')['phase']=='complete'
        new_pid=read(work/'ready.json')['pid']
        until(lambda:state().get('pid')==new_pid and state()['page']=='settings' and state()['updater']['version']==manifest['version'].removeprefix('Centaur GTK4 '),'Settings update did not restore its page/version')
        until(lambda:state()['updater']['iconState']=='complete','Settings completion did not show the real checkmark')
        assert profile.resolve()==Path(manifest['storePath'])
        for name,content in before.items():assert (data/name).read_bytes()==content,'Settings update changed saved data '+name
        assert qt.resolve()==previous and (qt_data/'keep').read_text()=='preserved Qt data'
        assert auth.read_text()=='opaque-test-credentials' and avatar.read_bytes()==avatar_bytes
        new_window=driver.find_window('org.centaur.Gtk4',new_pid);driver.track_native(new_window,state)
        window=new_window;reach('update-app')
        driver.screenshot(new_window,folder/'settings-updated-app.png')
        click('update-app')
        until(lambda:state()['updater']['footerStatus']=='Up to date','Real no-update check did not show transient notice')
        assert state()['updater']['versionChip']=='v'+state()['updater']['version']
        driver.screenshot(new_window,folder/'footer-up-to-date.png')
        until(lambda:state()['updater']['footerStatus']=='','Real no-update notice did not clear')
        assert state()['updater']['versionChip']=='v'+state()['updater']['version']
        summary['checks']+=['settings-version-and-published-update','figma-original-download-icon-right-version-chip-and-native-keyboard',
                            'both-entry-points-restart-warning-and-not-now-without-transaction',
                            'confirmed-footer-live-status-detached-download-signature-verification',
                            'confirmed-settings-real-profile-switch-restart-and-restored-settings-page',
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
            transaction=diagnostics/work.name;transaction.mkdir(exist_ok=True)
            for name in ('status.json','ready.json','request.json','resume.json','helper.log','application.log'):
                if (work/name).is_file(): shutil.copyfile(work/name,transaction/name)
        (folder/'summary.json').write_text(json.dumps(summary,indent=2))
        print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
