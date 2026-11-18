"""Public activity presentation; never renders model deltas or provider logs."""
from datetime import datetime,timezone

PHASES={
    'starting':'Starting agent…', 'waiting':'Waiting for agent response…',
    'processing':'Agent is preparing a response…', 'responding':'Receiving agent response…',
    'retrying':'Agent is retrying its response…', 'finishing':'Finishing agent request…',
    'inspecting':'Inspecting project files…', 'searching':'Searching project files…',
    'acquiring':'Copying the selected source…', 'saving':'Saving the prepared change…',
    'validating':'Checking the proposed app…', 'complete':'Finishing agent request…',
    'runtime_version':'Checking the diagnostic runtime…', 'validate_manifest':'Checking a manifest…',
    'diagnostics':'Reviewing recorded diagnostics…', 'source_facts':'Reviewing recorded source facts…',
    'failed':'Resolving agent request…',
}


def age(value,now):
    try:return max(0,int(now-datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()))
    except (TypeError,ValueError,AttributeError):return 0


def caption(activity,now=None):
    now=datetime.now(timezone.utc).timestamp() if now is None else now
    seconds=age(activity.get('startedAt'),now);phase=activity.get('phase','waiting')
    text=PHASES.get(phase,PHASES['waiting'])
    if seconds>=60:
        if phase in ('starting','waiting','processing','responding') and age(activity.get('updatedAt'),now)>=60:
            text='Still waiting for the agent…'
        text+=' · '+str(seconds//60)+'m '+str(seconds%60).zfill(2)+'s'
    return text


def details_text(details):
    lines=['This report contains lifecycle metadata, not provider output or private reasoning.']
    for key,title in [('code','Outcome'),('layer','Layer'),('lastActivePhase','Last observed phase'),
                      ('model','Model'),('requestId','Request'),('runId','Agent run')]:
        value=details.get(key)
        if isinstance(value,str) and value:lines.append(title+': '+value[:357])
    for key,title in [('elapsedMs','Agent response elapsed'),('requestElapsedMs','Whole request elapsed'),('deadlineMs','Per-response limit'),
                      ('lastEventMs','Last event'),('lastProviderActivityMs','Last provider activity')]:
        value=details.get(key)
        if isinstance(value,(int,float)) and value>=0:lines.append(title+': '+str(round(value/1000,1))+'s')
    for key,title in [('events','Events received'),('streamUpdates','Stream updates'),('retries','OMP retries'),
                      ('stdoutBytes','Output bytes'),('stderrBytes','Error-channel bytes'),('promptBytes','Request bytes')]:
        value=details.get(key)
        if isinstance(value,(int,float)) and value>=0:lines.append(title+': '+str(int(value)))
    if details.get('sourceComparisonAvailable'):
        lines.append('Saved app source: '+('verified unchanged' if details.get('sourceUnchanged') else 'changed during this request'))
    else:lines.append('Saved app source: unchanged state could not be verified')
    lines.append('A quiet process does not establish a stall or a lost connection. Last activity identifies only what Centaur observed.')
    return '\n'.join(lines)
