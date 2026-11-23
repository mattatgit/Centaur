#!/usr/bin/env python3
"""Atomically advertise a CI-verified package in its public prerelease body.

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
RELEASE_TAGS = {'aarch64-linux': 'gtk4-preview', 'x86_64-linux': 'gtk4-preview-x86_64-linux'}
# Protocol 1 clients pin this historical label as their GTK update stream.
# It remains stable when the repository's development branch changes to main.


def release_tag(manifest):
    tag = RELEASE_TAGS.get(manifest.get('system'))
    if (tag is None or manifest.get('packageAttribute')!='gtk4-preview' or
        manifest.get('updateProtocol')!=1 or manifest.get('branch')!='codex/gtk4-migration' or
        manifest.get('verifiedSignedClosureDownload') is not True):
        raise ValueError('Only a verified ARM64 or x86-64 GTK4 product package can be advertised.')
    return tag


def publish(manifest,request):
    tag = release_tag(manifest)
    path='/repos/'+REPO+'/releases'
    try: previous=request('GET',path+'/tags/'+tag)
    except urllib.error.HTTPError as error:
        if error.code!=404: raise
        error.close()
        previous=None
    title = 'Centaur GTK4 development preview'
    if manifest['system'] == 'x86_64-linux': title += ' (x86-64)'
    payload={'name':title,'body':json.dumps(manifest,indent=2),
             'draft':False,'prerelease':True}
    if previous:
        try: old=json.loads(previous.get('body','{}'))
        except ValueError: old={}
        if old.get('sourceTimestamp',0)>manifest['sourceTimestamp']:
            raise ValueError('Refusing to replace a newer published update with an older run.')
        return request('PATCH',path+'/'+str(previous['id']),payload)
    return request('POST',path,dict(payload,tag_name=tag,target_commitish=manifest['sourceRevision']))


def main():
    if os.environ.get('GITHUB_REPOSITORY')!=REPO or os.environ.get('GITHUB_REF')!='refs/heads/main':
        raise SystemExit('Update publication is restricted to main.')
    manifests=[json.loads(Path(path).read_text()) for path in sys.argv[1:]]
    tags=[release_tag(manifest) for manifest in manifests]
    if set(tags)!=set(RELEASE_TAGS.values()) or len(tags)!=len(RELEASE_TAGS):
        raise SystemExit('Supply one verified manifest for each GTK4 architecture.')
    if any(manifest['sourceRevision']!=os.environ.get('GITHUB_SHA') for manifest in manifests):
        raise SystemExit('Source revision mismatch.')
    token=os.environ['GH_TOKEN']
    def request(method,path,value=None):
        req=urllib.request.Request('https://api.github.com'+path,method=method,
            data=json.dumps(value).encode() if value is not None else None,
            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
                     'Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28',
                     'User-Agent':'Centaur-GTK4-Publisher'})
        with urllib.request.urlopen(req,timeout=30) as response: return json.load(response)
    for manifest in manifests:
        result=publish(manifest,request)
        print('Published GTK4 update '+manifest['sourceRevision'][:7]+' at '+result['html_url'])


if __name__=='__main__': main()
