"""Opt-in real OMP smoke check, using a disposable project and existing login."""
import json,os,subprocess,sys,time
from pathlib import Path
from check import until,read,target
from test_driver import Driver


def main():
    folder=Path(sys.argv[1]).resolve();folder.mkdir(parents=True,exist_ok=False)
    executable=Path(sys.argv[0]).resolve().parent/'centaur-gtk4'
    driver=Driver();driver.ipc('output HEADLESS-1 mode 1600x1100')
    report=folder/'report';root=folder/'data'
    env=dict(os.environ,CENTAUR_AGENT=str(Path.home()/'.local/bin/omp'),CENTAUR_MODEL='openai-codex/gpt-6.1-sol')
    for kind in ('CONFIG','DATA','CACHE'):
        path=folder/('desktop-'+kind.lower());path.mkdir(mode=0o700);env['XDG_'+kind+'_HOME']=str(path)
    # OMP continues to use its existing account/config. No login/logout or
    # credential/config-file copying is performed by this probe.
    process=subprocess.Popen([str(executable),'--data-dir',str(root),'--report-dir',str(report)],env=env)
    state=lambda:read(report/'shell.json');samples=[];result={'ownerProfileActivated':False,'rawProviderOutputStored':False}
    try:
        until(lambda:'create-main' in state().get('targets',{}),'Real-check shell did not map')
        window=driver.find_window('org.centaur.Gtk4',state()['pid']);driver.track_native(window,state)
        def click(name):
            x,y,w,h=target(state,name);driver.click(window,round(x+w/2),round(y+h/2));time.sleep(.15)
        click('create-main')
        until(lambda:state().get('form')=='Create a project','Create form missing')
        click('create-name');driver.type('Agent visibility verification');click('create-submit')
        until(lambda:state().get('page')=='workspace' and state().get('project',{}).get('id'),'Disposable project missing')
        source=root/'projects'/state()['project']['id']/'App.gtk.json'
        before=source.read_bytes();revision=state()['project']['revision']
        text='@centaur Please reply only with an informational answer saying connection verified. Do not propose or restore any app or source change.'
        click('editor');driver.type(text);driver.key('Return')
        until(lambda:state().get('activity',{}).get('requestId'),'Real request did not expose inline activity')
        started=time.monotonic();request=state()['activity']['requestId']
        last=None
        while time.monotonic()-started<200:
            s=state();a=s.get('activity',{});phase=a.get('phase')
            if phase and phase!=last:
                samples.append({'seconds':round(time.monotonic()-started,2),'phase':phase,'caption':a.get('caption')});last=phase
                driver.screenshot(window,folder/('real-agent-'+phase+'.png'))
            if not a.get('requestId') and any(m.get('kind') in ('agent','system') for m in s.get('project',{}).get('messages',[])[1:]):break
            time.sleep(.25)
        final=state();messages=final['project']['messages']
        failures=[m['agentDiagnostics'] for m in messages if m.get('agentDiagnostics')]
        result.update(samples=samples,requestId=request,seconds=round(time.monotonic()-started,2),failureDetails=failures,
            sourceUnchanged=source.read_bytes()==before,revisionUnchanged=final['project']['revision']==revision,
            inline=all('PRIVATE' not in x.get('caption','') for x in samples),animationStopped=not final['workingAnimation']['running'])
        assert result['sourceUnchanged'] and result['revisionUnchanged'] and result['animationStopped'],result
        assert not failures and any('connection verified' in m.get('text','').lower() for m in messages if m.get('kind')=='agent'),result
        assert any(s['phase'] in ('processing','responding') for s in samples),'Real provider progress was not observable'
        driver.screenshot(window,folder/'real-agent-complete.png');result['passed']=True
    finally:
        process.terminate();process.wait(timeout=8)
        subprocess.run([str(executable),'--stop-host','--data-dir',str(root)],env=env,check=True,timeout=10)
        (folder/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
        print('REAL_NATIVE_AGENT='+json.dumps(result),flush=True)
    return 0
