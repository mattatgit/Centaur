#!/usr/bin/env python3
"""Atomically advertise a CI-verified package in one public prerelease body.

This runs AFTER signed full-closure publication. A failed API call leaves the
previous body available; users never follow the moving development branch.
"""
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

REPO='mattatgit/Centaur'
TAG='gtk4-preview'


def publish(manifest,request):
    if (manifest.get('system')!='aarch64-linux' or manifest.get('packageAttribute')!='gtk4-preview' or
        manifest.get('updateProtocol')!=1 or manifest.get('branch')!='codex/gtk4-migration' or
        manifest.get('verifiedSignedClosureDownload') is not True):
        raise ValueError('Only a verified ARM64 GTK4 product package can be advertised.')
    path='/repos/'+REPO+'/releases'
    try: previous=request('GET',path+'/tags/'+TAG)
    except urllib.error.HTTPError as error:
        if error.code!=404: raise
        previous=None
    payload={'name':'Centaur GTK4 development preview','body':json.dumps(manifest,indent=2),
             'draft':False,'prerelease':True}
    if previous:
        try: old=json.loads(previous.get('body','{}'))
        except ValueError: old={}
        if old.get('sourceTimestamp',0)>manifest['sourceTimestamp']:
            raise ValueError('Refusing to replace a newer published update with an older run.')
        return request('PATCH',path+'/'+str(previous['id']),payload)
    return request('POST',path,dict(payload,tag_name=TAG,target_commitish=manifest['sourceRevision']))


def main():
    if os.environ.get('GITHUB_REPOSITORY')!=REPO or os.environ.get('GITHUB_REF')!='refs/heads/codex/gtk4-migration':
        raise SystemExit('Update publication is restricted to the GTK4 development branch.')
    manifest=json.loads(Path(sys.argv[1]).read_text())
    if manifest['sourceRevision']!=os.environ.get('GITHUB_SHA'): raise SystemExit('Source revision mismatch.')
    token=os.environ['GH_TOKEN']
    def request(method,path,value=None):
        req=urllib.request.Request('https://api.github.com'+path,method=method,
            data=json.dumps(value).encode() if value is not None else None,
            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
                     'Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28',
                     'User-Agent':'Centaur-GTK4-Publisher'})
        with urllib.request.urlopen(req,timeout=30) as response: return json.load(response)
    result=publish(manifest,request)
    print('Published GTK4 update '+manifest['sourceRevision'][:7]+' at '+result['html_url'])


if __name__=='__main__': main()
