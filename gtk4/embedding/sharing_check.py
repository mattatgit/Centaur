"""Exercise sharing decisions with native GTK windows and disposable profiles."""
import json
import signal
import subprocess
from check import target, until
from workspace_polish_check import move_over, record_motion


def check_sharing(driver, folder, launch, click, message, bridge, env, host, hw, guest, gw, prior_share):
    host_root=folder/'host-data'
    guest_root=folder/'guest-data'
    offline_root=folder/'offline-guest-data'
    evidence=folder/'sharing'
    evidence.mkdir()
    control=bridge(host_root,env)
    try:
        until(lambda:control.data.get('snapshotReady'),'Host fixture bridge did not connect')
        control.send('create',name='Weekend Planner',description='A shared native app')
        project=until(lambda:control.data.get('project') if control.data.get('project',{}).get('name')=='Weekend Planner' else None,
                      'Could not create sharing fixture')
        pid=project['id']
        assert control.data['collaborationRole']=='Host'

        def invite():
            previous=control.data.get('invitation')
            control.send('invite',address='127.0.0.1')
            return until(lambda:control.data.get('invitation') if control.data.get('invitation')!=previous else None,
                         'Could not create a fresh invitation')

        def projects(state,window):
            if state()['page']!='projects': click(state,window,'nav-projects')
            until(lambda:state()['page']=='projects' and not state()['motion']['workspaceRunning'],
                  'Projects view did not settle')

        def join(state,window,code):
            projects(state,window)
            click(state,window,'join')
            until(lambda:state().get('form')=='Join a project','Join modal did not open')
            driver.type(code); driver.key('Return')
            until(lambda:state().get('project',{}).get('id')==pid and state()['status']=='Guest connected'
                  and (state().get('child') or {}).get('ready'),'Guest did not join and embed the project')

        def roster(state,names):
            def current():
                for row in state().get('projects',[]):
                    if row['id']==pid:
                        members=row.get('collaborators',[])
                        if {person['name'] for person in members}==set(names): return members
            return until(current,'The participant roster was out of date')

        def avatars(state,window,names,who,filename):
            members=roster(state,names)
            assert [member['name'] for member in members if member['self']]==[who]
            projects(state,window)
            assert 'collaborators-'+pid not in state()['targets']
            move_over(driver,window,target(state,'open-'+pid))
            target(state,'collaborators-'+pid)
            driver.screenshot(window,evidence/filename)
            move_over(driver,window,target(state,'project-menu'))
            until(lambda:'collaborators-'+pid not in state()['targets'],'Avatars remained visible without hover')

        first_code=invite()
        projects(host,hw)
        click(host,hw,'open-'+pid)
        until(lambda:host().get('project',{}).get('id')==pid and (host().get('child') or {}).get('ready'),
              'Host did not embed the shared app')
        assert host()['role']=='Host'
        message(host,hw,'Shared planning notes')
        join(guest,gw,first_code)
        assert guest()['role']=='Guest'
        message(guest,gw,'Guest planning notes')
        prior_guest_project=next(p for p in guest()['projects'] if p['id']==prior_share)
        assert prior_guest_project['remote']

        other,offline,ow=launch('offline-guest')
        click(offline,ow,'nav-settings'); click(offline,ow,'settings-name')
        driver.key('ctrl+a'); driver.type('Riley')
        until(lambda:offline().get('author')=='Riley','Second guest identity was not saved')
        join(offline,ow,invite())
        avatars(host,hw,['Matt','Guest','Riley'],'Matt','01-host-roster.png')
        avatars(guest,gw,['Matt','Guest','Riley'],'Guest','02-guest-roster.png')
        click(guest,gw,'menu-'+pid)
        assert 'menu-stop-sharing-'+pid not in guest()['targets']
        driver.key('Escape')

        projects(offline,ow)
        click(offline,ow,'menu-'+pid); click(offline,ow,'menu-delete-'+pid)
        click(offline,ow,'delete-confirm')
        roster(host,['Matt','Guest']); roster(guest,['Matt','Guest'])
        connection=offline_root/'shared'/pid/'connection.json'
        until(lambda:not connection.exists(),'The departing guest retained an active connection')
        join(offline,ow,invite())
        roster(host,['Matt','Guest','Riley']); roster(guest,['Matt','Guest','Riley'])
        other.send_signal(signal.SIGTERM)
        assert other.wait(timeout=5)==0
        assert json.loads(connection.read_text()).get('memberToken')
        assert guest()['role']=='Guest'

        # Switch another project into the host workspace before using the
        # original tile's menu. The action must be scoped to the chosen tile.
        projects(host,hw)
        other_id=next(row['id'] for row in host()['projects'] if row['id']!=pid)
        click(host,hw,'open-'+other_id)
        until(lambda:host().get('project',{}).get('id')==other_id,'Host could not switch projects')
        projects(host,hw)
        host_source=host_root/'projects'/pid/'App.gtk.json'
        accepted=host_source.read_bytes()
        with record_motion(driver,hw,evidence/'host-stop-sharing.mp4'):
            click(host,hw,'menu-'+pid)
            driver.screenshot(hw,evidence/'03-host-project-menu.png')
            click(host,hw,'menu-stop-sharing-'+pid)
            until(lambda:host().get('form')=='Stop sharing?','Host confirmation did not open')
            assert 'stop-sharing-cancel' in host()['focusedTargets']
            driver.screenshot(hw,evidence/'04-host-confirmation.png',focus=False)
            click(host,hw,'stop-sharing-cancel')
            until(lambda:not host().get('form'),'Cancel did not close confirmation')
            assert not guest().get('endedShares')
            roster(host,['Matt','Guest','Riley'])
            click(host,hw,'menu-'+pid); click(host,hw,'menu-stop-sharing-'+pid)
            click(host,hw,'stop-sharing-confirm')
            until(lambda:any(row['id']==pid and not row.get('hostingShare') and not row.get('collaborators')
                             for row in host()['projects']),
                  'The project menu still reported active sharing')
            assert any(row.get('hostingShare') for row in host()['projects'] if row['id']==prior_share)
            assert host_source.read_bytes()==accepted

        until(lambda:guest().get('form')=='Sharing ended','Online guest was not notified')
        with record_motion(driver,gw,evidence/'guest-keep-copy.mp4'):
            driver.screenshot(gw,evidence/'05-guest-decision.png',focus=False)
            click(guest,gw,'sharing-choice-keep')
            copy=until(lambda:guest().get('project') if guest().get('project',{}).get('name')=='Weekend Planner'
                       and guest()['project']['id']!=pid and (guest().get('child') or {}).get('ready') else None,
                       'The retained project did not open as a new native app')
            assert guest()['role']=='Host' and not copy.get('remote')
            assert {'Shared planning notes','Guest planning notes'}<={item['text'] for item in copy['messages']}
            assert not guest()['endedShares']
            path=guest_root/'projects'/copy['id']
            assert (path/'App.gtk.json').read_bytes()==accepted
            assert subprocess.check_output(['git','-C',str(path),'remote'],text=True).strip()==''
            assert subprocess.check_output(['git','-C',str(path),'rev-list','--count','HEAD'],text=True).strip()=='1'
            assert not (guest_root/'shared'/pid/'connection.json').exists()
            message(guest,gw,'Independent edit')
            assert not any(m['text']=='Independent edit' for m in json.loads((host_source.parent/'.centaur/state.json').read_text())['messages'])
            projects(guest,gw)
            driver.screenshot(gw,evidence/'06-independent-project.png')
            click(guest,gw,'open-'+prior_share)
            until(lambda:guest().get('project',{}).get('id')==prior_share and guest().get('role')=='Guest',
                  'Switching from the retained project did not restore the Guest role')

        assert json.loads(connection.read_text()).get('memberToken')
        offline_process,offline,ow=launch('offline-guest')
        until(lambda:offline().get('form')=='Sharing ended','Offline guest did not receive the notice on reconnect')
        ended=json.loads(connection.read_text())
        assert ended.get('ended') and 'memberToken' not in ended
        assert not offline()['projects']
        offline_process.send_signal(signal.SIGTERM)
        assert offline_process.wait(timeout=5)==0
        _,offline,ow=launch('offline-guest')
        until(lambda:offline().get('form')=='Sharing ended','The offline guest choice was lost after restart')
        with record_motion(driver,ow,evidence/'offline-guest-declines.mp4'):
            driver.screenshot(ow,evidence/'07-offline-guest-decision.png',focus=False)
            click(offline,ow,'sharing-choice-decline')
            until(lambda:not offline().get('form') and not offline().get('endedShares'),'Decline did not clear the notice')
            assert not offline()['projects'] and not connection.exists()
            assert not list((offline_root/'projects').iterdir())
            driver.screenshot(ow,evidence/'08-offline-guest-declined.png')
    finally:
        control.close()
    return ['sharing-host-and-guest-roles-switch-with-projects-and-live-hover-rosters-follow-membership',
            'host-scoped-stop-sharing-confirmation-and-cancellation-preserve-app-and-other-share',
            'online-guest-creates-a-runnable-independent-app-and-offline-guest-can-decline-after-restart']
