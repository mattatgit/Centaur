"""Hands-on-equivalent native import flow, in disposable CI project storage."""
import json
import subprocess
from pathlib import Path
from check import until, target
from PIL import Image


def check_imports(driver,folder,state,window,click,message,root,bundle,reply_file,request_record):
    checks=[]
    def form(name,source,prompt=''):
        click(state,window,'nav-projects'); click(state,window,'import')
        until(lambda:state().get('form')=='Import a project','Import modal did not open')
        bounds=target(state,'dialog-card')
        assert bounds[2:]==[408,432],('Figma modal dimensions',bounds)
        for key,text in [('import-name',name),('import-source',str(source)),('import-prompt',prompt)]:
            if text: click(state,window,key); driver.type(text)
        if str(source).startswith('https://github.com/'):
            until(lambda:state().get('importDialog',{}).get('canImport'),'GitHub branch discovery did not enable import',timeout=110)

    count=len(state()['projects'])
    form('Friendly imported app','https://token@github.com/owner/private')
    driver.screenshot(window,folder/'ui-import-modal.png',focus=False)
    assert not state()['importDialog']['canImport'],'Credential URL enabled import'
    assert len(state()['projects'])==count
    driver.key('Escape')
    checks.append('figma-import-modal-and-credential-url-validation')

    original=folder/'local-gtk-source'; original.mkdir()
    marker=folder/'imported-code-executed'
    app=json.loads(json.dumps(bundle)); app['files']['app.py']='from pathlib import Path\nPath('+repr(str(marker))+').write_text("explicit run")\n'+app['files']['app.py']
    original_file=original/'App.gtk.json'; original_file.write_text(json.dumps(app)); before=original_file.read_bytes()
    form('Friendly imported app',original)
    assert not state()['importDialog']['branchVisible'],'Local folder displayed branch selector'
    click(state,window,'import-name'); driver.key('End')
    until(lambda:state()['importDialog']['nameFocused'],'Name input lost keyboard focus')
    driver.screenshot(window,folder/'ui-import-input-focus.png',focus=False)
    with Image.open(folder/'ui-import-input-focus.png') as image:
        pixels=image.convert('RGB'); x,y,w,h=map(round,target(state,'import-name'))
        assert not any(pixels.getpixel((xx,yy))==(19,142,213) for xx in range(x-3,x+w+3) for yy in range(y-3,y+h+3)), 'Input retains blue focus outline'
        assert pixels.getpixel((x+1,y+h//2))==(248,248,248) and pixels.getpixel((x+w-2,y+h//2))==(248,248,248),'Input edges are clipped'
    click(state,window,'import-source')
    rect=driver.rect(window); x,y,w,h=target(state,'import-submit')
    driver.ipc(f"seat seat0 cursor set {round(rect['x']+x+w-2)} {round(rect['y']+y+h/2)}"); driver.seat_command('motion 0 0')
    driver.screenshot(window,folder/'ui-import-button-hover.png',focus=False)
    with Image.open(folder/'ui-import-button-hover.png') as image:
        pixels=image.convert('RGB'); x,y,w,h=map(round,target(state,'import-submit'))
        assert pixels.getpixel((x+w-1,y+h//2))==(23,23,23),'Import button right edge is clipped'
        assert pixels.getpixel((x+w-1,y+1))==(255,255,255),'Import button right corner lost its radius on hover'
    click(state,window,'import-submit')
    until(lambda:state().get('page')=='workspace' and state().get('project',{}).get('name')=='Friendly imported app','Import did not enter workspace immediately')
    until(lambda:state()['project'].get('import',{}).get('status')=='readyToRun','Compatible source was not staged')
    project=state()['project']; imported_id=project['id']
    assert not state().get('childPid') and not marker.exists(),'Import executed source without explicit run'
    assert original_file.read_bytes()==before
    assert not (root/'projects'/imported_id/'App.gtk.json').exists(),'A fake starter app was created for import'
    driver.screenshot(window,folder/'ui-import-ready.png',focus=False)
    click(state,window,'nav-projects'); click(state,window,'open-'+imported_id)
    until(lambda:state()['project'].get('import',{}).get('status')=='readyToRun','Import state was lost on navigation')
    click(state,window,'import-run')
    until(lambda:(state().get('child') or {}).get('ready'),'Explicit imported GTK preview did not start')
    assert marker.exists() and state()['project']['import']['previewReady']
    assert original_file.read_bytes()==before
    checks.append('local-managed-copy-name-persistence-no-starter-and-explicit-native-run')
    preview_pid=state()['childPid']
    reply_file.write_text(json.dumps({'kind':'inspect','message':'Checking the source','paths':['App.gtk.json']}))
    message(state,window,'@centaur Check the imported source again.')
    until(lambda:any(m.get('text')=='I checked the imported source.' for m in state()['project'].get('messages',[])),
          'Source inspection did not continue after preview activation')
    assert state()['childPid']==preview_pid,'Reading source restarted the app'
    checks.append('controlled-source-inspection-after-preview-without-restarting-app')

    swift=folder/'ios-source'; swift.mkdir(); (swift/'App.swift').write_text('import SwiftUI\nstruct Example {}')
    reply_file.write_text(json.dumps({'kind':'question','message':'This is an iOS app. What would you like to make from it?'}))
    form('iOS source',swift); click(state,window,'import-submit')
    until(lambda:state()['project'].get('import',{}).get('status')=='awaitingAnswer','Unsupported source did not ask through chat')
    project=state()['project']; ios_id=project['id']
    assert project['import']['framework']=='iOS / Swift' and not state().get('childPid')
    reply_file.write_text(json.dumps({'kind':'artifact','message':'I’ll prepare a separate CSS/JS staging version.',
        'target':'css-js','files':{'index.html':'<h1>Staging app</h1>','app.js':'console.log("staging");','style.css':'body { margin: 24px; }'}}))
    message(state,window,'Make a CSS/JS staging version, please.')
    until(lambda:state()['project'].get('import',{}).get('output'),'Normal chat did not create the requested separate adaptation')
    info=state()['project']['import']; storage=root/'projects'/ios_id/'.centaur/import'/info['storage']
    assert (storage/'source/App.swift').read_text()=='import SwiftUI\nstruct Example {}'
    assert (storage/info['output']/'index.html').read_text()=='<h1>Staging app</h1>'
    assert not info.get('previewReady') and info['target']=='css-js'
    assert 'Make a CSS/JS staging version' in request_record.read_text()
    reply_file.write_text(json.dumps({'kind':'inspect','message':'Checking the staging version','scope':'adaptation','paths':['index.html']}))
    message(state,window,'Check the current staging version, please.')
    until(lambda:any(m.get('text')=='I checked the imported source.' for m in state()['project'].get('messages',[])),
          'The agent could not inspect its existing adaptation')
    assert 'adaptationInspection' in request_record.read_text() and '<h1>Staging app</h1>' in request_record.read_text()
    assert json.loads((root/'projects'/ios_id/'.centaur/state.json').read_text())['importLocal']['adaptation']['files']['index.html']=='<h1>Staging app</h1>'
    reply_file.write_text(json.dumps({'kind':'artifact','message':'I’ll update the staging heading.',
        'target':'css-js','files':{'index.html':'<h1>Updated staging app</h1>','app.js':'console.log("staging");','style.css':'body { margin: 24px; }'}}))
    message(state,window,'Change the staging heading, please.')
    until(lambda:state()['project'].get('import',{}).get('output')!=info['output'],'Adaptation edit was not saved')
    assert (storage/info['output']/'index.html').read_text()=='<h1>Staging app</h1>'
    assert (storage/state()['project']['import']['output']/'index.html').read_text()=='<h1>Updated staging app</h1>'
    driver.screenshot(window,folder/'ui-import-adaptation.png',focus=False)
    checks.append('unsupported-source-preserved-normal-chat-clarification-css-js-output-and-versioned-edits-with-inspection')

    reply_file.write_text(json.dumps({'kind':'question','message':'The repository is imported. What would you like to work on?'}))
    prompt='Preserve the source and tell me what this repository contains.'
    form('GitHub example','https://github.com/octocat/Hello-World',prompt)
    default=state()['importDialog']['branchLabel']; click(state,window,'import-branch')
    until(lambda:len(state().get('importDialog',{}).get('branches',[]))>1,'Branch menu did not populate')
    other=next(name for name in state()['importDialog']['branches'] if name!=default)
    click(state,window,'import-branch-option-'+other)
    assert state()['importDialog']['branchLabel']==other
    click(state,window,'import-branch'); click(state,window,'import-branch-option-'+default)
    assert state()['importDialog']['branchLabel']==default
    click(state,window,'import-submit')
    until(lambda:state()['project'].get('name')=='GitHub example' and state()['project'].get('import',{}).get('status')=='awaitingAnswer','Public GitHub source import did not finish',timeout=110)
    project=state()['project']; info=project['import']
    storage=root/'projects'/project['id']/'.centaur/import'/info['storage']
    assert (storage/'source/README').is_file() and (storage/'history.git/HEAD').is_file()
    assert prompt in request_record.read_text() and project['name']=='GitHub example'
    assert 'importLocal' not in project
    driver.screenshot(window,folder/'ui-import-github.png',focus=False)
    checks.append('public-github-history-optional-prompt-and-private-locator-not-published')
    value='https://github.com/mattatgit/landline/tree/linux-nix'
    expected_commit=subprocess.check_output(['git','ls-remote','--','https://github.com/mattatgit/landline.git','refs/heads/linux-nix'],text=True).split()[0]
    form('Landline Linux',value,'Investigate the Linux/Nix application on this selected branch.')
    assert state()['importDialog']['branchLabel']=='linux-nix'
    bounds=target(state,'dialog-card'); assert bounds[2:]==[408,512],bounds
    assert target(state,'import-branch')[1]>target(state,'import-source')[1],'Branch is not beneath Source'
    click(state,window,'import-branch'); driver.screenshot(window,folder/'ui-import-branches-open.png',focus=False)
    if state().get('targets',{}).get('import-branch-search'):
        click(state,window,'import-branch-search'); driver.type('linux-nix')
        until(lambda:state()['importDialog']['branches']==['linux-nix'],'Branch search did not filter its options')
    assert target(state,'import-branch-option-linux-nix')[3]==24
    driver.key('Escape')
    until(lambda:state().get('form')=='Import a project','Closing branch popup closed the form')
    driver.screenshot(window,folder/'ui-import-branch-selected.png',focus=False)
    click(state,window,'import-submit')
    until(lambda:state()['project'].get('name')=='Landline Linux' and state()['project'].get('import',{}).get('status')=='awaitingAnswer','Landline branch import failed',timeout=110)
    project=state()['project']; info=project['import']
    assert info['branch']=='linux-nix' and info['commit']==expected_commit
    assert 'LandlineNix/Cargo.toml' in request_record.read_text() and 'LandlineNix/src/main.rs' in request_record.read_text()
    assert info['commit'] in request_record.read_text() and info['framework']=='Nix / Rust'
    checks.append('landline-linux-nix-url-preselection-verified-commit-and-linux-agent-context')
    return checks
