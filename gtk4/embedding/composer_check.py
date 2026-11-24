"""Exercise the actual composer on the two native GTK clients."""
from contextlib import contextmanager
from hashlib import sha256
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
            driver.ipc(f'[con_id={fixture}] floating enable, resize set 152 72, move position 620 180')
            until(lambda:driver.rect(fixture)['width']==152,'Reference window did not settle')
            yield fixture
        finally:
            helper.terminate(); helper.wait(timeout=4)


@contextmanager
def clipboard(driver,kind,value):
    mime='image/png' if kind=='image' else 'text/plain;charset=utf-8'
    data=value.read_bytes() if kind=='image' else value.encode()
    with reference_source(driver,kind,value) as fixture:
        driver.click(fixture,50,32)
        def owns_selection():
            result=subprocess.run(['wl-paste','--no-newline','--type',mime],capture_output=True,timeout=3)
            return result.returncode==0 and result.stdout==data
        until(owns_selection,'The external window did not copy the requested bytes')
        yield


def drop_files(driver, state, window, paths):
    from check import target
    with reference_source(driver,'drop',*paths) as fixture:
        rect=driver.rect(fixture); receiver=driver.rect(window)
        x,y,w,h=target(state,'composer')
        dx=round(receiver['x']+x+w/2-rect['x']-36)
        dy=round(receiver['y']+y+h/2-rect['y']-30)
        driver.drag_path(fixture,36,30,[(18,0),(dx,dy),(dx+1,dy)])
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
    driver.ipc(f"[con_id={chooser['id']}] focus"); driver.key('ctrl+l'); time.sleep(.25)
    driver.key('ctrl+a'); driver.type(str(source))
    driver.screenshot(chooser['id'],evidence/'composer-image-picker.png',focus=False)
    driver.key('Return')
    # The multiple-file dialog may select the named file on Return and wait
    # for an explicit Open. Click its actual native action when it is still up.
    def selection():
        if guest()['draft']['attachments']: return 'loaded'
        native=guest().get('imageChooser')
        if native and native['selected'] and native['canAccept']: return native
    try: selected=until(selection,'Native chooser did not select the named image')
    except AssertionError:
        if any(node['id']==chooser['id'] for node in driver.nodes()):
            driver.screenshot(chooser['id'],evidence/'composer-picker-after-return.png',focus=False)
        raise
    if selected!='loaded':
        rect=driver.rect(chooser['id'])
        x,y=selected['button']
        driver.click(chooser['id'],round(x+(rect['width']-selected['width'])/2),
                     round(y+(rect['height']-selected['height'])/2))
    until(lambda:guest()['draft']['attachments']==['image'] and guest()['draft']['canSend'],'Selected image did not load')
    click(guest,gw,'send')
    until(lambda:any(m.get('text')=='Guest visual reference' and len(m.get('attachments',[]))==1
                     for m in host()['project']['messages']),'Host never received the guest’s selected image')
    from PIL import Image
    second=evidence/'drop-input.jpg'
    Image.new('RGB',(320,180),'#138ef5').save(second)
    drop_files(driver,guest,gw,[source,second])
    until(lambda:guest()['draft']['attachments']==['image','image'] and guest()['draft']['canSend'],
          'Dropped files did not become two composer images')
    driver.screenshot(gw,evidence/'composer-dropped-images.png')
    click(guest,gw,'remove-reference-1'); click(guest,gw,'remove-reference-0')
