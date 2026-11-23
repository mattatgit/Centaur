"""Native multiplayer regressions in disposable GTK4 host and guest profiles."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
from random import Random
import shutil
import signal
import time

from PIL import Image

from avatars import prepare_avatar
from check import target, until
from ink_check import place_agent_pointer
from workspace_polish_check import move_over


def fixture_avatar(path,colour,alpha=False):
    pixels=Random(path.stem).randbytes(640*640*3)
    image=Image.frombytes('RGB',(640,640),pixels)
    image.paste(colour,(255,255,385,385))
    if alpha:
        image=image.convert('RGBA')
        image.paste((0,0,0,0),(0,0,100,640))
    image.save(path)
    return path


def select_avatar(driver,state,window,click,source):
    click(state,window,'settings-avatar')
    chooser=until(lambda:next((node for node in driver.nodes() if node.get('name')=='Choose an avatar'
                              and node.get('pid')==state()['pid']),None),'Avatar chooser missing')
    driver.ipc(f"[con_id={chooser['id']}] focus")
    driver.key('ctrl+l')
    time.sleep(.25)
    driver.key('ctrl+a')
    driver.type(str(source))
    driver.key('Return')


def check_multiplayer(driver, folder, launch, click, message, bridge, env, host, hw, reply, starter):
    evidence=folder/'multiplayer'
    evidence.mkdir()
    host_root,guest_root=folder/'host-data',folder/'multiplayer-guest-data'
    guest_root.mkdir(mode=0o700)
    guest_avatar=guest_root/'profile-avatar'
    guest_wire=guest_root/'profile-avatar-wire'
    alpha=fixture_avatar(folder/'avatar-alpha.png',(224,96,43),True)
    shutil.copyfile(alpha,guest_avatar)
    guest_avatar.chmod(0o600)
    control=bridge(host_root,env)
    guest_process,guest,gw=launch('multiplayer-guest')

    def projects(state,window):
        if state()['page']!='projects': click(state,window,'nav-projects')
        until(lambda:state()['page']=='projects' and not state()['motion']['workspaceRunning'],'Projects did not settle')

    def opened(state):
        return state()['project'].get('id')==pid and (state().get('child') or {}).get('ready')

    def invite_and_join():
        before=control.data.get('invitation')
        control.send('invite',address='127.0.0.1')
        code=until(lambda:control.data.get('invitation') if control.data.get('invitation')!=before else None,'Invitation unavailable')
        projects(guest,gw); click(guest,gw,'join')
        until(lambda:guest()['form']=='Join a project','Join dialog missing')
        driver.type(code); driver.key('Return')
        until(lambda:opened(guest) and guest()['status']=='Guest connected','Disposable guest could not join')

    def reopen_guest():
        nonlocal guest_process,guest,gw
        guest_process.send_signal(signal.SIGTERM)
        assert guest_process.wait(timeout=5)==0
        guest_process,guest,gw=launch('multiplayer-guest')
        click(guest,gw,'open-'+pid)
        until(lambda:opened(guest) and guest()['status']=='Guest connected','Guest did not reconnect to saved membership')

    def remote_image(state,root,author,expected):
        key=hashlib.sha256(expected).hexdigest()
        def synced():
            people=state()['project'].get('sharing',{}).get('participants',[])
            path=root/'avatars'/key
            return any(person['name']==author and person.get('avatar')==key for person in people) and path.is_file() and path.read_bytes()==expected
        until(synced,'Verified small avatar did not reach the other device')
        return key

    @contextmanager
    def hold_coordinator():
        pid_host=int((host_root/'session.lock').read_text().splitlines()[0])
        command=Path(f'/proc/{pid_host}/cmdline').read_bytes().split(b'\0')
        assert str(host_root).encode() in command and any(b'centaur-host' in part for part in command)
        os.kill(pid_host,signal.SIGSTOP)
        try: yield
        finally: os.kill(pid_host,signal.SIGCONT)

    def draw(state,window,colour,label,y_fraction):
        click(state,window,'mode-Build'); click(state,window,'tool-draw')
        assert state()['drawingColor']==colour
        cx,cy,_,_=target(state,'canvas'); view=state()['viewport']
        x=round(cx+view['app_x']+.25*view['app_width']*view['scale'])
        y=round(cy+view['app_y']+y_fraction*view['app_height']*view['scale'])
        def pixels(name):
            path=evidence/(name+'.png'); driver.screenshot(window,path)
            with Image.open(path) as image:
                region=image.convert('RGB').crop((x+25,y-3,x+34,y+4))
                rgb=tuple(int(colour[i:i+2],16) for i in (1,3,5))
                return any(max(abs(a-b) for a,b in zip(value,rgb))<45 for value in region.getdata())
        with hold_coordinator():
            driver.drag_path(window,x,y,[(65,0)])
            mark=until(lambda:next(iter(state()['inkPending']),None),'Completed stroke vanished before its acknowledgement',timeout=3)
            assert mark not in {a['id'] for a in state()['project']['annotations']}
            assert pixels(label+'-before-sync'),'Pending stroke was missing from the rendered canvas'
        until(lambda:all(any(a['id']==mark and a['color']==colour for a in current()['project']['annotations'])
                         for current in (host,guest)) and not state()['inkPending'],'Stroke was not replaced by one authoritative mark')
        assert pixels(label+'-after-sync'),'Saved stroke changed colour or position on acknowledgement'

    def conflict_requests(host_text,guest_text,number):
        gate=evidence/f'conflict-gate-{number}'
        final={'kind':'proposal','message':'Use both proposed headings','conflict':
               {'reason':'The two participants requested incompatible headings','authors':['Matt',guest()['author']]},
               'gtk':starter}
        reply.write_text(json.dumps({'kind':'question','message':'Waiting for other directions',
                                     'fixtureProgressGate':str(gate),'fixtureFinalReply':final}))
        message(host,hw,host_text)
        until(lambda:host()['busy'],'The first concurrent build did not start')
        message(guest,gw,guest_text); gate.write_text('finish')
        until(lambda:all(s()['project'].get('proposal',{}).get('conflict') for s in (host,guest)),'Concurrent requests did not produce a conflict')
        return host()['project']['proposal']

    try:
        until(lambda:control.data.get('snapshotReady'),'Host bridge unavailable')
        control.send('create',name='Multiplayer Verification',description='Disposable collaboration project')
        pid=until(lambda:control.data.get('project',{}).get('id') if control.data.get('project',{}).get('name')=='Multiplayer Verification' else None,
                  'Could not create multiplayer project')
        projects(host,hw); click(host,hw,'open-'+pid); until(lambda:opened(host),'Host native app unavailable')
        message(host,hw,'Project note from before sharing')
        click(guest,gw,'nav-settings'); click(guest,gw,'settings-name')
        driver.key('ctrl+a'); driver.type('Framework')
        until(lambda:guest()['author']=='Framework','Guest name did not save')
        invite_and_join()
        shared_host=(host_root/'profile-avatar-wire').read_bytes()
        assert guest_avatar.read_bytes()==alpha.read_bytes()
        with Image.open(guest_wire) as image:
            assert image.size==(256,256) and image.format=='PNG' and image.getchannel('A').getextrema()[0]==0
        shared_guest=guest_wire.read_bytes()
        remote_image(guest,guest_root,'Matt',shared_host); remote_image(host,host_root,'Framework',shared_guest)
        message(host,hw,'Host profile image'); message(guest,gw,'Guest profile image')
        for name,state,window in (('host',host,hw),('guest',guest,gw)):
            until(lambda:len(state()['chatRows'])>=3 and all(row['avatar'].get('image') for row in state()['chatRows'][:3]),
                  'Chat rendered initials instead of profile images')
            driver.screenshot(window,evidence/f'avatars-chat-{name}.png')
            projects(state,window); move_over(driver,window,target(state,'open-'+pid))
            target(state,'collaborators-'+pid); driver.screenshot(window,evidence/f'avatars-roster-{name}.png')
            click(state,window,'open-'+pid); until(lambda:opened(state),'Could not return to canvas')
        # Use the same preparation and bridge notification as Settings for a
        # live change, keeping this assertion independent of file picker focus.
        replacement=fixture_avatar(folder/'avatar-updated.png',(178,61,130),True)
        shutil.copyfile(replacement,guest_avatar)
        prepare_avatar(guest_avatar,guest_wire)
        updated=guest_wire.read_bytes()
        assert updated!=shared_guest
        guest_control=bridge(guest_root,env)
        try:
            until(lambda:any(p['id']==pid and p.get('connected') for p in guest_control.data.get('projects',[])),
                  'Avatar change bridge did not reconnect')
            guest_control.send('refreshAvatar')
            remote_image(host,host_root,'Framework',updated)
        finally:
            guest_control.close()
        reopen_guest()
        remote_image(host,host_root,'Framework',updated); remote_image(guest,guest_root,'Matt',shared_host)
        print('PASS: remote avatar transfer, active replacement and reconnect',flush=True)

        draw(host,hw,'#138EF5','host-blue',.33); draw(guest,gw,'#FF6157','guest-red',.52)
        print('PASS: host and guest strokes present before and after acknowledgement',flush=True)
        place_agent_pointer(driver,guest,gw,click)
        message(guest,gw,'Look at this part of the app')
        active=until(lambda:host()['project'].get('humanPointer'),'Human pointer did not sync')
        for state,window,name in ((host,hw,'host'),(guest,gw,'guest')):
            line=until(lambda:state()['sharedPointer'] if state()['sharedPointer']['tail'] else None,'Message pointer was not rendered')
            x,y,w,_=line['messageBounds']
            assert all(abs(a-b)<.1 for a,b in zip(line['tail'],(x+w,y)))
            driver.screenshot(window,evidence/f'pointer-{name}.png')
        previous=guest()['sharedPointer']
        click(guest,gw,'zoom'); driver.key('Home','Return')
        until(lambda:guest()['viewport']['mode']=='50%' and guest()['sharedPointer']['head']!=previous['head'],
              'Shared pointer did not follow the zoomed app')
        message(guest,gw,'A further note by the same author')
        assert host()['project']['humanPointer']['messageId']==active['messageId']
        for n in range(7): message(guest,gw,f'Follow-up {n} '+('Keep the pointer anchored as the conversation scrolls. '*7))
        until(lambda:not host()['sharedPointer']['tail'] and host()['project'].get('humanPointer'),'Offscreen pointer tail was still rendered')
        move_over(driver,hw,target(host,'chat-scroller')); driver.scroll(up=True)
        until(lambda:host()['sharedPointer']['tail'],'Pointer failed to return when its message scrolled into view')
        message(host,hw,'I have seen the pointer')
        until(lambda:all(not state()['project'].get('humanPointer') and not state()['sharedPointer']['tail']
                         for state in (host,guest)),'The other participant’s reply did not clear the arrow everywhere')
        print('PASS: shared pointer anchor, zoom, scroll and reply lifetime',flush=True)

        # A queued conflicting request must stay parked during voting, even if
        # it would otherwise return a valid automatic app update.
        revision=host()['project']['revision']
        start_bytes=(host_root/'projects'/pid/'App.gtk.json').read_bytes()
        proposal=conflict_requests('@centaur Use the Host Choice heading','@centaur Use the Framework Choice heading',1)
        choices=proposal['choices']
        assert len(choices)==2 and host()['project']['queueCount']>=1
        host_choice=next(key for key,choice in choices.items() if choice['author']=='Matt')
        resolved=json.loads(json.dumps(starter))
        resolved['files']['app.ui']=resolved['files']['app.ui'].replace('Family board','Host Choice')
        reply.write_text(json.dumps({'kind':'proposal','message':'Use the Host Choice heading','conflict':None,'gtk':resolved}))
        click(host,hw,'accept')
        until(lambda:host().get('approvalStatus')=='1 of 2 agreed — waiting for Framework','Host vote did not show the waiting participant')
        driver.screenshot(hw,evidence/'conflict-one-vote.png')
        reopen_guest()
        assert guest()['project']['revision']==revision
        assert (host_root/'projects'/pid/'App.gtk.json').read_bytes()==start_bytes
        def choose_host(state,window):
            index=list(state()['project']['proposal']['choices']).index(host_choice)+1
            click(state,window,'approval-choice'); driver.key('Home',*(['Down']*index),'Return')
            click(state,window,'accept')
        choose_host(guest,gw)
        until(lambda:host().get('approvalStatus','').startswith('Different choices'),'Mismatched votes were not exposed')
        assert host()['project']['revision']==revision
        choose_host(host,hw)
        until(lambda:all((state().get('child') or {}).get('title')=='Host Choice' for state in (host,guest)),
              'Both agreeing to the original request did not apply it',timeout=25)
        assert host()['project']['revision']==guest()['project']['revision']==revision+1
        driver.screenshot(gw,evidence/'conflict-agreed.png')

        conflict_requests('@centaur Try a smaller heading','@centaur Try a larger heading',2)
        click(guest,gw,'reject-proposal')
        until(lambda:not host()['project'].get('proposal'),'Decline did not close the conflict')
        assert host()['project']['revision']==revision+1
        projects(guest,gw); click(guest,gw,'menu-'+pid); click(guest,gw,'menu-delete-'+pid); click(guest,gw,'delete-confirm')
        until(lambda:not (guest_root/'shared'/pid/'connection.json').exists(),'Guest did not leave before a new invite')
        invite_and_join()
        remote_image(guest,guest_root,'Matt',shared_host)
        remote_image(host,host_root,guest()['author'],updated)
        assert guest()['drawingColor']=='#FF6157'
        projects(host,hw)
    finally:
        control.close()
    return ['remote-original-sized-and-alpha-avatars-update-and-survive-reconnect-and-rejoin',
            'optimistic-strokes-render-continuously-on-both-profiles-and-keep-participant-colours',
            'human-message-pointer-tracks-scroll-and-zoom-and-clears-on-the-other-participants-reply',
            'queued-conflict-waits-for-each-identity-and-the-same-option-across-reconnect-decline-and-once-only-application']
