"""Compressed download bytes from Nix's internal-json file-transfer activities.

Nix activity 101 reports HTTP payload bytes; copy-path activity 100 reports
uncompressed NAR bytes and must not be added to the download counter.
See Nix 2.28.4 libutil/logging.hh and libstore/filetransfer.cc.
"""
import json
import re
import time
from urllib.parse import urljoin, urlparse


def path_info(value):
    # Nix 2.19+ returns an object; older versions used a list with path fields.
    if isinstance(value,list): value={item['path']:item for item in value}
    if not isinstance(value,dict) or not all(re.fullmatch(r'/nix/store/[0-9a-df-np-sv-z]{32}-[^\s/]+',p) for p in value):
        raise ValueError('Invalid path metadata')
    return value


def download_plan(cache,remote,local):
    plan={}
    for path,info in path_info(remote).items():
        if local.get(path) is not None: continue
        size=info['downloadSize']; url=info['url']
        if type(size) is not int or size<=0 or not isinstance(url,str): raise ValueError('Missing download size')
        plan[urljoin(cache+'/',url)]=size
    return plan


def progress_message(done,total):
    if total is None: return f'Downloaded {done/1_000_000:.1f} MB'
    return f'Downloaded {done/1_000_000:.1f} of {total/1_000_000:.1f} MB'


class DownloadProgress:
    def __init__(self,cache,plan,callback):
        self.cache=cache; self.plan=plan; self.callback=callback
        self.activities={}; self.received={}; self.last_time=0; self.last_value=None
        self.flush()

    def feed(self,line):
        try:
            if not line.startswith('@nix '): return
            event=json.loads(line[5:])
            if not isinstance(event,dict): return
            activity=event.get('id')
            if type(activity) is not int: return
            if event.get('action')=='start' and event.get('type')==101:
                url=event['fields'][0]
                if not isinstance(url,str): return
                if self.plan is not None:
                    if url not in self.plan: return
                elif not (url.startswith(self.cache+'/') and '/nar/' in urlparse(url).path): return
                self.activities[activity]=url
            elif event.get('action')=='result' and event.get('type')==105 and activity in self.activities:
                done=event['fields'][0]
                if type(done) is not int or done<0: return
                url=self.activities[activity]
                if self.plan is not None: done=min(done,self.plan[url])
                # Repeated events/retries for a NAR must not inflate the count.
                self.received[url]=max(done,self.received.get(url,0))
                self.tick()
            elif event.get('action')=='stop': self.activities.pop(activity,None)
        except (ValueError,KeyError,TypeError,IndexError):
            pass  # Unknown diagnostics must never prevent an otherwise valid update.

    def tick(self):
        if time.monotonic()-self.last_time>=.2: self.flush()

    def flush(self):
        value=(sum(self.received.values()),None if self.plan is None else sum(self.plan.values()))
        if value!=self.last_value:
            self.callback(*value); self.last_value=value; self.last_time=time.monotonic()
