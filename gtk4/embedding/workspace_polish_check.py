"""Native navigation, mode control and authenticated project roster checks."""
from contextlib import contextmanager
import json
import os
import signal
import subprocess
import time
from PIL import Image
from check import target, until


@contextmanager
def record_motion(driver, window, path, crop=None):
    if os.environ.get('CENTAUR_GTK4_RECORD_MOTION') != '1':
        yield
        return
    assert driver.wayland, 'Motion recordings require the disposable Wayland session'
    driver.ipc(f'[con_id={window}] focus')
    rect=driver.rect(window)
    x,y,w,h=crop or (0,0,rect['width'],rect['height'])
    region=f"{rect['x']+x},{rect['y']+y} {w}x{h}"
    args=['wf-recorder','--no-dmabuf','-D','-g',region,'-c','libx264','-p','preset=ultrafast',
          '-p','crf=16','-x','yuv420p','-f',str(path)]
    with subprocess.Popen(args,stdin=subprocess.DEVNULL) as recorder:
        try:
            time.sleep(.65)
            yield
            time.sleep(.65)
        finally:
            if recorder.poll() is None:
                recorder.send_signal(signal.SIGINT)
            try:
                recorder.wait(timeout=8)
            except subprocess.TimeoutExpired:
                recorder.kill()
                raise
    assert recorder.returncode==0 and path.stat().st_size>0, f'Could not record {path.name}'


def move_over(driver, window, bounds):
    x, y, width, height = bounds
    rect = driver.rect(window)
    driver.ipc(f"seat seat0 cursor set {round(rect['x']+x+width/2)} {round(rect['y']+y+height/2)}")
    driver.seat_command('motion 0 0')


def check_workspace_polish(driver, folder, hs, hw, gs, gw, click, project_id):
    def settle(state, page):
        until(lambda:state()['page']==page and not state()['motion']['workspaceRunning'],
              'Workspace transition did not settle in '+page)

    def tap(state, window, name, bounds=None):
        x,y,w,h = bounds or target(state,name)
        driver.click(window,round(x+w/2),round(y+h/2))

    switch=target(hs,'mode-switch')
    interact=target(hs,'mode-Interact')
    build=target(hs,'mode-Build')
    assert switch[2:]==[136,24] and interact[2:]==[72,24] and build[2:]==[64,24]
    if hs()['mode']!='Interact':
        tap(hs,hw,'mode-Interact',interact)
    until(lambda:hs()['mode']=='Interact' and hs()['motion']['mode']==0,'Interact indicator did not settle')
    driver.screenshot(hw,folder/'polish-mode-interact.png')
    x,y,_,_=map(round,switch)
    with record_motion(driver,hw,folder/'mode-switch.mp4',(x-36,y-20,272,116)):
        tap(hs,hw,'mode-Build',build)
        time.sleep(.07)
        driver.screenshot(hw,folder/'polish-mode-slide-right.png',focus=False)
        until(lambda:hs()['mode']=='Build' and hs()['motion']['mode']==1,'Build indicator did not settle')
        driver.screenshot(hw,folder/'polish-mode-build.png')
        tap(hs,hw,'mode-Interact',interact)
        time.sleep(.07)
        driver.screenshot(hw,folder/'polish-mode-slide-left.png',focus=False)
        until(lambda:hs()['mode']=='Interact' and hs()['motion']['mode']==0,'Interact indicator did not return')
    tap(hs,hw,'mode-Build',build)
    tap(hs,hw,'mode-Interact',interact)
    until(lambda:hs()['mode']=='Interact' and hs()['motion']['mode']==0,'Rapid mode toggles selected the wrong mode')
    driver.key('Tab');driver.key('space')
    until(lambda:hs()['mode']=='Build' and hs()['motion']['mode']==1,'Native keyboard did not select Build')
    tap(hs,hw,'mode-Interact',interact)
    for name,selected_x,idle_x in [('interact',4,132),('build',132,4)]:
        with Image.open(folder/('polish-mode-'+name+'.png')) as image:
            pixels=image.convert('RGB')
            assert pixels.getpixel((x+selected_x,y+12))==(235,235,235),'Selected mode fill did not match Figma'
            assert pixels.getpixel((x+idle_x,y+12))==(248,248,248),'Mode track did not match Figma'

    first=hs()
    pid=first['childPid']
    size=first['windowSize']
    move_over(driver,hw,target(hs,'chat-scroller'))
    driver.scroll(up=True)
    time.sleep(.25)
    saved=hs()
    with record_motion(driver,hw,folder/'edit-to-projects.mp4'):
        tap(hs,hw,'nav-projects')
        time.sleep(.14)
        driver.screenshot(hw,folder/'polish-workspace-to-projects.png',focus=False)
        settle(hs,'projects')
    assert hs()['childPid']==pid and hs()['windowSize']==size

    def check_roster(state, window, expected_self, name):
        card=target(state,'open-'+project_id)
        menu=target(state,'menu-'+project_id)
        key='collaborators-'+project_id
        move_over(driver,window,(card[0]+card[2]+8,card[1]+8,1,1))
        until(lambda:key not in state()['targets'],'Collaborator avatars were visible without hover')
        move_over(driver,window,card)
        bounds=target(state,key)
        assert bounds==[card[0]+card[2]-56,card[1]+16,40,24],(card,bounds)
        assert target(state,'menu-'+project_id)==menu
        people=next(p['collaborators'] for p in state()['projects'] if p['id']==project_id)
        assert {p['name'] for p in people}=={'Matt','Guest'}
        assert people[0]['name']==expected_self and people[0]['self']
        driver.screenshot(window,folder/('polish-shared-'+name+'.png'))
        tap(state,window,'menu-'+project_id,menu)
        until(lambda:'menu-rename-'+project_id in state()['targets'],'Hover avatars blocked the tile menu')
        driver.key('Escape')
        return people

    host_roster=check_roster(hs,hw,'Matt','host')
    with record_motion(driver,hw,folder/'projects-to-edit.mp4'):
        tap(hs,hw,'open-'+project_id)
        time.sleep(.17)
        driver.screenshot(hw,folder/'polish-projects-to-workspace.png',focus=False)
        settle(hs,'workspace')
    after=hs()
    assert after['childPid']==pid and after['windowSize']==size
    assert after['project']['id']==saved['project']['id']
    assert after['project']['messages']==saved['project']['messages']
    assert abs(after['chatScroll']['value']-saved['chatScroll']['value'])<3,(saved['chatScroll'],after['chatScroll'])
    assert after['viewport']['mode']==saved['viewport']['mode']
    assert after['viewport']['pan_x']==saved['viewport']['pan_x'] and after['viewport']['pan_y']==saved['viewport']['pan_y']

    guest_pid=gs()['childPid']
    tap(gs,gw,'nav-projects')
    settle(gs,'projects')
    guest_roster=check_roster(gs,gw,'Guest','guest')
    tap(gs,gw,'open-'+project_id)
    settle(gs,'workspace')
    assert gs()['childPid']==guest_pid and gs()['status']=='Guest connected'

    tap(hs,hw,'nav-projects')
    settle(hs,'projects')
    driver.resize(hw,560,size[1])
    until(lambda:hs()['windowSize']==[560,size[1]],'Narrow Projects allocation failed')
    tap(hs,hw,'open-'+project_id)
    settle(hs,'workspace')
    assert hs()['windowSize']==[560,size[1]] and hs()['childPid']==pid
    chat=target(hs,'chat-panel')
    canvas=target(hs,'canvas-panel')
    assert chat[0]==canvas[0] and chat[1]+chat[3]<=canvas[1],(chat,canvas)
    assert target(hs,'mode-switch')[2:]==[136,24]
    driver.screenshot(hw,folder/'polish-narrow-workspace.png')
    driver.resize(hw,*size)
    until(lambda:hs()['windowSize']==size and hs()['targets']['canvas-panel'][0]>hs()['targets']['chat-panel'][0],
          'Wide workspace allocation did not recover')

    (folder/'workspace-polish.json').write_text(json.dumps({
        'hostRoster':host_roster,'guestRoster':guest_roster,'modeSwitch':switch,
        'hostAppProcessPreserved':True,'guestAppProcessPreserved':True,
        'chatAndViewportPreserved':True,'windowSizePreserved':True,'narrowWorkspace':[560,size[1]]},indent=2))
    return ['workspaces-slide-in-both-directions-with-live-host-and-guest-app-chat-and-viewport',
            'mode-indicator-two-directions-rapid-toggles-keyboard-and-figma-geometry',
            'actual-host-and-connected-guest-avatars-hover-only-with-unobstructed-project-menu']


def check_unshared_hover(driver, folder, state, window, project_id, scenario='unshared'):
    move_over(driver,window,target(state,'open-'+project_id))
    time.sleep(.3)
    project=next(p for p in state()['projects'] if p['id']==project_id)
    assert not project.get('collaborators'), 'An unshared project reported participants'
    assert 'collaborators-'+project_id not in state()['targets']
    driver.screenshot(window,folder/f'polish-{scenario}-hover.png')
