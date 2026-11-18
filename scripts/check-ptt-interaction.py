from pathlib import Path
import json,os,sys,subprocess,time,hashlib,ast,base64,shlex,argparse,platform
from PIL import Image

def main():
    parser=argparse.ArgumentParser(description='Native PTT hold/release and original-artwork verification in a private test compositor.')
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--artwork',type=Path,required=True)
    parser.add_argument('--product',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--widget',default='ptt')
    args=parser.parse_args()
    assert platform.machine()=='aarch64' and 'ID=nixos' in Path('/etc/os-release').read_text()
    assert os.environ.get('WLR_BACKENDS')=='headless' and os.environ.get('CENTAUR_GTK4_TEST_BACKEND')=='wayland'
    source=args.bundle.resolve();folder=args.output.resolve();product=args.product.resolve()
    assert source.is_relative_to(Path('/tmp').resolve()) and folder.is_relative_to(Path('/tmp').resolve())
    os.umask(0o077);folder.mkdir(parents=True,mode=0o700)
    sys.path.insert(0,str(product/'share/centaur-gtk4-test'))
    from check import read,until
    from test_driver import Driver
    bundle=json.loads(source.read_text());original_data=[args.artwork.read_bytes()]
    original={hashlib.sha256(v).hexdigest() for v in original_data}
    embedded=[];content_reused=False
    for n in ast.walk(ast.parse(bundle['files']['app.py'])):
     if not isinstance(n,ast.Constant) or not isinstance(n.value,(str,bytes)):continue
     raw=n.value.encode() if isinstance(n.value,str) else n.value
     if hashlib.sha256(raw).hexdigest() in original:embedded.append('literal')
     if any(raw.strip()==v.strip() for v in original_data):content_reused=True
     try:decoded=base64.b64decode(b''.join(raw.split()),validate=True)
     except ValueError:continue
     if hashlib.sha256(decoded).hexdigest() in original:embedded.append('base64');content_reused=True
    raw=(product/'bin/centaur-gtk4').read_bytes();start=raw.find(b"makeCWrapper '");assert start>=0
    flags=shlex.split(raw[start:].split(b'\0',1)[0].decode().replace('\\\n',''),comments=True);wrapped_env=dict(os.environ);i=2
    while i<len(flags):
     flag=flags[i];i+=1
     if flag in ('--set','--set-default'):
      key,value=flags[i:i+2];i+=2
      if flag=='--set':wrapped_env[key]=value
      else:wrapped_env.setdefault(key,value)
     elif flag in ('--prefix','--suffix'):
      key,sep,value=flags[i:i+3];i+=3;old=wrapped_env.get(key,'')
      wrapped_env[key]=value+sep+old if flag=='--prefix' and old else old+sep+value if flag=='--suffix' and old else value
     elif flag=='--unset':wrapped_env.pop(flags[i],None);i+=1
     elif flag=='--inherit-argv0':pass
     else:raise AssertionError('Unsupported native wrapper metadata option '+flag)
    for kind in ('CONFIG','DATA','CACHE','STATE'):
     path=folder/('desktop-'+kind.lower());path.mkdir();os.environ['XDG_'+kind+'_HOME']=str(path)
    home=folder/'home';home.mkdir();env=dict(wrapped_env,HOME=str(home),GSETTINGS_BACKEND='memory');env.update({k:v for k,v in os.environ.items() if k.startswith('XDG_') and k.endswith('_HOME')})
    report=folder/'native.json';process=subprocess.Popen([sys.executable,str(Path(__file__).with_name('ptt-probe-app.py')),str(source),str(report),args.widget],env=env,cwd=home,stderr=subprocess.DEVNULL)
    state=lambda:read(report);driver=Driver();summary={'originalMicOnBytesEmbedded':bool(embedded),'originalMicOnContentReused':content_reused,'ownerProfileActivated':False}
    try:
     until(lambda:state().get('target'),'PTT app did not map')
     window=driver.find_window('org.centaur.PttVerification',process.pid);driver.ipc(f'[con_id={window}] floating enable, border none, move position 40 px 40 px')
     driver.track_native(window,state);time.sleep(.25)
     def photo(name):
      p=folder/(name+'.png');driver.screenshot(window,p);s=state();x,y,w,h=map(round,s['target']);im=Image.open(p).convert('RGB');crop=im.crop((x,y,x+w,y+h));crop.save(folder/(name+'-button.png'))
      pixels=list(crop.get_flattened_data());red=sum(r>140 and r>g*1.4 and r>b*1.1 for r,g,b in pixels);green=sum(g>80 and g>r*1.2 and g>b*1.05 for r,g,b in pixels)
      return {'redPixels':red,'greenPixels':green,'images':s['images'],'classes':s['classes']}
     before=photo('ptt-idle');x,y,w,h=state()['target'];r=driver.rect(window)
     driver.ipc(f"seat seat0 cursor set {round(r['x']+x+w/2)} {round(r['y']+y+h/2)}");driver.seat_command('motion 0 0');time.sleep(.2)
     driver.seat_command('left press');time.sleep(.4);held=photo('ptt-held');time.sleep(.8);still=photo('ptt-still-held')
     driver.seat_command('left release');time.sleep(.3);released=photo('ptt-released')
     driver.seat_command('left press');time.sleep(.2);driver.seat_command('motion 150 -150');driver.seat_command('left release');time.sleep(.3);outside=photo('ptt-release-outside')
     summary.update(idle=before,held=held,stillHeld=still,released=released,outside=outside)
     assert before['redPixels']>100 and held['greenPixels']>100 and still['greenPixels']>100,summary
     assert released['redPixels']>100 and outside['redPixels']>100,summary
     assert held['images']!=before['images'],'Held microphone image did not change'
     assert content_reused,'The original repository mic_on SVG content was not reused'
     summary['passed']=True
    finally:
     driver.seat_command('left release');process.terminate();process.wait(timeout=6)
     (folder/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('NATIVE_PTT_CHECK='+json.dumps(summary),flush=True)


if __name__ == "__main__":
    main()
