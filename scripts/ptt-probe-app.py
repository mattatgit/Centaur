"""Private native probe of an unmodified generated app; no handler invocation."""
import os,sys,json,hashlib,signal,time
from pathlib import Path
sys.path.insert(0,os.environ['CENTAUR_GTK_PACKAGE']+'/share/centaur-gtk4-test')
import gi
gi.require_version('Gtk','4.0');gi.require_version('Gdk','4.0')
from gi.repository import Gtk,Gdk,Gio,GLib
from bundle import load_bundle
calls=[];started=time.monotonic()
def profile(frame,event,arg):
 if event=='call' and frame.f_code.co_filename=='app.py' and frame.f_code.co_name in ('render_ptt','reset_ptt','pointer_pressed','pointer_released') and len(calls)<80:
  calls.append({'seconds':round(time.monotonic()-started,3),'function':frame.f_code.co_name,'held':bool(frame.f_locals.get('held_inputs')),'argumentCount':len(frame.f_locals.get('_args',()))})
if os.environ.get('CENTAUR_PTT_TRACE')=='1':sys.setprofile(profile)
bundle=load_bundle(sys.argv[1]);report=Path(sys.argv[2]);app=Gtk.Application(application_id='org.centaur.PttVerification',flags=Gio.ApplicationFlags.NON_UNIQUE)
def activate(application):
 provider=Gtk.CssProvider();provider.load_from_data(bundle['files']['style.css'].encode());Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
 builder=Gtk.Builder.new_from_string(bundle['files']['app.ui'],-1);namespace={'__name__':'centaur_generated_app','__file__':'app.py'};exec(compile(bundle['files']['app.py'],'app.py','exec'),namespace)
 window=namespace['create_window'](builder);window.set_decorated(False);window.set_default_size(bundle['width'],bundle['height']);window.set_application(application)
 button=builder.get_object(sys.argv[3]);assert isinstance(button,Gtk.Button)
 pointer={'nativePointer':None,'nativePointerSerial':0};motion=Gtk.EventControllerMotion()
 def moved(controller,x,y):pointer['nativePointer']=[x,y];pointer['nativePointerSerial']+=1
 motion.connect('motion',moved);window.add_controller(motion)
 def emit():
  ok,rect=button.compute_bounds(window);images=[]
  def walk(node):
   if isinstance(node,Gtk.Image):
    paint=node.get_paintable();d={'type':type(paint).__name__ if paint else None,'themeIcon':bool(node.get_icon_name())}
    if isinstance(paint,Gdk.Texture):d['textureSha256']=hashlib.sha256(paint.save_to_png_bytes().get_data()).hexdigest()
    images.append(d)
   child=node.get_first_child()
   while child:walk(child);child=child.get_next_sibling()
  walk(button)
  value={'pid':os.getpid(),'windowSize':[window.get_width(),window.get_height()],'target':[rect.get_x(),rect.get_y(),rect.get_width(),rect.get_height()] if ok else None,'classes':button.get_css_classes(),'images':images,'active':window.is_active(),'calls':calls.copy(),**pointer}
  temp=report.with_suffix('.pending');temp.write_text(json.dumps(value));temp.replace(report);return True
 GLib.timeout_add(50,emit);window.present()
app.connect('activate',activate);GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,signal.SIGTERM,lambda:(app.quit(),False)[1]);app.run([])
