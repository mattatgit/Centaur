"""Fixed two-machine engineering check using isolated GTK clients and Iroh."""
import base64
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit


def run(session):
    from PIL import Image
    import gi
    gi.require_version("Gtk","4.0")
    from gi.repository import GLib,Gtk,Graphene
    from attachment_model import image_filename
    from shell import Centaur
    address=urlsplit(session)
    if address.scheme!='https' or not address.hostname or not ipaddress.ip_address(address.hostname).is_private:
        raise ValueError('Provide a local HTTPS test session.')
    pin=address.fragment
    if not re.fullmatch('[a-f0-9]{64}',pin) or not re.fullmatch('/[a-zA-Z0-9_-]{20,80}',address.path):
        raise ValueError('The test session is incomplete.')
    architecture=platform.machine()
    role={'aarch64':'host','x86_64':'guest'}[architecture]
    revision=os.environ['CENTAUR_GTK4_BUILD_ID']
    def exchange(method, suffix, value=None):
        # The one-use session pins the exact ephemeral certificate.
        ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
        conn=http.client.HTTPSConnection(address.hostname,address.port or 443,context=ctx,timeout=5)
        try:
            conn.connect()
            if hashlib.sha256(conn.sock.getpeercert(binary_form=True)).hexdigest()!=pin:
                raise ValueError('The test session certificate differs.')
            body=None if value is None else json.dumps(value).encode()
            conn.request(method,address.path+'/'+role+'/'+suffix,body=body)
            response=conn.getresponse(); raw=response.read(8192)
            if response.status==404 and method=='GET': return None
            if response.status!=200: raise ValueError('Test session rejected the request.')
            return json.loads(raw)
        finally: conn.close()

    with tempfile.TemporaryDirectory(prefix='centaur-composer-peer-') as folder:
        work=Path(folder); root=work/'profile'
        for variable in ('HOME','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME','XDG_STATE_HOME'):
            target=work/variable.lower(); target.mkdir(mode=0o700)
            os.environ[variable]=str(target)
        os.environ.update(CENTAUR_AGENT='/nonexistent/centaur-peer-test-agent',CENTAUR_AUTHOR='Composer '+role,CENTAUR_PORT='0')
        root.mkdir(mode=0o700)
        peer=Centaur(root)
        done=threading.Event(); failures=[]
        url='https://www.figma.com/design/Fixture123/branch/Branch42/Shared-composer?node-id=17-2'
        def ui(action):
            ready=threading.Event(); result=[]
            def call():
                try: result.append((True,action()))
                except Exception as error: result.append((False,error))
                finally: ready.set()
                return False
            GLib.idle_add(call)
            if not ready.wait(12): raise TimeoutError('The GTK test window stopped responding.')
            ok,value=result[0]
            if not ok: raise value
            return value
        def until(read, seconds=180):
            end=time.monotonic()+seconds
            while time.monotonic()<end and not done.is_set():
                value=read()
                if value: return value
                time.sleep(.4)
            raise TimeoutError('The peer did not finish this test step before its deadline.')
        def post_picture():
            path=work/'test-picture.png'
            Image.new('RGB',(400,240),'#138ef5' if role=='host' else '#ff6157').save(path)
            peer.composer_input.add(peer.project['id'],{'type':'figma','url':url,'name':'Shared composer'})
            peer.composer_input.ingest(path.read_bytes)
            peer.editor.get_buffer().set_text('Picture from the '+role)
        def exchange_complete():
            messages=peer.project.get('messages',[])
            entries={}
            for name in ('host','guest'):
                found=next((m for m in messages if m.get('text')=='Picture from the '+name),None)
                if not found: return None
                refs=found.get('attachments',[])
                if len(refs)!=2 or refs[0].get('url')!=url or found['kind']!='human': raise AssertionError('Reference metadata differs.')
                path=Path(peer.data['sourcePath']).parent/'.centaur'/'attachments'/image_filename(refs[1])
                if not path.is_file(): return None
                digest=hashlib.sha256(path.read_bytes()).hexdigest()
                if digest!=refs[1]['hash']: raise AssertionError('Image bytes differ.')
                entries[name]={'id':found['id'],'author':found['author'],'sha256':digest}
            return entries
        def capture():
            widget=peer.root_overlay
            width,height=widget.get_width(),widget.get_height()
            shot=Gtk.Snapshot.new(); Gtk.WidgetPaintable.new(widget).snapshot(shot,width,height)
            node=shot.to_node()
            if not node: raise ValueError('The disposable window has not been drawn.')
            texture=peer.window.get_renderer().render_texture(node,Graphene.Rect().init(0,0,width,height))
            return base64.b64encode(texture.save_to_png_bytes().get_data()).decode('ascii')
        def check():
            try:
                until(lambda:ui(lambda:peer.data.get('snapshotReady')),35)
                exchange('POST','hello',{'revision':revision,'system':architecture})
                until(lambda:exchange('GET','ready'),900)
                ui(lambda:peer.service.send('author',name='Composer '+role))
                if role=='host':
                    ui(lambda:peer.service.send('create',name='Composer cross-machine test',description=''))
                    until(lambda:ui(lambda:peer.project.get('id')),30)
                    ui(lambda:peer.service.send('invite',address='iroh'))
                    code=until(lambda:ui(lambda:peer.data.get('invitation')),90)
                    exchange('POST','invite',{'invitation':code})
                    ui(lambda:peer.dismiss_dialog(peer.active_form) if peer.active_form else None)
                else:
                    offer=until(lambda:exchange('GET','invite'),480)
                    ui(lambda:peer.service.send('join',name='Composer guest',code=offer['invitation']))
                until(lambda:ui(lambda:len(peer.project.get('sharing',{}).get('participants',[]))>=2 and peer.data.get('connected')),150)
                ui(post_picture)
                until(lambda:ui(lambda:len(peer.composer_input.refs)==2 and peer.send_button.get_sensitive()),30)
                ui(peer.send)
                result=until(lambda:ui(exchange_complete),120)
                exchange('POST','result',{'revision':revision,'system':architecture,'messages':result,'screenshot':ui(capture)})
                until(lambda:exchange('GET','complete'),120)
                print('Both GTK clients verified both images. This disposable session will close.',flush=True)
            except Exception as error:
                failures.append(str(error)); print('Engineering check stopped:',str(error),file=sys.stderr,flush=True)
                try: exchange('POST','failure',{'step':type(error).__name__,'revision':revision})
                except Exception: pass
            finally: GLib.idle_add(lambda:peer.quit() or False)
        worker=threading.Thread(target=check,daemon=True); worker.start()
        try: peer.run([])
        finally:
            done.set(); worker.join(timeout=7)
            subprocess.run([os.environ['CENTAUR_GTK_HOST'],'--stop','--data-dir',str(root)],timeout=6,check=False)
        return 1 if failures else 0
