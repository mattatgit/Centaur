"""Compressed download bytes from Nix's internal-json file-transfer activities.

Nix activity 101 reports HTTP payload bytes; copy-path activity 100 reports
uncompressed NAR bytes and must not be added to the download counter.
See Nix 2.28.4 libutil/logging.hh and libstore/filetransfer.cc.
"""
import json
import re
import time
from urllib.parse import urljoin, urlparse, urlunparse


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
    @staticmethod
    def url_key(url):
        # Signed/temporary query parameters do not identify a different NAR.
        # This is display accounting only; Nix still verifies the archive.
        parts=urlparse(url)
        return urlunparse((parts.scheme.lower(),parts.netloc.lower(),parts.path,'','',''))

    def __init__(self,cache,plan,callback):
        self.cache=self.url_key(cache).rstrip('/')
        self.plan=None if plan is None else {self.url_key(url):size for url,size in plan.items()}
        self.callback=callback; self.unplanned=False
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
                url=self.url_key(url)
                known=self.plan is not None and url in self.plan
                if not known:
                    if not (url.startswith(self.cache+'/nar/')): return
                    # A republished archive or stale metadata can disagree with
                    # the plan. Never silently discard its real byte events.
                    # Its relationship to the old total is unknown, so stop
                    # displaying that total rather than inventing a percentage.
                    self.unplanned=True
                self.activities[activity]=url
            elif event.get('action')=='result' and event.get('type')==105 and activity in self.activities:
                done=event['fields'][0]
                if type(done) is not int or done<0: return
                url=self.activities[activity]
                if self.plan is not None and url in self.plan: done=min(done,self.plan[url])
                # Repeated events/retries for a NAR must not inflate the count.
                self.received[url]=max(done,self.received.get(url,0))
                self.tick()
            elif event.get('action')=='stop': self.activities.pop(activity,None)
        except (ValueError,KeyError,TypeError,IndexError):
            pass  # Unknown diagnostics must never prevent an otherwise valid update.

    def tick(self):
        if time.monotonic()-self.last_time>=.2: self.flush()

    def flush(self):
        value=(sum(self.received.values()),None if self.plan is None or self.unplanned else sum(self.plan.values()))
        if value!=self.last_value:
            self.callback(*value); self.last_value=value; self.last_time=time.monotonic()
