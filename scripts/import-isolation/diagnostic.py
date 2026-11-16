"""Trusted fixed diagnostics inside the boundary; never import project modules."""
import json
from pathlib import Path
import sys
import tomllib

operation=sys.argv[1]
if operation=='validate_manifest':
    path=Path('/source')/sys.argv[2]
    raw=path.read_bytes()
    if len(raw)>240000:raise SystemExit(2)
    try:
        text=raw.decode('utf-8')
        if path.suffix=='.json':json.loads(text)
        elif path.suffix=='.toml':tomllib.loads(text)
        else:raise SystemExit(2)
        result={'valid':True,'format':path.suffix[1:]}
    except (json.JSONDecodeError,tomllib.TOMLDecodeError,UnicodeError) as error:
        # Parser messages may quote source contents. Only numerical positions
        # and a stable code leave the boundary; never return parsed values.
        result={'valid':False,'format':path.suffix[1:],'code':'invalid_manifest'}
        for key in ('lineno','colno'):
            number=getattr(error,key,None)
            if type(number) is int:result[{'lineno':'line','colno':'column'}[key]]=number
    except (RecursionError,ValueError):
        result={'valid':None,'format':path.suffix[1:],'code':'parse_limit'}
    print(json.dumps(result))
else:raise SystemExit(2)
