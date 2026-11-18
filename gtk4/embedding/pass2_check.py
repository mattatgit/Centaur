"""Pass 2 native presentation/lifecycle checks using disposable project data."""
import hashlib,json,time
from pathlib import Path
from PIL import Image
from check import until,target


def check_settings_feedback(driver,folder,state,window,click,root):
    report={};original=state()['author'];size=state()['grid']['size']
    until(lambda:not state()['settings']['pending'],'Initial Settings reads did not settle')
    assert not state()['settings']['badgeVisible'],'Settings claimed changes on first open'
    def text(key,value):
        click(state,window,key);driver.key('ctrl+a')
        if value:driver.type(value)
        else:driver.key('BackSpace')
        driver.key('Return')
    text('settings-name',original)
    until(lambda:not state()['settings']['pending'],'Unchanged name did not settle')
    assert not state()['settings']['badgeVisible'],'Unchanged value manufactured a saved notice'
    prefs=root/'preferences.ini';before=prefs.read_bytes() if prefs.exists() else None
    text('settings-name','')
    until(lambda:state()['settings']['failed'],'Invalid setting did not retain its error')
    assert state()['settings']['status']=='Could not save changes'
    assert (prefs.read_bytes() if prefs.exists() else None)==before
    click(state,window,'settings-name');driver.key('ctrl+a');driver.type(original+' UI check')
    until(lambda:state()['settings']['pending'],'Editing did not report a pending save')
    assert state()['settings']['status']=='Saving…'
    driver.key('Return')
    until(lambda:state()['author']==original+' UI check' and state()['settings']['status']=='Changes saved','Name was not acknowledged as saved')
    badge=target(state,'saved-status');close=target(state,'window-close')
    assert badge[2:]==[127,32] and abs(close[0]-(badge[0]+badge[2])-8)<=1,('Saved badge differs from Figma header',badge,close)
    first=state()['settings']['savedUntil'];report['firstDeadline']=first
    driver.screenshot(window,folder/'pass2-settings-saved.png')
    while time.monotonic()<first-2:time.sleep(.05)
    text('settings-grid-size',str(16 if size!=16 else 24))
    until(lambda:state()['settings']['savedUntil']>first+6,'A second save did not restart the notice duration')
    second=state()['settings']['savedUntil'];report['secondDeadline']=second
    while time.monotonic()<first+.15:time.sleep(.05)
    assert state()['settings']['badgeVisible'] and state()['settings']['badgeOpacity']>.99,'The original deadline hid a newer saved notice'
    samples=[]
    while time.monotonic()<second+1.2:
        s=state()['settings'];samples.append({'secondsToDeadline':round(second-time.monotonic(),3),'visible':s['badgeVisible'],'opacity':s['badgeOpacity']})
        if 0<s['badgeOpacity']<1:driver.screenshot(window,folder/'pass2-settings-fading.png')
        time.sleep(.05)
    assert any(0<s['opacity']<1 for s in samples),'Saved badge did not fade smoothly'
    assert not state()['settings']['badgeVisible'] and state()['settings']['badgeOpacity']==0
    report.update(badge=badge,close=close,samples=samples,passed=True)
    text('settings-name',original);text('settings-grid-size',str(size))
    until(lambda:state()['author']==original and state()['grid']['size']==size and not state()['settings']['pending'],'Settings audit did not restore its disposable values')
    click(state,window,'settings-name');target(state,'settings-name')
    (folder/'pass2-settings-feedback.json').write_text(json.dumps(report,indent=2)+'\n')
    return 'pass2-settings-no-initial-or-noop-success-pending-errors-acknowledged-save-ten-second-reset-and-fade'


def check_cards_and_profile(driver,folder,state,window,click,project_id):
    def move(x,y):
        r=driver.rect(window);driver.ipc(f"seat seat0 cursor set {round(r['x']+x)} {round(r['y']+y)}");driver.seat_command('motion 0 0');time.sleep(.25)
    def shot(name):
        p=folder/(name+'.png');driver.screenshot(window,p)
        with Image.open(p) as image:return image.convert('RGB').copy()
    card=target(state,'open-'+project_id);image=target(state,'thumbnail-'+project_id)
    assert card[:2]==[state()['layout']['sidebarWidth']+40,state()['windowChrome']['headerHeight']+40],('Project grid inset differs from Figma',card)
    metrics=until(lambda:state().get('thumbnails',{}).get(project_id),'Cached screenshot was not rendered')
    x,y,w,h=metrics['contentRect'];tw,th=metrics['textureSize']
    assert min(x,y,image[2]-x-w,image[3]-y-h)>=24-.01,metrics
    assert abs(w/h-tw/th)<.001,'Cached screenshot changed aspect ratio'
    move(card[0]-20,card[1]-20);idle=shot('pass2-project-rest')
    move(card[0]+card[2]/2,card[1]+card[3]/2);hover=shot('pass2-project-hover')
    assert target(state,'open-'+project_id)==card,'Card hover shifted its layout'
    text_point=(round(card[0]+4),round(card[1]+card[3]-36))
    assert idle.getpixel(text_point)==hover.getpixel(text_point)==(248,248,248),'Card hover changed its text-area background'
    shadow_point=(round(card[0]-4),round(card[1]+100))
    assert sum(hover.getpixel(shadow_point))<sum(idle.getpixel(shadow_point))-5,'Figma card shadow is missing'
    profile=target(state,'sidebar-profile');point=(round(profile[0]+8),round(profile[1]+profile[3]/2))
    move(card[0]-20,card[1]-20);rest=shot('pass2-profile-rest')
    move(profile[0]+profile[2]/2,profile[1]+profile[3]/2);over=shot('pass2-profile-hover')
    assert rest.getpixel(point)==over.getpixel(point),'Sidebar identity retained its rectangular hover fill'
    click(state,window,'sidebar-profile');until(lambda:state()['page']=='settings','Avatar click stopped opening Settings')
    assert not state()['settings']['badgeVisible'],'Reopening Settings displayed an old saved notice'
    click(state,window,'nav-projects')
    for _ in range(12):
        driver.key('Tab');time.sleep(.2)
        if 'sidebar-profile' in state().get('focusedTargets',[]):break
    assert 'sidebar-profile' in state().get('focusedTargets',[]),'Sidebar identity is not keyboard accessible'
    driver.screenshot(window,folder/'pass2-profile-focus.png');driver.key('Return')
    until(lambda:state()['page']=='settings','Keyboard avatar activation stopped opening Settings')
    click(state,window,'nav-projects')
    (folder/'pass2-project-presentation.json').write_text(json.dumps({'card':card,'thumbnailSlot':image,**metrics,'shadowRest':idle.getpixel(shadow_point),'shadowHover':hover.getpixel(shadow_point),'profileHoverFillUnchanged':True,'passed':True},indent=2)+'\n')
    return ['pass2-cached-project-screenshot-24px-padding-and-original-aspect-ratio',
            'pass2-project-hover-elevation-without-text-fill-or-layout-change',
            'pass2-sidebar-avatar-no-block-hover-click-and-native-keyboard-focus']


def check_waiting_flows(driver,folder,state,window,click,message,root,bundle,reply_file):
    gate=folder/'pass2-waiting-gate';gate.write_text('')
    result=json.loads(json.dumps(bundle));result['files']['app.ui']=result['files']['app.ui'].replace('Family board','Prompt-created app')
    proposal={'kind':'proposal','message':'Created the requested native app','conflict':None,'gtk':result}
    def gated(final):
        gate.write_text('');reply_file.write_text(json.dumps({'kind':'question','message':'Creation fixture','fixtureProgressGate':str(gate),'fixtureFinalReply':final}))
    def create(name,prompt):
        click(state,window,'nav-projects');click(state,window,'create')
        until(lambda:state().get('form')=='Create a project','Create form did not open')
        driver.type(name);click(state,window,'create-prompt');driver.type(prompt);click(state,window,'create-submit')
        until(lambda:state()['project'].get('name')==name and state()['waiting']['visible'],'Create did not reach its genuine waiting state')
    def verify_panel(operation,name):
        s=state();assert s['waiting']['operation']==operation and s['waiting']['support']=='Please wait a moment'
        assert s['waiting']['title']=='Centaur is '+('creating' if operation=='create' else 'importing')+' your project'
        assert target(state,'canvas-waiting')[2:]==[304,256] and target(state,'waiting-illustration')[2:]==[128,128]
        panel=target(state,'canvas-waiting');canvas=target(state,'canvas-panel')
        assert abs(panel[0]+panel[2]/2-canvas[0]-canvas[2]/2)<=1 and abs(panel[1]+panel[3]/2-canvas[1]-canvas[3]/2)<=1,'Waiting panel is not centred in the full canvas'
        assert s['workingAnimation']['running'] and s['activity']['inConversation'],'Canvas waiting replaced chronological agent progress'
        assert not s.get('childPid'),'Waiting state executed a starter/imported app'
        driver.screenshot(window,folder/(name+'.png'))
    gated(proposal);create('Pass 2 creation','Create a native app from this prompt.')
    verify_panel('create','pass2-create-waiting');project=state()['project'];first_id=project['id']
    expected='@'+project['agentName']+' Create a native app from this prompt.'
    assert sum(m.get('text')==expected for m in project['messages'])==1,'Create prompt was lost or duplicated'
    gate.write_text('finish')
    until(lambda:(state().get('child') or {}).get('title')=='Prompt-created app','Create prompt did not reach a useful native preview',timeout=25)
    assert not state()['project'].get('creationPending') and not state()['waiting']['visible']
    gated(proposal);create('Pass 2 retry','Create another native app.')
    verify_panel('create','pass2-create-cancellable');click(state,window,'stop-agent')
    until(lambda:not state().get('busy') and not state()['waiting']['visible'],'Stop left a false creation waiting state')
    assert state()['project']['creationPending'] and not state().get('childPid')
    gated(proposal);message(state,window,'@'+state()['project']['agentName']+' Retry this creation.')
    until(lambda:state()['waiting']['visible'],'Creation retry did not show genuine progress');gate.write_text('fail')
    until(lambda:not state().get('busy') and not state()['waiting']['visible'],'Failed creation retained its waiting panel')
    assert state()['project']['creationPending'];driver.screenshot(window,folder/'pass2-create-failed.png')
    reply_file.write_text(json.dumps(proposal));message(state,window,'@'+state()['project']['agentName']+' Create the app now.')
    until(lambda:(state().get('child') or {}).get('title')=='Prompt-created app' and not state()['project'].get('creationPending'),'Creation did not recover after cancellation and failure',timeout=25)
    # A controlled unreadable source checks the real acquisition failure path.
    source=folder/'pass2-import-source';source.mkdir();original=source/'App.swift';original.write_text('import SwiftUI\nstruct Example {}\n');before=original.read_bytes()
    click(state,window,'nav-projects');click(state,window,'import')
    until(lambda:state().get('form')=='Import a project','Import form did not open')
    for key,text in [('import-name','Pass 2 import'),('import-source',str(source))]:click(state,window,key);driver.type(text)
    reply_file.write_text(json.dumps({'kind':'question','message':'The source was unreadable. Please choose it again.'}))
    try:
        source.chmod(0);click(state,window,'import-submit')
        until(lambda:state()['project'].get('name')=='Pass 2 import' and state()['project'].get('import',{}).get('status')=='awaitingAnswer' and not state()['busy'],'Controlled acquisition failure did not reach its diagnostic question')
        saved=json.loads((root/'projects'/state()['project']['id']/'.centaur/state.json').read_text())
        assert saved['importLocal']['diagnostics']['failure'] and not saved['importLocal']['sourceAvailable']
        assert not state()['waiting']['visible'] and not state().get('childPid')
        driver.screenshot(window,folder/'pass2-import-failed.png')
    finally:source.chmod(0o700)
    gated({'kind':'question','message':'Please confirm the desired GTK preview.'})
    failed_id=state()['project']['id'];click(state,window,'nav-projects');click(state,window,'menu-'+failed_id);click(state,window,'menu-change-source-'+failed_id)
    until(lambda:state().get('form')=='Import a project','Retry did not reopen source management');click(state,window,'import-submit')
    until(lambda:state()['waiting']['visible'] and state()['workingAnimation']['running'],'Import retry did not reach genuine agent progress')
    verify_panel('import','pass2-import-waiting');imported_id=state()['project']['id'];gate.write_text('finish')
    until(lambda:state()['project']['import']['status']=='awaitingAnswer' and not state()['waiting']['visible'],'Import question left a false waiting state')
    reply_file.write_text(json.dumps(proposal));message(state,window,'@'+state()['project']['agentName']+' Prepare a GTK preview from this source.')
    until(lambda:state()['project']['import']['status']=='readyToRun','Import did not stage its GTK adaptation')
    assert not state().get('childPid') and not state()['waiting']['visible'];click(state,window,'import-run')
    until(lambda:(state().get('child') or {}).get('ready'),'Explicit adapted preview did not map',timeout=25)
    edited=json.loads(json.dumps(result));edited['files']['app.ui']=edited['files']['app.ui'].replace('Prompt-created app','Edited imported app')
    reply_file.write_text(json.dumps({'kind':'proposal','message':'Edit the imported app','conflict':None,'gtk':edited}))
    message(state,window,'@'+state()['project']['agentName']+' Change the title of this imported preview.')
    until(lambda:(state().get('child') or {}).get('title')=='Edited imported app','Imported agent edit did not reach the native app',timeout=25)
    assert 'import-retry' not in state()['targets'] and 'import-run' not in state()['targets'] and not state()['waiting']['visible'],'Stray source controls returned above the composer'
    assert original.read_bytes()==before
    driver.screenshot(window,folder/'pass2-imported-edit-no-stray-button.png')
    click(state,window,'nav-projects');click(state,window,'menu-'+imported_id)
    until(lambda:'menu-source-'+imported_id in state()['targets'] and 'menu-change-source-'+imported_id in state()['targets'],'Imported source menu did not map')
    # Check the actual launch method without starting the VM's file manager.
    # Original source and a separately exported adaptation must stay distinct.
    from types import SimpleNamespace
    from unittest.mock import patch
    from gi.repository import Gio
    from shell import Centaur
    current=json.loads(json.dumps(state()['project']));storage=root/'projects'/imported_id/'.centaur/import'/current['import']['storage']
    adaptation=storage/'launch-check-adaptation';adaptation.mkdir()
    current['import']['output']=adaptation.name;opened=[]
    def missing(*unused):raise AssertionError('Source launcher rejected a valid saved directory')
    owner=SimpleNamespace(root=root,notice=missing)
    with patch.object(Gio.AppInfo,'launch_default_for_uri',side_effect=lambda uri,context:opened.append(uri)):
        Centaur.open_imported(owner,current)
        Centaur.open_imported(owner,current,True)
    assert opened==[(storage/'source').resolve().as_uri(),adaptation.resolve().as_uri()],'Open source opened the adaptation instead of the copied source'
    click(state,window,'menu-change-source-'+imported_id)
    until(lambda:state().get('form')=='Import a project','Source management was lost when removed from chat')
    driver.key('Escape');assert original.read_bytes()==before
    (folder/'pass2-waiting-flows.json').write_text(json.dumps({'createdProject':first_id,'importedProject':imported_id,'createPromptSubmittedOnce':True,'createCancellationFailureAndRetry':True,'sourceUnchanged':True,'noStrayChatActionsAfterEdit':True,'sourceManagementInProjectMenu':True,'openSourceCorrectManagedDirectory':True,'openAdaptationSeparate':True,'passed':True},indent=2)+'\n')
    return ['pass2-create-prompt-real-agent-queue-canvas-state-native-completion-cancel-failure-retry',
            'pass2-import-canvas-state-acquisition-failure-retry-question-and-explicit-native-run',
            'pass2-successful-imported-agent-edit-no-stray-composer-source-actions-menu-management-retained']
