"""Exercise the actual composer on the two native GTK clients."""
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import time
from check import until


@contextmanager
def reference_source(driver,kind,*values):
    program=Path(__file__).with_name('composer_fixture.py')
    with subprocess.Popen([sys.executable,str(program),kind,*map(str,values)]) as helper:
        try:
            node=until(lambda:next((node for node in driver.nodes() if node.get('pid')==helper.pid
                           and node.get('name')=='Composer reference source'),None),'External reference window did not appear')
            fixture=node['id']
            last=None; since=0
            def placed():
                nonlocal last,since
                rect=driver.rect(fixture)
                if rect!=last: last=rect; since=time.monotonic()
                return rect['width']>0 and rect['height']>0 and time.monotonic()-since>=.2
            until(placed,'Reference window did not settle')
            yield fixture
        finally:
            helper.terminate(); helper.wait(timeout=4)


@contextmanager
def clipboard(driver,kind,value):
    mime='image/png' if kind=='image' else 'text/plain;charset=utf-8'
    data=value.read_bytes() if kind=='image' else value.encode()
    with reference_source(driver,kind,value) as fixture:
        def owns_selection():
            # Wayland grants ownership using the focused source's input
            # serial. Renew that serial if the initial window map raced the
            # click. The check still requires the exact bytes from wl-paste.
            rect=driver.rect(fixture)
            driver.click(fixture,rect['width']//2,rect['height']//2)
            result=subprocess.run(['wl-paste','--no-newline','--type',mime],capture_output=True,timeout=3)
            return result.returncode==0 and result.stdout==data
        until(owns_selection,'The external window did not copy the requested bytes')
        yield


def drop_files(driver, state, window, paths):
    from check import target
    with reference_source(driver,'drop',*paths) as fixture:
        rect=driver.rect(fixture); receiver=driver.rect(window)
        x,y,w,h=target(state,'composer')
        start_x,start_y=rect['width']//2,rect['height']//2
        dx=round(receiver['x']+x+w/2-rect['x']-start_x)
        dy=round(receiver['y']+y+h/2-rect['y']-start_y)
        driver.drag_path(fixture,start_x,start_y,[(18,0),(dx,dy),(dx+1,dy)])
        until(lambda:len(state()['draft']['attachments'])==len(paths),
              'The composer did not receive the file drop')


def check_composer(driver, evidence, click, host, hw, guest, gw, source, host_root, guest_root):
    from check import target
    from workspace_polish_check import move_over
    pid=host()['project']['id']
    name=host()['project']['agentName']
    click(host,hw,'editor')
    driver.type('@'+name[0].upper())
    until(lambda:host()['draft']['suggestion'].casefold()==name[1:].casefold(),'Inline mention did not appear')
    driver.key('Escape')
    until(lambda:not host()['draft']['suggestion'] and host()['draft']['bytes']==2,'Escape edited the mention')
    driver.key('BackSpace');driver.type(name[0])
    driver.key('Tab')
    until(lambda:host()['draft']['bytes']==len(('@'+name+' ').encode()),'Tab did not accept the mention')
    driver.key('ctrl+a','BackSpace')
    url='https://www.figma.com/design/Fixture123/branch/Branch42/Shared-composer?node-id=17-2'
    with clipboard(driver,'text',url):
        click(host,hw,'editor'); driver.key('ctrl+v')
        until(lambda:host()['draft']['attachments']==['figma'],'The pasted Figma link did not become a chip')
    with clipboard(driver,'image',source):
        click(host,hw,'editor'); driver.key('ctrl+v')
        until(lambda:host()['draft']['attachments']==['figma','image'],'Clipboard image was not attached')
    driver.screenshot(hw,evidence/'composer-mixed.png')
    assert host()['draft']['bytes']==0 and host()['draft']['canSend']
    click(host,hw,'editor')
    for _ in range(12):
        previous=host()['focusSequence']
        driver.key('Tab')
        until(lambda:host()['focusSequence']>previous,'Native keyboard focus did not move')
        if 'attach' in host()['focusedTargets']: break
    assert 'attach' in host()['focusedTargets'],'The attach button was unreachable by keyboard'
    driver.screenshot(hw,evidence/'composer-keyboard-focus.png')
    move_over(driver,hw,target(host,'remove-reference-1'))
    driver.screenshot(hw,evidence/'composer-remove-hover.png')
    old_size=host()['windowSize']
    driver.resize(hw,376,old_size[1])
    until(lambda:host()['layout']['chatWidth']<400 and host()['draft']['canSend'],'Narrow composer did not settle')
    driver.screenshot(hw,evidence/'composer-narrow.png')
    driver.resize(hw,*old_size)
    until(lambda:host()['windowSize']==old_size,'Could not restore the workspace after the narrow check')
    click(host,hw,'send')
    def received(state):
        return next((m for m in reversed(state()['project']['messages']) if len(m.get('attachments',[]))==2 and
                     m['attachments'][0].get('url')==url),None)
    sent=until(lambda:received(guest),'Guest never received the mixed attachment-only message')
    assert not sent['text'] and sent['kind']=='human'
    ref=sent['attachments'][1]
    filename=ref['hash']+'.'+ref['format']
    for directory in [host_root/'projects',guest_root/'shared']:
        path=directory/pid/'.centaur'/'attachments'/filename
        until(lambda:path.is_file() and sha256(path.read_bytes()).hexdigest()==ref['hash'],'Image content failed verification')
    until(lambda:not host()['draft']['attachments'],'Confirmed message stayed in composer')
    image_control='inspect-image-'+sent['id']+'-0'
    image_box=target(guest,image_control)
    assert 1<=image_box[2]<=232 and 1<=image_box[3]<=232, image_box
    driver.screenshot(gw,evidence/'composer-shared-history.png')
    click(guest,gw,image_control)
    until(lambda:guest()['form']=='Uploaded image','Sent image inspector did not open')
    driver.screenshot(gw,evidence/'composer-inspector.png')
    driver.key('Escape')
    until(lambda:not guest()['form'],'Image inspector did not close')
    click(guest,gw,'editor');driver.type('Guest visual reference')
    with clipboard(driver,'image',source):
        click(guest,gw,'editor'); driver.key('ctrl+v')
        until(lambda:guest()['draft']['attachments']==['image'],'Guest could not attach image')
    click(guest,gw,'remove-reference-0')
    until(lambda:not guest()['draft']['attachments'],'Could not remove image')
    assert guest()['draft']['sha256']==sha256(b'Guest visual reference').hexdigest()
    click(guest,gw,'attach')
    chooser=until(lambda:next((node for node in driver.nodes() if node.get('name')=='Attach images'
                 and node.get('pid')==guest()['pid']),None),'Native multi-image chooser did not open')
    # The earlier Settings flow opened this actual file, so it is listed
    # in GTK's Recent view. Select its rendered row in the multi-file chooser.
    # A typed location is a separate mode and is not a selected file row.
    recent=source.with_name('avatar-photograph.png')
    name_hash=sha256(recent.name.encode()).hexdigest()
    def chooser_click(native,point):
        rect=driver.rect(chooser['id'])
        x,y=point
        driver.click(chooser['id'],round(x+(rect['width']-native['width'])/2),
                     round(y+(rect['height']-native['height'])/2))
    def recent_visible():
        native=guest().get('imageChooser')
        return native if native and name_hash in native['rows'] else None
    native=until(recent_visible,'Recent test image did not appear in the chooser')
    chooser_click(native,native['rows'][name_hash])
    native=until(lambda:v if (v:=guest().get('imageChooser')) and v['selected']==1 and v['canAccept'] else None,
                 'The native file chooser did not select the image')
    driver.screenshot(chooser['id'],evidence/'composer-image-picker.png',focus=False)
    driver.key('Return')
    time.sleep(.35)
    native=guest().get('imageChooser')
    if native and native['selected'] and native['canAccept'] and any(n['id']==chooser['id'] for n in driver.nodes()):
        chooser_click(native,native['button'])
    try:
        until(lambda:guest()['draft']['attachments']==['image'] and guest()['draft']['canSend'],
              'The selected native image did not load')
    except AssertionError:
        if any(n['id']==chooser['id'] for n in driver.nodes()):
            driver.screenshot(chooser['id'],evidence/'composer-picker-after-open.png',focus=False)
        raise
    click(guest,gw,'send')
    until(lambda:any(m.get('text')=='Guest visual reference' and len(m.get('attachments',[]))==1
                     for m in host()['project']['messages']),'Host never received the guest’s selected image')
    from attachment_model import prepare_image
    picked=prepare_image(recent.read_bytes())[0]
    assert any(m.get('text')=='Guest visual reference' and m.get('attachments')==[picked]
               for m in host()['project']['messages']),'The chosen file did not reach the other participant'
    from PIL import Image
    second=evidence/'drop-input.jpg'
    Image.new('RGB',(320,180),'#138ef5').save(second)
    drop_files(driver,guest,gw,[source,second])
    until(lambda:guest()['draft']['attachments']==['image','image'] and guest()['draft']['canSend'],
          'Dropped files did not become two composer images')
    for index in range(2):
        bounds=target(guest,'draft-reference-'+str(index))
        assert tuple(map(round,bounds[2:]))==(72,72),bounds
    driver.screenshot(gw,evidence/'composer-dropped-images.png')
    click(guest,gw,'remove-reference-1'); click(guest,gw,'remove-reference-0')


def check_agent_references(driver,click,message,host,hw,guest,gw,source,reply,record,app):
    """Exercise the host coordinator and the actual inputs delivered to its provider."""
    from attachment_model import prepare_image
    from PIL import Image
    url='https://www.figma.com/design/Fixture123/Centaur?node-id=7-8'

    def attach(state,window,kind,value):
        before=len(state()['draft']['attachments'])
        with clipboard(driver,kind,value):
            click(state,window,'editor'); driver.key('ctrl+v')
            until(lambda:len(state()['draft']['attachments'])==before+1,'Reference did not attach')

    def ask(state,window,text,answer):
        text='@centaur '+text
        reply.write_text(json.dumps(answer))
        before={m['id'] for m in host()['project']['messages']}
        message(state,window,text)
        def answered():
            for row in host()['project']['messages']:
                if row['id'] in before: continue
                if row.get('agentDiagnostics'): raise AssertionError(text+' failed: '+row['text'])
                if row.get('kind')=='agent' and row['text']==answer['message']: return True
        until(answered,'The provider did not answer '+text,timeout=30)
        payload=json.loads(record.read_text().split('PROJECT AND CONVERSATION:\n',1)[1].split('\n\nCURRENT ',1)[0])
        assert payload['requestText']==text and payload['canvasAttached']
        return payload,json.loads(record.with_suffix('.images.json').read_text())

    attach(host,hw,'image',source); attach(host,hw,'text',url)
    click(host,hw,'send')
    until(lambda:any(not m['text'] and any(r.get('url')==url for r in m.get('attachments',[]))
                     for m in guest()['project']['messages']),'Guest did not receive the mixed reference')
    distinct=reply.parent/'agent-reference-blue.png'
    Image.new('RGB',(40,28),'#0157ab').save(distinct)
    expected=prepare_image(distinct.read_bytes())[0]['hash']
    attach(guest,gw,'image',distinct)
    question={'kind':'question','message':'Image and canvas received'}
    explicit,pixels=ask(guest,gw,'Describe the attached image and the current app heading.',question)
    original=explicit['referenceMessage']
    assert len(pixels)==2 and pixels[1]==expected and explicit['visualReferences'][0]['hash']==expected

    # The disposable host has no private reader. An explicitly requested
    # design must fail visibly and leave the saved app byte-for-byte intact.
    saved=app.read_bytes()
    attach(host,hw,'text',url)
    message(host,hw,'@centaur Read the attached Figma frame.')
    until(lambda:any(m.get('agentDiagnostics',{}).get('code')=='figma_unavailable'
                     for m in host()['project']['messages']),'Explicit Figma failure was not reported')
    assert app.read_bytes()==saved

    for role,state,window in [('Guest',guest,gw),('Host',host,hw)]:
        for request in ('Describe the previously uploaded image.',
                        'I meant the previous image, not the Figma link.'):
            payload,pixels=ask(state,window,request,question)
            assert payload['referenceMessage']==original and [r['hash'] for r in payload['visualReferences']]==[expected]
            assert len(pixels)==2 and pixels[1]==expected
        bundle=json.loads(app.read_text())
        old=host()['child']['title']; new=role+' context verified'
        assert old in bundle['files']['app.ui']
        bundle['files']['app.ui']=bundle['files']['app.ui'].replace(old,new)
        answer={'kind':'proposal','message':'Set the heading for '+role,'conflict':None,'gtk':bundle}
        payload,pixels=ask(state,window,'Change the app heading to '+new+'.',answer)
        assert not payload['visualReferences'] and len(pixels)==1
        until(lambda:all((s().get('child') or {}).get('title')==new for s in (host,guest)),
              'The heading edit did not reach both embedded apps',timeout=25)
