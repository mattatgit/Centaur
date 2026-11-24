"""Conversation references contain no local filenames or image bytes."""
from hashlib import sha256
from io import BytesIO
import re
from urllib.parse import parse_qs, unquote, urlsplit

MAX_IMAGE = 1024 * 1024
MAX_INPUT = 16 * MAX_IMAGE
MAX_MESSAGE = 3 * MAX_IMAGE
MAX_ITEMS = 8


def figma_reference(text):
    if not isinstance(text, str) or len(text) > 2048 or any(ord(c) < 33 or c == '\\' for c in text):
        return None
    try:
        url = urlsplit(text)
    except ValueError:
        return None
    if url.scheme != 'https' or url.netloc.lower() not in ('figma.com', 'www.figma.com') or url.fragment:
        return None
    match = re.fullmatch(r'/(?:design|file)/([A-Za-z0-9]+)(?:/branch/([A-Za-z0-9]+))?(?:/([^/]+))?/?', url.path)
    if not match:
        return None
    ids = parse_qs(url.query, keep_blank_values=True).get('node-id', [])
    if ids and (len(ids) != 1 or not re.fullmatch(r'[0-9]+[:-][0-9]+', ids[0])):
        return None
    name = unquote(match[3] or 'Figma design').replace('-', ' ').strip()
    if '/' in name or name in ('.', '..'):
        return None
    return {'type': 'figma', 'url': text, 'name': (name or 'Figma design')[:120]}


def mentions_agent(text, name):
    return bool(name and re.search(r'(?<![\w@])@'+re.escape(name)+r'(?![\w-])',text,re.I))


def mention_suffix(text, cursor, names):
    if cursor < len(text) and re.match(r'[\w-]', text[cursor]):
        return ''
    token = re.search(r'(?<![\w@])@([\w-]+)$', text[:cursor])
    if token:
        for name in names:
            prefix = token[1]
            if len(prefix) < len(name) and name[:len(prefix)].casefold() == prefix.casefold():
                return name[len(prefix):]
    return ''


def image_filename(ref):
    key, fmt = ref.get('hash', ''), ref.get('format')
    if not isinstance(key, str) or not re.fullmatch(r'[0-9a-f]{64}', key) or fmt not in ('png', 'jpeg'):
        raise ValueError('Invalid image reference.')
    return f'{key}.{fmt}'


def prepare_image(raw):
    from PIL import Image, ImageOps, UnidentifiedImageError
    if len(raw) > MAX_INPUT:
        raise ValueError('Choose an image smaller than 16 MB.')
    try:
        with Image.open(BytesIO(raw), formats=('PNG', 'JPEG', 'WEBP')) as src:
            if src.width * src.height > 16000000 or max(src.size) > 8192 or getattr(src, 'n_frames', 1) != 1:
                raise ValueError('Choose a static image up to 16 megapixels and 8192 pixels wide or high.')
            image = ImageOps.exif_transpose(src)
            alpha = image.has_transparency_data if hasattr(image, 'has_transparency_data') else ('A' in image.getbands() or 'transparency' in image.info)
            fmt = 'png' if alpha or src.format == 'PNG' else 'jpeg'
            image = image.convert('RGBA' if alpha else 'RGB')
            # Strip private EXIF/GPS and unrelated metadata from shared pixels.
            image.info.clear()
            for _ in range(12):
                out = BytesIO()
                image.save(out, format=fmt.upper(), optimize=True, **({'quality':90} if fmt == 'jpeg' else {}))
                raw = out.getvalue()
                if len(raw) <= MAX_IMAGE:
                    return {'type':'image', 'format':fmt, 'hash':sha256(raw).hexdigest()}, raw
                if fmt == 'png' and not alpha:
                    fmt = 'jpeg'
                else:
                    image.thumbnail(tuple(max(1,int(n * .78)) for n in image.size), Image.Resampling.LANCZOS)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError('Choose a readable static PNG, JPEG or WebP image.') from error
    raise ValueError('This image could not fit the attachment size limit.')


def stored_image(folder, ref):
    try:
        path = folder / image_filename(ref)
        if not any(p.is_symlink() for p in (folder.parent, folder, path)) and path.is_file() and path.stat().st_size <= MAX_IMAGE:
            return path
    except (OSError, ValueError):
        pass
    return None
