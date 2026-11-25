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


def check_multiplayer(driver, folder, launch, click, message, bridge, env, host, hw, reply, starter,request_record):
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
        current=state()
        return (current['page']=='workspace' and not current['motion']['workspaceRunning'] and
                current['project'].get('id')==pid and (current.get('child') or {}).get('ready'))

    def invite_and_join(used_code=None):
        before=control.data.get('invitation')
        control.send('invite',address='127.0.0.1')
        code=until(lambda:control.data.get('invitation') if control.data.get('invitation')!=before else None,'Invitation unavailable')
        projects(guest,gw); click(guest,gw,'join')
        until(lambda:guest()['form']=='Join a project','Join dialog missing')
        if used_code:
            driver.type(used_code); driver.key('Return')
            until(lambda:'used' in guest()['error'],'Used invitation did not explain rejection')
            assert all(p['id']!=pid for p in guest()['projects']), 'Rejected invitation reopened a departed project'
            driver.screenshot(gw,evidence/'used-invitation.png')
            driver.key('Return')
            assert 'used' in guest()['error'], 'Unchanged rejected invitation was resubmitted'
            click(guest,gw,'join-code'); driver.key('ctrl+a')
        driver.type(code); driver.key('Return')
        until(lambda:opened(guest) and guest()['status']=='Guest connected','Disposable guest could not join')
        until(lambda:not guest()['error'],'Successful retry left the previous error visible')
        return code

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
        first_invitation=invite_and_join()
        from composer_check import check_composer
        check_composer(driver,evidence,click,host,hw,guest,gw,alpha,host_root,guest_root)
        shared_host=(host_root/'profile-avatar-wire').read_bytes()
        assert guest_avatar.read_bytes()==alpha.read_bytes()
        with Image.open(guest_wire) as image:
            assert image.size==(256,256) and image.format=='PNG' and image.getchannel('A').getextrema()[0]==0
        shared_guest=guest_wire.read_bytes()
        remote_image(guest,guest_root,'Matt',shared_host); remote_image(host,host_root,'Framework',shared_guest)
        message(host,hw,'Host profile image'); message(guest,gw,'Guest profile image')
        def chat_appearance(state,text):
            current=state()
            ident=next((m['id'] for m in current['project']['messages'] if m.get('text')==text),None)
            return current['chatMessageAppearance'].get(ident,{})
        for name,state,window in (('host',host,hw),('guest',guest,gw)):
            for text,author in (('Project note from before sharing','host'),
                                ('Host profile image','host'),('Guest profile image','guest')):
                def rendered_message():
                    row=chat_appearance(state,text)
                    return row if row.get('image') else None
                row=until(rendered_message,'Chat did not render the author’s image for '+text)
                assert row['own']==(name==author)
            driver.screenshot(window,evidence/f'avatars-chat-{name}.png')
            projects(state,window); move_over(driver,window,target(state,'open-'+pid))
            target(state,'collaborators-'+pid); assert state()['rosterImages']['collaborators-'+pid]==2
            driver.screenshot(window,evidence/f'avatars-roster-{name}.png')
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
        assert tuple(round(c*255) for c in guest()['commentPointer']['color'])==tuple(bytes.fromhex('FF6157'))
        driver.screenshot(gw,evidence/'pointer-guest-before-send.png')
        message(guest,gw,'Look at this part of the app')
        active=until(lambda:host()['project'].get('humanPointer'),'Human pointer did not sync')
        for state,window,name in ((host,hw,'host'),(guest,gw,'guest')):
            line=until(lambda:state()['sharedPointer'] if state()['sharedPointer']['tail'] else None,'Message pointer was not rendered')
            x,y,w,_=line['messageBounds']
            assert all(abs(a-b)<.1 for a,b in zip(line['tail'],(x+w-12,y+12)))
            assert line['color']=='#FF6157'
            driver.screenshot(window,evidence/f'pointer-{name}.png')
        previous=guest()['sharedPointer']
        click(guest,gw,'zoom'); driver.key('Home','Return')
        until(lambda:guest()['viewport']['mode']=='50%' and guest()['sharedPointer']['head']!=previous['head'],
              'Shared pointer did not follow the zoomed app')
        message(guest,gw,'A further note by the same author')
        assert host()['project']['humanPointer']['messageId']==active['messageId']
        for n in range(7):
            text=f'Follow-up {n} '+('Keep the pointer anchored as the conversation scrolls. '*7)
            message(guest,gw,text.strip())
        until(lambda:not host()['sharedPointer']['tail'] and host()['project'].get('humanPointer'),'Offscreen pointer tail was still rendered')
        scroller=target(host,'chat-scroller')
        driver.ipc(f'[con_id={hw}] focus')
        move_over(driver,hw,scroller)
        # Pictures change the distance to the original message. Scroll until
        # its actual attachment point is inside the viewport, then check that
        # the product restores the pointer at that position.
        for _ in range(100):
            state=host()
            y=state['sharedPointer']['messageBounds'][1]+12
            if scroller[1]<=y<scroller[1]+scroller[3]: break
            previous=state['chatScroll']['value']
            driver.seat_command('scroll up' if y<scroller[1] else 'scroll down')
            until(lambda:abs(host()['chatScroll']['value']-previous)>1,'The chat did not scroll toward the pointer')
        else: raise AssertionError('The originating message did not enter the chat viewport')
        until(lambda:host()['sharedPointer']['tail'],'Pointer failed to return when its message scrolled into view')
        message(host,hw,'I have seen the pointer')
        until(lambda:all(not state()['project'].get('humanPointer') and not state()['sharedPointer']['tail']
                         for state in (host,guest)),'The other participant’s reply did not clear the arrow everywhere')
        # The host was deliberately scrolled back to an older message. Return
        # to the end before checking the new pointer on both screens.
        move_over(driver,hw,target(host,'chat-scroller'))
        for _ in range(10):
            driver.scroll()
            scroll=host()['chatScroll']
            if scroll['upper']-scroll['pageSize']-scroll['value']<12: break
        else: raise AssertionError('Host chat could not return to the latest message')
        place_agent_pointer(driver,host,hw,click)
        assert tuple(round(c*255) for c in host()['commentPointer']['color'])==tuple(bytes.fromhex('138EF5'))
        driver.screenshot(hw,evidence/'pointer-host-before-send.png')
        message(host,hw,'The host points here')
        until(lambda:all(state()['sharedPointer']['tail'] and state()['sharedPointer']['color']=='#138EF5'
                         for state in (host,guest)),'Host pointer did not render blue on both machines')
        driver.screenshot(gw,evidence/'pointer-host-blue-as-seen-by-guest.png')
        print('PASS: shared pointer colours, inset anchor, zoom, scroll and reply lifetime',flush=True)

        # A queued conflicting request must stay parked during voting, even if
        # it would otherwise return a valid automatic app update.
        revision=host()['project']['revision']
        start_bytes=(host_root/'projects'/pid/'App.gtk.json').read_bytes()
        proposal=conflict_requests('@centaur Use the Host Choice heading','@centaur Use the Framework Choice heading',1)
        choices=proposal['choices']
        assert len(choices)==2 and host()['project']['queueCount']>=1
        for choice in ('agent','guest','host'):
            target(host,'approval-'+choice)
        conflict_id=proposal['id']
        record=next(m['id'] for m in host()['project']['messages'] if m.get('conflictId')==conflict_id)
        assert host()['chatMessageAppearance'][record]['inConversation']
        click(host,hw,'approval-agent')
        until(lambda:host().get('approvalStatus')=='1 of 2 agreed — waiting for Framework','Host vote did not show the waiting participant')
        driver.screenshot(hw,evidence/'conflict-one-vote.png')
        message(guest,gw,'The conflict card should stay above this newer message')
        assert host()['chatMessageAppearance'][record]['inConversation']
        reopen_guest()
        assert guest()['project']['revision']==revision
        assert (host_root/'projects'/pid/'App.gtk.json').read_bytes()==start_bytes
        click(guest,gw,'approval-host')
        outcome='Neither side could agree, so no changes have been made to the app.'
        def stalemate(state):
            return not state()['project'].get('proposal') and any(
                m['id']==record and m.get('conflictOutcome')==outcome for m in state()['project']['messages'])
        until(lambda:all(stalemate(state) for state in (host,guest)),'Split vote did not close the original chat card')
        for state in (host,guest):
            assert not any(key.startswith('approval-') for key in state()['targets'])
            assert state()['project']['revision']==revision and state()['project']['queueCount']==0
        assert (host_root/'projects'/pid/'App.gtk.json').read_bytes()==start_bytes
        driver.screenshot(gw,evidence/'conflict-stalemate.png')

        conflict_requests('@centaur Use the Host Choice heading again','@centaur Use the Framework Choice heading again',2)
        resolved=json.loads(json.dumps(starter))
        resolved['files']['app.ui']=resolved['files']['app.ui'].replace('Family board','Host Choice')
        reply.write_text(json.dumps({'kind':'proposal','message':'Use the Host Choice heading','conflict':None,'gtk':resolved}))
        click(host,hw,'approval-host')
        until(lambda:host().get('approvalStatus')=='1 of 2 agreed — waiting for Framework','Original choice did not enter voting')
        assert host()['project']['revision']==revision
        click(guest,gw,'approval-host')
        until(lambda:all((state().get('child') or {}).get('title')=='Host Choice' for state in (host,guest)),
              'A new unanimous vote did not apply the chosen original request',timeout=25)
        assert host()['project']['revision']==guest()['project']['revision']==revision+1
        driver.screenshot(gw,evidence/'conflict-agreed.png')

        former=next(p['id'] for p in host()['project']['sharing']['participants'] if p['name']=='Framework')
        projects(guest,gw); click(guest,gw,'menu-'+pid); click(guest,gw,'menu-delete-'+pid); click(guest,gw,'delete-confirm')
        until(lambda:not (guest_root/'shared'/pid/'connection.json').exists(),'Guest did not leave before a new invite')
        invite_and_join(first_invitation)
        remote_image(guest,guest_root,'Matt',shared_host)
        remote_image(host,host_root,guest()['author'],updated)
        assert guest()['drawingColor']=='#FF6157'
        returned=next(p for p in host()['project']['sharing']['participants'] if p['name']==guest()['author'])
        assert returned['id']!=former and former in returned['previousIds']
        assert guest()['author']=='Framework' and returned['displayName']=='Framework'
        assert returned['profileId']==former

        message(guest,gw,'New message after redeeming the second invitation')
        for name,state,window in (('host',host,hw),('guest',guest,gw)):
            for text in ('Host profile image','Guest profile image','New message after redeeming the second invitation'):
                until(lambda:chat_appearance(state,text).get('image'),'Chat rendered initials after fresh join')
                assert chat_appearance(state,text)['own']==((text=='Host profile image')==(name=='host'))
            driver.screenshot(window,evidence/f'rejoined-chat-{name}.png')
            projects(state,window); move_over(driver,window,target(state,'open-'+pid))
            target(state,'collaborators-'+pid)
            assert state()['rosterImages']['collaborators-'+pid]==2,'Fresh join hover roster lost a photograph'
            driver.screenshot(window,evidence/f'rejoined-roster-{name}.png')

        # A deliberately identical visible name must never transfer authorship.
        projects(guest,gw)
        click(guest,gw,'nav-settings')
        until(lambda:guest()['page']=='settings','Guest did not open Settings from Projects')
        click(guest,gw,'settings-name')
        driver.key('ctrl+a'); driver.type('Matt')
        until(lambda:guest()['author']=='Matt' and
              any(p.get('displayName')=='Matt' and p.get('id')==returned['id']
                  for p in control.data['project']['sharing']['participants']),'Guest cannot rename while collaborating')
        projects(guest,gw); click(guest,gw,'open-'+pid); until(lambda:opened(guest),'Renamed guest did not reopen')
        projects(host,hw); click(host,hw,'open-'+pid); until(lambda:opened(host),'Host did not reopen')
        message(guest,gw,'Guest with the same display name')
        for state,own in ((host,False),(guest,True)):
            until(lambda:chat_appearance(state,'Guest with the same display name').get('author')=='Matt',
                  'Chat exposed the internal actor alias')
            assert chat_appearance(state,'Guest with the same display name')['own']==own
            assert chat_appearance(state,'Host profile image')['own']!=own
        projects(guest,gw); click(guest,gw,'menu-'+pid); click(guest,gw,'menu-delete-'+pid); click(guest,gw,'delete-confirm')
        until(lambda:not (guest_root/'shared'/pid/'connection.json').exists(),'Second departure did not finish')
        invite_and_join()
        until(lambda:guest()['author']=='Matt' and chat_appearance(guest,'Guest profile image').get('own'),
              'Repeated rejoin changed the chosen name or lost a proven former author')
        assert chat_appearance(guest,'Guest profile image')['image'] and not chat_appearance(guest,'Host profile image')['own']
        driver.screenshot(gw,evidence/'same-name-rejoin.png')
        from composer_check import check_agent_references
        check_agent_references(driver,click,message,host,hw,guest,gw,alpha,reply,request_record,host_root/'projects'/pid/'App.gtk.json')
    finally:
        control.close()
    return ['host-and-guest-recall-uploaded-image-and-build-after-figma-failure',
            'editable-same-name-profiles-preserve-distinct-authorship-through-repeated-rejoins',
            'used-invitation-dismissal-and-successful-retry','draft-pointers-use-the-assigned-colour',
            'remote-original-sized-and-alpha-avatars-update-and-survive-reconnect-and-rejoin',
            'optimistic-strokes-render-continuously-on-both-profiles-and-keep-participant-colours',
            'human-message-pointer-tracks-scroll-and-zoom-and-clears-on-the-other-participants-reply',
            'inline-conflict-vote-survives-reconnect-closes-on-stalemate-and-applies-a-new-unanimous-choice-once']
