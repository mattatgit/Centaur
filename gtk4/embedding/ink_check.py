"""Native cross-app-boundary drawing checks in the disposable product display."""
import time
from PIL import Image
from check import until


def check_ink(driver,folder,hs,hw,gs,gw,click,resize_host,project_id):
    def zoom(state,window,index):
        click(state,window,'zoom'); driver.key('Home',*(['Down']*index),'Return')
        mode=('50%','75%','100%','125%','150%','Fit')[index]
        until(lambda:state()['viewport']['mode']==mode,'Ink test zoom did not select '+mode)
        time.sleep(.2)

    def location(state,x,y):
        cx,cy,_,_=state()['targets']['canvas']; v=state()['viewport']
        return (cx+v['app_x']+x*v['app_width']*v['scale'],
                cy+v['app_y']+y*v['app_height']*v['scale'])

    def stroke(state,window,tool,points):
        click(state,window,'tool-'+tool)
        x,y=map(round,location(state,*points[0]))
        moves=[(round(px)-x,round(py)-y) for px,py in (location(state,*p) for p in points[1:])]
        driver.drag_path(window,x,y,moves)

    def blue(state,window,name,point):
        path=folder/(name+'.png'); x,y=map(round,location(state,*point))
        def visible():
            driver.screenshot(window,path)
            with Image.open(path) as image:
                pixels=image.convert('RGB').crop((x-3,y-3,x+4,y+4)).getdata()
                return any(r<90 and g<150 and b>180 for r,g,b in pixels)
        until(visible,'Outside-app ink was not rendered: '+name)

    def synced(count):
        until(lambda:len(hs()['project'].get('annotations',[]))==count and
              hs()['project'].get('annotations')==gs()['project'].get('annotations'),
              'Cross-boundary marks did not synchronise')

    resize_host(1440,944)
    click(hs,hw,'mode-Build')
    for index,mode in enumerate(('50','75','100','125','150','fit')):
        zoom(hs,hw,index)
        stroke(hs,hw,'draw',[(-.08,.35),(.2,.35),(-.08,.4)])
        synced(1)
        mark=hs()['project']['annotations'][0]
        assert mark['points'][0]['x']<mark['frame']['x'] and mark['points'][-1]['x']<mark['frame']['x'],'Stroke was clamped to the app edge'
        assert all(0<=v<=1 for p in mark['points']+[mark['frame']] for v in p.values()),'Ink left the existing wire range'
        blue(hs,hw,'ink-host-'+mode,(-.04,.35))
        blue(gs,gw,'ink-guest-'+mode,(-.04,.35))
        stroke(hs,hw,'comment',[(.15,.55),(-.08,.6)])
        synced(2)
        arrow=hs()['project']['annotations'][1]
        assert len(arrow['points'])==2 and arrow['points'][-1]['x']<arrow['frame']['x'],'Arrow endpoint was clamped'
        blue(hs,hw,'arrow-host-'+mode,(-.08,.6))
        blue(gs,gw,'arrow-guest-'+mode,(-.08,.6))
        click(hs,hw,'undo'); synced(1)
        click(hs,hw,'undo'); synced(0)

    # Persist a mark while navigating, then view it under different transforms.
    zoom(hs,hw,2)
    stroke(hs,hw,'draw',[(-.08,.35),(.2,.35),(-.08,.4)]); synced(1)
    saved=hs()['project']['annotations']
    click(hs,hw,'nav-projects'); click(hs,hw,'open-'+project_id)
    until(lambda:(hs().get('child') or {}).get('ready'),'Ink test project did not reopen')
    assert hs()['project']['annotations']==saved,'Project navigation lost the saved mark'
    resize_host(1200,860)
    blue(hs,hw,'ink-after-resize-and-reopen',(-.04,.35))
    zoom(hs,hw,4)
    before=hs()['viewport']['pan_y']
    cx,cy,cw,ch=hs()['targets']['canvas']
    driver.drag(hw,round(cx+cw/2),round(cy+ch/2),0,40,button=2)
    until(lambda:hs()['viewport']['pan_y']>before+10,'Ink test panning did not move the app')
    # At 150% this narrow canvas clips the app's left edge. An inside segment
    # still verifies that the saved stroke follows panning instead of the window.
    blue(hs,hw,'ink-after-zoom-and-pan',(.1,.35))
    zoom(hs,hw,2)
    blue(hs,hw,'ink-after-zoom-reset',(-.04,.35))

    # A guest's Undo must remove only its own mark, leaving the host's drawing.
    click(gs,gw,'mode-Build')
    stroke(gs,gw,'comment',[(.15,.55),(-.08,.6)]); synced(2)
    assert gs()['project']['annotations'][-1]['author']=='Guest'
    click(gs,gw,'undo'); synced(1)
    assert hs()['project']['annotations']==saved
    click(gs,gw,'mode-Interact'); click(hs,hw,'mode-Interact')
    driver.ipc(f'[con_id={hw}] move position 40 px 60 px')
    # Leave the shared crossing stroke for the following guest agent capture.


def assert_capture(context,geometry):
    x=round(geometry['app_x']-.04*geometry['app_width']*geometry['scale'])
    y=round(geometry['app_y']+.35*geometry['app_height']*geometry['scale'])
    pixels=context.convert('RGB').crop((x-3,y-3,x+4,y+4)).getdata()
    assert any(r<90 and g<150 and b>180 for r,g,b in pixels),'Agent context lost the outside-app drawing'
