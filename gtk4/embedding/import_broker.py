"""Bounded read-only import tools. This module never starts a process.

All paths are opened relative to verified directory descriptors with NOFOLLOW.
The coordinator chooses root/scope; source text is never evaluated or imported.
"""
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import time

from import_policy import ImportError, MAX_FILES, TOKEN, excluded, relative, visible

MAX_RESULT = 96000
MAX_SCAN = 512000


class Tree:
    def __init__(self, root):
        self.fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in Path(root).absolute().parts[1:]:
                new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.fd)
                os.close(self.fd); self.fd = new
        except BaseException:
            os.close(self.fd); raise
        self.deadline = time.monotonic()+5
        self.scanned = 0
        self.omitted = 0

    def close(self):
        os.close(self.fd)

    def check(self):
        if time.monotonic()>self.deadline:
            raise ImportError('Inspection reached its time limit. Choose a smaller folder.', code='time_limit')

    def open(self, name='', directory=False):
        self.check()
        parts = relative(name).parts if name else ()
        if excluded(PurePosixPath(name)):
            raise ImportError('Private or generated files are omitted.', code='omitted')
        fd = os.dup(self.fd)
        try:
            for i, part in enumerate(parts):
                flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                if directory or i<len(parts)-1: flags |= os.O_DIRECTORY
                new = os.open(part, flags, dir_fd=fd)
                os.close(fd); fd = new
            mode = os.fstat(fd).st_mode
            if not (stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)):
                raise ImportError('That file is unavailable.', code='unavailable')
            return fd
        except BaseException:
            os.close(fd); raise

    def entries(self, path):
        fd = self.open(path, directory=True)
        try:
            result=[]
            with os.scandir(fd) as entries:
                for entry in entries:
                    self.check(); self.scanned+=1
                    if self.scanned>MAX_FILES:
                        raise ImportError('Inspection reached its entry limit. Choose a smaller folder.', code='entry_limit')
                    name = path+'/'+entry.name if path else entry.name
                    try: relative(name)
                    except ImportError: self.omitted+=1; continue
                    if excluded(PurePosixPath(name)): self.omitted+=1; continue
                    # lstat never follows symlinks or opens special files.
                    mode=entry.stat(follow_symlinks=False).st_mode
                    if stat.S_ISDIR(mode): kind='directory'
                    elif stat.S_ISREG(mode): kind='file'
                    else: self.omitted+=1; continue
                    result.append({'path':name,'type':kind})
            return sorted(result,key=lambda x:x['path'])
        finally: os.close(fd)

    def text(self, name):
        fd=self.open(name)
        try:
            with os.fdopen(fd,'rb',closefd=False) as stream: raw=stream.read(MAX_SCAN+1)
            self.check()
            if b'\x00' in raw: raise ImportError('Binary file omitted.', code='binary')
            try: text=raw[:MAX_SCAN].decode('utf-8')
            except UnicodeError: raise ImportError('Binary file omitted.', code='binary') from None
            if TOKEN.search(text): raise ImportError('Potential credentials omitted.', code='omitted')
            return text, len(raw)>MAX_SCAN
        finally: os.close(fd)


def validate(tool):
    if not isinstance(tool,dict): raise ImportError('Choose an inspection operation.', code='invalid_request')
    op=tool.get('operation')
    keys={'list':{'path','cursor'},'read':{'paths','startLine','lineCount'},'search':{'path','query'}}
    if op not in keys or set(tool)-keys[op]-{'operation','scope'}:
        raise ImportError('That inspection operation is not available.', code='invalid_request')
    if tool.get('scope','source') not in ('source','adaptation'):
        raise ImportError('Choose source or adaptation.', code='invalid_request')
    if op in ('list','search'):
        if tool.get('path','')!='': relative(tool['path'])
    if op=='list' and (not isinstance(tool.get('cursor',''),str) or len(tool.get('cursor',''))>64):
        raise ImportError('That page is unavailable.', code='invalid_request')
    if op=='read':
        paths=tool.get('paths')
        if not isinstance(paths,list) or not 1<=len(paths)<=12:
            raise ImportError('Inspect up to 12 files at a time.', code='invalid_request')
        for path in paths: relative(path)
        for key,default,limit in [('startLine',1,100000),('lineCount',200,1000)]:
            n=tool.get(key,default)
            if type(n) is not int or not 1<=n<=limit:
                raise ImportError('Choose a bounded line range.', code='invalid_request')
    if op=='search' and (not isinstance(tool.get('query'),str) or not 1<=len(tool['query'])<=200
                         or any(ord(c)<32 for c in tool['query']) or TOKEN.search(tool['query'])):
        raise ImportError('Choose a short literal search.', code='invalid_request')
    return tool


def execute(root, tool, output=None):
    op=tool.get('operation','') if isinstance(tool,dict) else ''
    result={'schemaVersion':1,'operation':op,'scope':tool.get('scope','source') if isinstance(tool,dict) else 'source',
            'ok':False,'sourceAvailable':False,'truncated':False,'omissionPolicy':'Private, generated, symbolic-link and special files are omitted.'}
    tree=None
    try:
        validate(tool)
        base=Path(root)/'source'
        if result['scope']=='adaptation':
            parts=relative(output).parts
            if len(parts)!=2 or parts[0]!='adaptations':
                raise ImportError('No adaptation is available.', code='source_unavailable')
            base=Path(root).joinpath(*parts)
        tree=Tree(base); result['sourceAvailable']=True
        if op=='list':
            entries=tree.entries(tool.get('path',''))
            digest=hashlib.sha256(json.dumps([result['scope'],tool.get('path',''),entries]).encode()).hexdigest()[:16]
            cursor=tool.get('cursor',''); offset=0
            if cursor:
                prefix,sep,number=cursor.partition(':')
                if prefix!=digest or not sep or not number.isdecimal() or not 0<int(number)<=len(entries):
                    raise ImportError('The folder changed. Inspect its first page again.', code='stale_cursor')
                offset=int(number)
            page=[]; size=0
            for entry in entries[offset:offset+200]:
                size+=len(json.dumps(entry).encode())
                if size>70000: break
                page.append(entry)
            end=offset+len(page); result['truncated']=end<len(entries)
            result['data']={'entries':page,'cursor':f'{digest}:{end}' if result['truncated'] else ''}
        elif op=='read':
            files={}; size=0
            for name in tool['paths']:
                try:
                    text,scan_limited=tree.text(name)
                    lines=text.splitlines(keepends=True); start=tool.get('startLine',1)-1
                    chosen=''.join(lines[start:start+tool.get('lineCount',200)])
                    raw=chosen.encode(); clipped=raw[:min(24000,max(0,70000-size))].decode('utf-8','ignore')
                    size+=len(clipped.encode())
                    truncated=scan_limited or start+tool.get('lineCount',200)<len(lines) or clipped!=chosen
                    files[name]={'text':visible(clipped),'startLine':start+1,'truncated':truncated,'scanTruncated':scan_limited}
                    result['truncated'] |= truncated
                except (ImportError,OSError) as error:
                    files[name]={'error':error_code(error)}
            result['data']={'files':files}
        else:
            matches=[]; scanned=0; size=0; omitted=0; pending=[tool.get('path','')]
            while pending:
                entries=tree.entries(pending.pop())
                for entry in entries:
                    if entry['type']=='directory': pending.append(entry['path']); continue
                    try: text,limited=tree.text(entry['path'])
                    except (ImportError,OSError): omitted+=1; continue
                    scanned+=len(text.encode()); result['truncated'] |= limited
                    for number,line in enumerate(text.splitlines(),1):
                        if tool['query'] not in line: continue
                        excerpt=visible(line[:500]); size+=len(excerpt.encode())+len(entry['path'].encode())+80
                        matches.append({'path':entry['path'],'line':number,'text':excerpt})
                        if len(matches)>=100 or size>=65000: break
                    if len(matches)>=100 or size>=65000 or scanned>=8*1024*1024: break
                if len(matches)>=100 or size>=65000 or scanned>=8*1024*1024:
                    result['truncated']=True; break
            result['data']={'matches':matches,'omitted':omitted,'scannedBytes':scanned}
        result['ok']=True
        result['omittedEntries']=tree.omitted
        if len(json.dumps(result).encode())>MAX_RESULT:
            raise ImportError('The result is too large. Choose a smaller range.', code='output_limit')
    except (ImportError,OSError,TypeError) as error:
        result.pop('data',None); result['ok']=False; result['error']={'code':error_code(error)}
    finally:
        if tree: tree.close()
    return result


def error_code(error):
    if isinstance(error,ImportError): return error.code
    if isinstance(error,OSError) and error.errno in (errno.ELOOP,errno.ENOTDIR): return 'unsafe_path'
    return 'unavailable'
