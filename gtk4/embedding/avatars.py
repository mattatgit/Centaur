"""Generate a small, private sharing copy of a locally uploaded avatar."""
from io import BytesIO
from pathlib import Path
import re
import tempfile

from PIL import Image, ImageOps


def prepare_avatar(original: Path, destination: Path):
    with Image.open(original) as source:
        if max(source.size)>8192 or source.width*source.height>32_000_000:
            raise ValueError('Avatar dimensions are too large')
        avatar=ImageOps.exif_transpose(source).convert('RGBA')
        avatar.thumbnail((256,256),Image.Resampling.LANCZOS)
    output=BytesIO()
    if avatar.getchannel('A').getextrema()[0]<255:
        avatar.save(output,format='PNG',optimize=True)
    else:
        avatar.convert('RGB').save(output,format='JPEG',quality=88,optimize=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent,prefix='.avatar-wire-',delete=False) as file:
        pending=Path(file.name)
        file.write(output.getvalue())
    try:
        pending.replace(destination)
    finally:
        pending.unlink(missing_ok=True)


def shared_avatar(root, digest):
    if isinstance(digest,str) and re.fullmatch(r'[a-f0-9]{64}',digest):
        path=root/'avatars'/digest
        if path.is_file():
            return path
    return None
