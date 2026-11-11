"""Native drawing plus temporary composer-connected comment pointers."""
import json
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

    def pointer(state,window,point,name):
        click(state,window,'tool-comment')
        until(lambda:state()['commentPointer']['phase']=='following','Comment did not start following the pointer')
        x,y=map(round,location(state,*point)); rect=driver.rect(window)
        driver.ipc(f"seat seat0 cursor set {rect['x']+x} {rect['y']+y}"); driver.seat_command('motion 0 0')
        until(lambda:state()['commentPointer']['head']==[x,y],'Arrowhead did not follow motion without a button held')
        driver.screenshot(window,folder/(name+'-following.png'))
        driver.click(window,x,y)
        until(lambda:state()['commentPointer']['phase']=='placed' and state()['focus']=='GtkTextView','Placement did not focus comment text input')
        mark=state()['commentPointer']; composer=state()['targets']['composer']
        assert mark['tail']==[composer[0]+12,composer[1]+12],mark
        rect=driver.rect(window)
        driver.ipc(f"seat seat0 cursor set {rect['x']+composer[0]+40} {rect['y']+composer[1]+40}"); driver.seat_command('motion 0 0')
        time.sleep(.15); assert all(abs(a-b)<.01 for a,b in zip(state()['commentPointer']['head'],[x,y])),'A placed head kept following the pointer'
        driver.screenshot(window,folder/(name+'-placed.png'))
        with Image.open(folder/(name+'-placed.png')) as image:
            assert any(r>200 and g<170 and b<170 and r-g>60 for r,g,b in image.convert('RGB').crop((x-4,y-4,x+4,y+4)).getdata()),'Pointer head was not rendered in coral red'
        return mark['reference']

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
        reference=pointer(hs,hw,(-.08,.6),'comment-'+mode)
        synced(1)  # Draft pointers never become permanent shared drawings.
        assert reference['point']['x']<reference['frame']['x'],'Comment head was clamped to the app'
        text=' A comment at '+mode+' '
        driver.type(text); driver.key('Return')
        until(lambda:hs()['commentPointer']['phase']=='idle','Sending did not remove the temporary arrow')
        until(lambda:any(m.get('text')==text.strip() and m.get('comment')==reference for m in gs()['project']['messages']),'Comment location did not reach the guest with its message')
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
    stroke(gs,gw,'draw',[(.15,.55),(-.08,.6)]); synced(2)
    assert gs()['project']['annotations'][-1]['author']=='Guest'
    click(gs,gw,'undo'); synced(1)
    assert hs()['project']['annotations']==saved
    click(gs,gw,'mode-Interact'); click(hs,hw,'mode-Interact')
    driver.ipc(f'[con_id={hw}] move position 40 px 60 px')
    # Leave the shared crossing stroke for the following guest agent capture.


def place_agent_pointer(driver,state,window,click):
    click(state,window,'mode-Build'); click(state,window,'tool-comment')
    cx,cy,cw,ch=state()['targets']['canvas']; view=state()['viewport']
    x=round(cx+view['app_x']+.35*view['app_width']*view['scale'])
    y=round(cy+view['app_y']+.45*view['app_height']*view['scale'])
    rect=driver.rect(window); driver.ipc(f"seat seat0 cursor set {rect['x']+x} {rect['y']+y}"); driver.seat_command('motion 0 0')
    until(lambda:state()['commentPointer']['head']==[x,y],'Guest arrow did not follow')
    driver.click(window,x,y)
    until(lambda:state()['commentPointer']['phase']=='placed' and state()['focus']=='GtkTextView','Guest placement did not focus its input')
    return x-cx,y-cy,state()['commentPointer']['reference']


def assert_capture(context,geometry):
    x=round(geometry['app_x']-.04*geometry['app_width']*geometry['scale'])
    y=round(geometry['app_y']+.35*geometry['app_height']*geometry['scale'])
    pixels=context.convert('RGB').crop((x-3,y-3,x+4,y+4)).getdata()
    assert any(r<90 and g<150 and b>180 for r,g,b in pixels),'Agent context lost the outside-app drawing'
