"""Native conversation-flow, truthful progress and in-app diagnostic checks."""
import json,time,hashlib
from check import until,target
from agent_activity import details_text


def check_activity(driver,folder,hs,hw,gs,gw,click,message,control,reply_file):
    checks=[];gate=folder/'progress-gate';gate.write_text('')
    before=len(hs()['project']['messages'])
    reply_file.write_text(json.dumps({'kind':'question','message':'Controlled progress complete.','fixtureProgressGate':str(gate)}))
    message(hs,hw,'@centaur A controlled progress request')
    until(lambda:hs().get('activity',{}).get('phase')=='processing','OMP processing event did not reach inline activity')
    initial=hs();activity=initial['activity'];request=activity['requestId'];widget=activity['widget']
    epoch=activity['animationEpoch']
    assert activity['inConversation'] and 'preparing a response' in activity['caption']
    assert len(initial['project']['messages'])==before+1,'Progress inserted persistent message clutter'
    assert initial['workingAnimation']['running']
    tile=target(hs,'activity-tile');viewport=target(hs,'chat-scroller')
    assert tile[1]>=viewport[1] and tile[1]+tile[3]<=viewport[1]+viewport[3]+1,(tile,viewport)
    driver.screenshot(hw,folder/'ui-inline-agent-processing.png')
    gate.write_text('response')
    until(lambda:hs()['activity']['phase']=='responding','Text-stream event did not update the same tile')
    assert hs()['activity']['widget']==widget and hs()['activity']['requestId']==request
    assert len(hs()['project']['messages'])==before+1
    assert 'PRIVATE_ACTIVITY_CANARY' not in json.dumps(hs())
    # Scroll real input upward. The activity must move with normal messages.
    value=hs()['chatScroll']['value'];y=target(hs,'activity-tile')[1]
    r=driver.rect(hw);x0,y0,w,h=viewport
    driver.ipc(f"seat seat0 cursor set {round(r['x']+x0+w/2)} {round(r['y']+y0+h/2)}")
    driver.seat_command('motion 0 0');driver.scroll(up=True)
    until(lambda:hs()['chatScroll']['value']<value-40,'Conversation did not scroll upward')
    reading=hs();delta=value-reading['chatScroll']['value']
    assert abs(target(hs,'activity-tile')[1]-y-delta)<=2,'Activity remained fixed outside scrolling messages'
    old=reading['chatScroll']['value']
    gate.write_text('retry')
    until(lambda:hs()['activity']['phase']=='retrying','Real retry event did not reach the tile')
    message(gs,gw,'A note while the agent is working.')
    until(lambda:any(m.get('text')=='A note while the agent is working.' for m in hs()['project']['messages']),'Concurrent conversation message did not arrive')
    time.sleep(.35)
    assert abs(hs()['chatScroll']['value']-old)<3,'Progress or a new message forced a reader to the bottom'
    assert hs()['activity']['requestId']==request and hs()['activity']['widget']==widget
    assert hs()['activity']['animationEpoch']==epoch,'A concurrent message restarted the working animation'
    driver.screenshot(hw,folder/'ui-inline-agent-reading-history.png')
    gate.write_text('finish')
    until(lambda:any(m.get('text')=='Controlled progress complete.' for m in hs()['project']['messages']),'Controlled completion did not reach chat')
    until(lambda:not hs().get('activity',{}).get('requestId') and not hs()['workingAnimation']['running'],'Completed tile kept animating')
    assert abs(hs()['chatScroll']['value']-old)<3,'Completion forced a reader to the bottom'
    checks.append('inline-chronological-stable-progress-observed-events-no-clutter-natural-scroll-and-reader-position')
    # Return to the end using the native scrollbar/wheel before another request.
    driver.ipc(f'[con_id={hw}] focus');r=driver.rect(hw)
    driver.ipc(f"seat seat0 cursor set {round(r['x']+x0+w/2)} {round(r['y']+y0+h/2)}")
    driver.seat_command('motion 0 0')
    for _ in range(30):
        scroll=hs()['chatScroll']
        if scroll['value']>=scroll['upper']-scroll['pageSize']-2:break
        driver.scroll(up=False)
    until(lambda:hs()['chatScroll']['value']>=hs()['chatScroll']['upper']-hs()['chatScroll']['pageSize']-2,'Could not return to current conversation')
    gate.write_text('')
    reply_file.write_text(json.dumps({'kind':'question','message':'Controlled failure.','fixtureProgressGate':str(gate)}))
    message(hs,hw,'@centaur A controlled failing request')
    until(lambda:hs()['activity']['phase']=='processing','Second request did not start independently')
    assert hs()['activity']['requestId']!=request
    gate.write_text('fail')
    until(lambda:any(m.get('agentDiagnostics') for m in hs()['project']['messages']),'Failed request has no in-app diagnostic record')
    failure=next(m for m in reversed(hs()['project']['messages']) if m.get('agentDiagnostics'))
    details=failure['agentDiagnostics'];assert details['code']=='agent_process_exit'
    assert details['layer']=='centaur.agent' and details['sourceUnchanged'] and details['sourceComparisonAvailable']
    assert 'SECRET_' not in json.dumps(details)
    until(lambda:not hs()['workingAnimation']['running'],'Failed request kept animating')
    click(hs,hw,'agent-details-'+failure['id'])
    until(lambda:hs().get('form')=='Agent request details','In-app request details did not open')
    driver.screenshot(hw,folder/'ui-agent-request-details.png')
    click(hs,hw,'agent-details-copy')
    click(hs,hw,'agent-details-done')
    until(lambda:not hs().get('form'),'Request details did not close')
    # A background Wayland client cannot read another client's clipboard.
    # Paste through the focused native UI instead; this is a disposable chat.
    copied=details_text(details)
    click(hs,hw,'editor');driver.key('ctrl+a');driver.key('ctrl+v')
    digest=hashlib.sha256(copied.encode()).hexdigest()
    until(lambda:hs().get('draft',{}).get('sha256')==digest,'Copied details did not reach the native editor')
    driver.key('Return')
    until(lambda:any(m.get('text')==copied for m in hs()['project']['messages']),'Request details could not be copied and pasted')
    assert 'SECRET_' not in copied and 'PRIVATE_ACTIVITY_CANARY' not in copied
    checks.append('failure-resolves-inline-activity-and-public-correlated-diagnostics-copy-without-provider-secrets')
    (folder/'activity-metrics.json').write_text(json.dumps({'initialTile':tile,'scroller':viewport,'requestId':request,'nativeScrollDelta':delta,'diagnosticCode':details['code'],'sourceUnchanged':details['sourceUnchanged'],'copiedDetails':True},indent=2))
    return checks
