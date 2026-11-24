"""Exercise the actual composer on the two native GTK clients."""
from contextlib import contextmanager
from hashlib import sha256
import subprocess
import sys
import time
from check import until


@contextmanager
def clipboard(kind, value):
    # A real Wayland selection owner. Its event loop serves the receiving
    # process even while the native-input driver is waiting for a frame.
    code = """
import sys, gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,Gdk,GLib
Gtk.init()
clip=Gdk.Display.get_default().get_clipboard()
value=Gdk.Texture.new_from_filename(sys.argv[2]) if sys.argv[1]=='image' else sys.argv[2]
clip.set_content(Gdk.ContentProvider.new_for_value(value))
Gdk.Display.get_default().flush()
print('ready',flush=True)
GLib.MainLoop().run()
"""
    with subprocess.Popen([sys.executable,'-c',code,kind,str(value)],stdout=subprocess.PIPE,text=True) as child:
        try:
            if child.stdout.readline().strip()!='ready': raise AssertionError('Clipboard setup failed')
            yield
        finally: child.terminate(); child.wait(timeout=5)


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
