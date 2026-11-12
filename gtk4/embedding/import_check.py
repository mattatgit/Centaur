"""Hands-on-equivalent native import flow, in disposable CI project storage."""
import json
from pathlib import Path
from check import until, target


def check_imports(driver,folder,state,window,click,message,root,bundle,reply_file,request_record):
    checks=[]
    def form(name,source,prompt=''):
        click(state,window,'nav-projects'); click(state,window,'import')
        until(lambda:state().get('form')=='Import a project','Import modal did not open')
        bounds=target(state,'dialog-card')
        assert bounds[2:]==[408,432],('Figma modal dimensions',bounds)
        for key,text in [('import-name',name),('import-source',str(source)),('import-prompt',prompt)]:
            if text: click(state,window,key); driver.type(text)

    count=len(state()['projects'])
    form('Friendly imported app','https://token@github.com/owner/private')
    driver.screenshot(window,folder/'ui-import-modal.png',focus=False)
    click(state,window,'import-submit')
    until(lambda:state().get('targets',{}).get('import-error'),'Invalid source did not stay in the modal')
    assert len(state()['projects'])==count
    driver.key('Escape')
    checks.append('figma-import-modal-and-credential-url-validation')

    original=folder/'local-gtk-source'; original.mkdir()
    marker=folder/'imported-code-executed'
    app=json.loads(json.dumps(bundle)); app['files']['app.py']='from pathlib import Path\nPath('+repr(str(marker))+').write_text("explicit run")\n'+app['files']['app.py']
    original_file=original/'App.gtk.json'; original_file.write_text(json.dumps(app)); before=original_file.read_bytes()
    form('Friendly imported app',original)
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
    driver.screenshot(window,folder/'ui-import-adaptation.png',focus=False)
    checks.append('unsupported-source-preserved-normal-chat-clarification-and-requested-css-js-output')

    reply_file.write_text(json.dumps({'kind':'question','message':'The repository is imported. What would you like to work on?'}))
    prompt='Preserve the source and tell me what this repository contains.'
    form('GitHub example','https://github.com/octocat/Hello-World',prompt); click(state,window,'import-submit')
    until(lambda:state()['project'].get('import',{}).get('status')=='awaitingAnswer','Public GitHub source import did not finish',timeout=110)
    project=state()['project']; info=project['import']
    storage=root/'projects'/project['id']/'.centaur/import'/info['storage']
    assert (storage/'source/README').is_file() and (storage/'history.git/HEAD').is_file()
    assert prompt in request_record.read_text() and project['name']=='GitHub example'
    assert 'importLocal' not in project
    driver.screenshot(window,folder/'ui-import-github.png',focus=False)
    checks.append('public-github-history-optional-prompt-and-private-locator-not-published')
    return checks
