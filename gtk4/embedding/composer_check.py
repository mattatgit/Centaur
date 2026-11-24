"""Exercise the actual composer on the two native GTK clients."""
from contextlib import contextmanager
from hashlib import sha256
import subprocess
import time
from check import until


@contextmanager
def clipboard(kind, value):
    mime='image/png' if kind=='image' else 'text/plain;charset=utf-8'
    data=value.read_bytes() if kind=='image' else value.encode('utf-8')
    # wl-copy owns the actual compositor selection. A display connection
    # without a focused Wayland surface cannot claim it with Gdk.Clipboard.
    child=subprocess.Popen(['wl-copy','--foreground','--type',mime],stdin=subprocess.PIPE)
    try:
        child.stdin.write(data); child.stdin.close()
        def available():
            types=subprocess.run(['wl-paste','--list-types'],capture_output=True,text=True,timeout=3)
            return types.returncode==0 and mime in types.stdout.splitlines()
        until(available,'Fixture did not own the Wayland clipboard')
        yield
    finally:
        child.terminate(); child.wait(timeout=4)


def check_composer(driver, evidence, click, host, hw, guest, gw, source, host_root, guest_root):
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
    with clipboard('text',url):
        driver.key('ctrl+v')
        until(lambda:host()['draft']['attachments']==['figma'],'The pasted Figma link did not become a chip')
    with clipboard('image',source):
        driver.key('ctrl+v')
        until(lambda:host()['draft']['attachments']==['figma','image'],'Clipboard image was not attached')
    driver.screenshot(hw,evidence/'composer-mixed.png')
    assert host()['draft']['bytes']==0 and host()['draft']['canSend']
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
    driver.screenshot(gw,evidence/'composer-shared-history.png')
    click(guest,gw,'inspect-image-'+sent['id']+'-0')
    until(lambda:guest()['form']=='Uploaded image','Sent image inspector did not open')
    driver.screenshot(gw,evidence/'composer-inspector.png')
    driver.key('Escape')
    until(lambda:not guest()['form'],'Image inspector did not close')
    click(guest,gw,'editor');driver.type('Guest visual reference')
    with clipboard('image',source):
        driver.key('ctrl+v')
        until(lambda:guest()['draft']['attachments']==['image'],'Guest could not attach image')
    click(guest,gw,'remove-reference-0')
    until(lambda:not guest()['draft']['attachments'],'Could not remove image')
    assert guest()['draft']['sha256']==sha256(b'Guest visual reference').hexdigest()
    click(guest,gw,'attach')
    chooser=until(lambda:next((node for node in driver.nodes() if node.get('name')=='Attach images'
                 and node.get('pid')==guest()['pid']),None),'Native multi-image chooser did not open')
    driver.ipc(f"[con_id={chooser['id']}] focus"); driver.key('ctrl+l'); time.sleep(.25)
    driver.key('ctrl+a'); driver.type(str(source)); driver.key('Return')
    until(lambda:guest()['draft']['attachments']==['image'] and guest()['draft']['canSend'],'Selected image did not load')
    click(guest,gw,'send')
    until(lambda:any(m.get('text')=='Guest visual reference' and len(m.get('attachments',[]))==1
                     for m in host()['project']['messages']),'Host never received the guest’s selected image')
