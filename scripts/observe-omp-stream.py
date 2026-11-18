"""Pass-through observer. Retains only safe aggregate event/shape metadata."""
import os,sys,json,time,subprocess,collections,re,hashlib
from pathlib import Path

def main():
    out=Path(os.environ['CENTAUR_OBSERVATIONS']);out.mkdir(mode=0o700,parents=True,exist_ok=True)
    index=len(list(out.glob('run-*.json')))+1;dest=out/f'run-{index}.json';start=time.monotonic()
    counts=collections.Counter();deltas=collections.Counter();timeline=[];text='';bytes_out=0;stderr_bytes=0;last_write=0;prompt={};parsed={};last_stage=''
    for arg in sys.argv[1:]:
     if arg.startswith('@') and arg.endswith('.txt'):
      data=Path(arg[1:]).read_text();prompt['bytes']=len(data.encode())
      try:
       project=data.split('PROJECT AND CONVERSATION:\n',1)[1].split('\n\nCURRENT ',1)[0];s=json.loads(project)
       prompt['fieldBytes']={k:len(json.dumps(v,ensure_ascii=False,separators=(',',':')).encode()) for k,v in s.items()}
       blob=data.split('\n\nCURRENT GTK4 BUNDLE:\n',1)[1] if '\n\nCURRENT GTK4 BUNDLE:\n' in data else ''
       if blob:
        _,end=json.JSONDecoder().raw_decode(blob);prompt['currentSourceJsonBytes']=len(blob[:end].encode())
      except (ValueError,IndexError):prompt['shapeUnavailable']=True
    allowed={'session','agent_start','turn_start','message_start','message_update','message_end','turn_end','agent_end','auto_retry_start','auto_retry_end','tool_execution_start','tool_execution_end','tool_execution_update'}
    fields=('app.py','app.ui','style.css','index.html')
    def snapshot(force=False):
     nonlocal last_write,last_stage
     now=time.monotonic()
     if not force and now-last_write<.5:return
     stages=[(m.start(),m.group(1)) for m in re.finditer(r'(?<!\\)"(app\.py|app\.ui|style\.css|index\.html)"\s*:',text)]
     stage=stages[-1][1] if stages else None
     if stage!=last_stage:
      timeline.append({'seconds':round(now-start,3),'responseField':stage});last_stage=stage
     summary={'seconds':round(now-start,3),'prompt':prompt,'events':dict(counts),'streamCategories':dict(deltas),'stdoutBytes':bytes_out,'responseTextBytes':len(text.encode()),'responseTextCharacters':len(text),'responseLineBreaks':text.count('\\n'),'responseFieldsObserved':list(dict.fromkeys(s for _,s in stages)),'timeline':timeline[-60:],'parsedResponse':parsed,'rawReasoningRetained':False,'rawProviderOutputStored':False,'toolFlagsDisabled':all(x in sys.argv for x in ('--no-tools','--no-extensions','--no-skills','--no-rules'))}
     temp=dest.with_suffix('.pending');temp.write_text(json.dumps(summary,indent=2)+'\n');temp.replace(dest);last_write=now
    p=subprocess.Popen([os.environ['CENTAUR_REAL_OMP'],*sys.argv[1:]],stdin=sys.stdin,stdout=subprocess.PIPE,stderr=sys.stderr)
    try:
     for line in p.stdout:
      bytes_out+=len(line)
      try:e=json.loads(line)
      except ValueError:e={}
      kind=e.get('type','unknown');key=kind if kind in allowed else 'other';counts[key]+=1
      if counts[key]==1 and kind in allowed and kind!='message_update':timeline.append({'seconds':round(time.monotonic()-start,3),'event':kind})
      if kind=='message_update':
       u=e.get('assistantMessageEvent',{});t=u.get('type','unknown');deltas[t if t in ('text_start','text_delta','text_end','thinking_start','thinking_delta','thinking_end','toolcall_start','toolcall_delta','toolcall_end','start','done','error') else 'other']+=1
       if t=='text_delta' and len(text)<2*1024*1024:text+=u.get('delta','')[:2*1024*1024-len(text)]
      if kind=='message_end' and e.get('message',{}).get('role')=='assistant':
       msg=e['message'];final=''.join(b.get('text','') for b in msg.get('content',[]) if b.get('type')=='text')
       try:
        obj=json.loads(final)
        if not isinstance(obj,dict):raise ValueError('Response shape')
        parsed={'kind':obj.get('kind') if obj.get('kind') in ('question','proposal','inspect','retry','restore','artifact','patch') else 'other','validJson':True,'outputBytes':len(final.encode()),'fileBytes':{k:len(v.encode()) for k,v in obj.get('gtk',{}).get('files',{}).items() if k in fields and isinstance(v,str)},'editCount':len(obj.get('edits',[])),'editedFiles':sorted({e.get('file') for e in obj.get('edits',[]) if e.get('file') in fields}),'toolOperation':obj.get('tool',{}).get('operation') if obj.get('tool',{}).get('operation') in ('read','list','search','source_facts','diagnostics','runtime_version','validate_manifest') else None}
       except (ValueError,TypeError,AttributeError):parsed={'validJson':False,'outputBytes':len(final.encode())}
       parsed['stopReason']=msg.get('stopReason') if msg.get('stopReason') in ('stop','length','error','aborted','toolUse') else 'other'
       usage=msg.get('usage',{});parsed['usage']={k:v for k,v in usage.items() if k in ('input','output','cacheRead','cacheWrite','totalTokens') and isinstance(v,(int,float))}
      snapshot();sys.stdout.buffer.write(line);sys.stdout.buffer.flush()
     p.wait();snapshot(True)
    finally:
     if p.poll() is None:p.terminate();p.wait(timeout=3)
    sys.exit(p.returncode)


if __name__ == "__main__":
    main()
