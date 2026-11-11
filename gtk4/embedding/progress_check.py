"""CI: a throttled, genuinely signed NAR transfer displayed by both updater controls."""
import http.server
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from types import SimpleNamespace
import gi

gi.require_version('Gtk','4.0')
gi.require_version('Gdk','4.0')
from gi.repository import Gdk,Gio,GLib,Gtk
from check import read,until
from download_progress import DownloadProgress,download_plan
from ui import box,margins,label
from update_ui import UpdateControls
from updater import Runtime,Transaction,CACHE,KEY,NIX_FLAGS


def check_progress(driver,folder,path,info):
    folder.mkdir()
    # Nix has already fetched and signature-verified this real cache object.
    # Export its canonical NAR instead of making a second Python HTTP request
    # that may be rejected by a cache's user-agent/CDN policy.
    with (folder/'payload.nar').open('wb') as output:
        subprocess.run(['nix',*NIX_FLAGS,'nar','dump-path',path],stdout=output,check=True,timeout=20)
    payload=(folder/'payload.nar').read_bytes()
    assert len(payload)==info['narSize'] and info['signatures']
    narinfo='\n'.join(['StorePath: '+path,'URL: nar/progress.nar','Compression: none',
                       'FileHash: '+info['narHash'],'FileSize: '+str(len(payload)),
                       'NarHash: '+info['narHash'],'NarSize: '+str(len(payload)),
                       'References: '+ ' '.join(Path(p).name for p in info['references']),
                       *['Sig: '+signature for signature in info['signatures']],
                       *(['CA: '+info['ca']] if info.get('ca') else [])])+'\n'
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_HEAD(self): self.serve(False)
        def do_GET(self): self.serve(True)
        def serve(self,body):
            data={'/nix-cache-info':b'StoreDir: /nix/store\nWantMassQuery: 0\nPriority: 40\n',
                  '/'+Path(path).name.split('-',1)[0]+'.narinfo':narinfo.encode(),
                  '/nar/progress.nar':payload}.get(self.path)
            if data is None: self.send_error(404); return
            self.send_response(200); self.send_header('Content-Length',str(len(data))); self.end_headers()
            if body:
                try:
                    chunk=max(16384,len(data)//16) if self.path=='/nar/progress.nar' else len(data)
                    for offset in range(0,len(data),chunk):
                        self.wfile.write(data[offset:offset+chunk]); self.wfile.flush()
                        if self.path=='/nar/progress.nar': time.sleep(.12)
                except (BrokenPipeError,ConnectionResetError): pass
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    serving=threading.Thread(target=server.serve_forever,daemon=True); serving.start()
    cache='http://127.0.0.1:'+str(server.server_port)
    # This loopback cache serves unchanged signed bytes and original signatures.
    # Only the unsigned download-location field is redirected for throttling.
    plan=download_plan(cache,{path:dict(info,url='nar/progress.nar',downloadSize=len(payload))},{})
    runtime=Runtime(folder); transaction=Transaction(folder,runtime)
    tracker=DownloadProgress(cache,plan,transaction.download_progress)
    args=['nix',*NIX_FLAGS,'--log-format','internal-json','copy','--from',cache,'--to',str(folder/'empty-store'),
          '--extra-trusted-public-keys',KEY,path]
    errors=[]
    def copy():
        try: runtime.copy_with_progress(args,tracker,timeout=30)
        except Exception as error: errors.append(error)
    worker=threading.Thread(target=copy,daemon=True)
    Gtk.init()
    app=Gtk.Application(application_id='org.centaur.Gtk4',flags=Gio.ApplicationFlags.NON_UNIQUE); app.register()
    window=Gtk.ApplicationWindow(application=app,title='Centaur update progress check',default_width=704,default_height=240,decorated=False)
    provider=Gtk.CssProvider(); provider.load_from_path(str(Path(__file__).with_name('shell.css')))
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    root=margins(box(True,24),24); section=box(True,16); section.append(label('App','section-title')); root.append(section)
    footer=box(spacing=8); root.append(footer); window.set_child(root)
    owner=SimpleNamespace(update_session=None,version=lambda:'0.4.0-preview+progress',targets={},
                          update_footer=footer,closing=False,window=window)
    controls=UpdateControls(owner,section); controls.work=folder; controls.next_check=float('inf'); controls.set_sensitive(False)
    window.present(); context=GLib.MainContext.default()
    def pump():
        while context.pending(): context.iteration(False)
        return window.get_mapped()
    samples=[]; captured=False
    try:
        until(pump,'Progress fixture did not map')
        handle=until(lambda:next((n['id'] for n in driver.nodes() if n.get('app_id')=='org.centaur.Gtk4' and n.get('pid')==os.getpid()),None),'Progress fixture has no native window')
        worker.start(); deadline=time.monotonic()+35
        while time.monotonic()<deadline:
            pump(); controls.tick(); value=read(folder/'status.json')
            message=controls.status.get_text()
            assert message==controls.footer_status.get_text(),'Settings/footer progress diverged'
            assert controls.footer_labels.get_visible_child().get_text()=='Updating…','Byte progress hid Updating caption'
            if not samples or message!=samples[-1]['message']:
                samples.append({'bytes':value.get('downloadBytes',0),'total':value.get('totalBytes'),
                                'message':message,'copyRunning':worker.is_alive()})
            partial=[s for s in samples if 0<s['bytes']<len(payload) and s['copyRunning']]
            if len(partial)>=2 and not captured:
                driver.screenshot(handle,folder/'live-counter.png'); captured=True
            if not worker.is_alive(): break
            time.sleep(.04)
        worker.join(timeout=2)
        assert not worker.is_alive(),'Controlled download did not finish'
        if errors: raise errors[0]
        assert len({s['message'] for s in samples if 0<s['bytes']<len(payload) and s['copyRunning']})>=2,samples
        assert samples[-1]['bytes']==len(payload),samples
        transaction.status('verifying','Download complete. Verifying the update…'); controls.tick(); pump()
        assert controls.status.get_text().endswith(' · Verifying…') and 'Downloaded ' in controls.footer_status.get_text()
        assert controls.footer_labels.get_visible_child().get_text()=='Updating…'
        (folder/'visible-progress.json').write_text(json.dumps(samples,indent=2))
    finally:
        window.destroy(); pump(); server.shutdown(); server.server_close(); serving.join(timeout=2)

