"""Shared source policy. No project imports, evaluation or command execution."""
from pathlib import PurePosixPath
import re

MAX_FILES, MAX_BYTES, MAX_FILE = 20000, 128*1024*1024, 16*1024*1024
SKIP = {'.git', '.hg', '.svn', 'node_modules', '.venv', 'venv', '__pycache__',
        '.ssh', '.aws', '.gnupg', '.centaur', '.omp', '.pi', '.codex', '.config',
        '.docker', 'result', 'target', 'build', 'dist'}
SECRET = re.compile(r'(^\.env($|\.)|credentials|secrets?\.|^id_(rsa|ed25519)|\.(pem|key|p12|pfx)$|^\.(netrc|npmrc|gitconfig|git-credentials|pypirc|authinfo)$)', re.I)
TOKEN = re.compile(r'(?:github_pat_|gh[pousr]_|sk-[A-Za-z0-9]|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY|(?i:api[_-]?key|access[_-]?token|password)\s*[=:]\s*["\']?[^\s"\']{12,})')


class ImportError(ValueError):
    def __init__(self, message, diagnostic=None, code='source_unavailable'):
        super().__init__(message)
        self.diagnostic, self.code = diagnostic, code


def relative(value):
    if (not isinstance(value, str) or not value or len(value)>1024
        or value.startswith('/') or any(p in ('', '.', '..') for p in value.split('/'))
        or len(value.split('/'))>32 or '\\' in value or any(ord(c)<32 or ord(c)==127
            or c in '\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069' for c in value)):
        raise ImportError('That file is outside the imported source.', code='invalid_path')
    return PurePosixPath(value)


def excluded(path):
    return any(p in SKIP or SECRET.search(p) or TOKEN.search(p) for p in path.parts)


def visible(text):
    """Keep source text as data; remove terminal/bidi controls from excerpts."""
    return ''.join(c if c in '\n\t' or (ord(c)>=32 and ord(c)!=127
                   and c not in '\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069')
                   else '\\u%04x'%ord(c) for c in text)
