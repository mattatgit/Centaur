"""Pixel and native-input checks for the four owner-reported V2 issues."""
import json
import time
from PIL import Image
from check import until,target


def check_provider_hovers(driver,folder,state,window):
    report={}
    def move(x,y):
        rect=driver.rect(window)
        driver.ipc(f"seat seat0 cursor set {round(rect['x']+x)} {round(rect['y']+y)}")
        driver.seat_command('motion 0 0'); time.sleep(.25)
    def capture(name,bounds):
        path=folder/(name+'.png');driver.screenshot(window,path,focus=False)
        with Image.open(path) as image:
            x,y,w,h=map(round,bounds)
            return image.convert('RGB').crop((x,y,x+w,y+h))
    for provider,connected in [('openai-codex',True),('anthropic',False)]:
        action='provider-'+provider; card='provider-card-'+provider
        baseline=[target(state,card),target(state,action)]
        row,bounds=baseline; x,y,w,h=bounds
        assert row[2:]==[504,48] and [w,h]==([80,32] if connected else [67,32]),baseline
        background=(241,250,248) if connected else (248,248,248)
        hover=(224,242,238) if connected else (235,235,235)
        move(240,100)
        resting=capture('ui-provider-'+provider+'-rest',row)
        move(row[0]+160,row[1]+24)
        row_hover=capture('ui-provider-'+provider+'-row-hover',row)
        move(x+w/2,y+h/2)
        action_hover=capture('ui-provider-'+provider+'-action-hover',row)
        # Sample the centre-left interior of the action, outside its glyphs.
        sample=(round(x-row[0]+3),round(y-row[1]+h/2))
        assert resting.getpixel(sample)==row_hover.getpixel(sample)==background,(provider,sample)
        assert action_hover.getpixel(sample)==hover,(provider,action_hover.getpixel(sample),hover)
        rect=(round(x-row[0]),round(y-row[1]),round(x-row[0]+w),round(y-row[1]+h))
        assert list(row_hover.crop(rect).getdata()).count((50,50,50))>=3,'Row-hover action lost Charcoal text'
        assert list(action_hover.crop(rect).getdata()).count((23,23,23))>=3,'Action-hover text is not Main text colour'
        assert action_hover.getpixel((round(x-row[0]),round(y-row[1])))==background,'Action lost its 8px rounded corner'
        for image in (row_hover,action_hover):
            assert image.getpixel((0,24))==background,'Action hover changed the row background'
        if not connected:
            assert resting.tobytes()!=row_hover.tobytes(),'Row hover did not reveal Connect'
        assert [target(state,card),target(state,action)]==baseline,'Provider hover shifted layout'
        # Let GTK's normal tooltip delay elapse; none may be configured/shown.
        time.sleep(1.25)
        assert not state()['tooltipWidgets'] and not state()['tooltipWindows'],state()['tooltipWidgets']
        report[provider]={'row':row,'action':bounds,'restAndRowFill':background,'directHoverFill':hover}
    # Navigate with real keyboard focus. Do not activate authentication controls.
    driver.click(window,round(row[0]+120),round(row[1]+24)); time.sleep(.25)
    for provider in ('openai-codex','anthropic'):
        for _ in range(40):
            if 'provider-'+provider in state().get('focusedTargets',[]): break
            previous=state().get('focusSequence',0)
            driver.key('Tab')
            until(lambda:state().get('focusSequence',0)>previous,'Native Tab focus did not reach the next control')
        until(lambda:'provider-'+provider in state().get('focusedTargets',[]),'Provider action was unreachable by keyboard')
        capture('ui-provider-'+provider+'-keyboard-focus',target(state,'provider-card-'+provider))
    assert [target(state,'provider-card-anthropic'),target(state,'provider-anthropic')]==baseline
    (folder/'provider-hover-metrics.json').write_text(json.dumps(report,indent=2))
    return 'figma-connected-disconnected-row-and-action-hover-pixels-stable-layout-keyboard-focus-no-tooltips'


def check_working_pixels(driver,folder,state,window):
    until(lambda:state().get('workingAnimation',{}).get('running'),'Working mark did not start its native frame clock')
    mark=until(lambda:next((s['bounds'] for s in state()['assetSlots'] if s['file']=='v2/centaur_wait_animation.svg'),None),'Working mark did not receive its native allocation')
    x,y,w,h=map(round,mark);assert (w,h)==(32,32)
    captures=[]; samples=[]; started=time.monotonic()
    for index in range(12):
        time.sleep(.12)
        path=folder/f'ui-working-clock-{index:02}.png'
        driver.screenshot(window,path,focus=False)
        with Image.open(path) as image:
            crop=image.convert('RGB').crop((x,y,x+w,y+h));captures.append(crop.copy())
        path.unlink();crop.save(path)
        samples.append({'seconds':round(time.monotonic()-started,3),**state()['workingAnimation']})
        assert 'import-open' not in state()['targets'],'Uncontextual source action returned to chat'
        assert not state()['tooltipWidgets'] and not state()['tooltipWindows']
    assert len({c.tobytes() for c in captures})>=3,'Active agent card remained visually static'
    captures[0].save(folder/'ui-working-playback.gif',save_all=True,append_images=captures[1:],duration=round(samples[-1]['seconds']*1000/len(captures)),loop=0)
    (folder/'working-playback-metrics.json').write_text(json.dumps(samples,indent=2))
    return 'active-agent-card-visible-native-animation-and-contextual-import-controls'
