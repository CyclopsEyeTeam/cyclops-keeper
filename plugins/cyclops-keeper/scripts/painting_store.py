"""Strict shared paintings. No expression, observer, terminal or installation writes."""
from contextlib import contextmanager
import copy
import fcntl
import json
import math
import os
import re
import secrets
import stat
import time

MAX_BYTES = 256 * 1024
OWNERS = ('keeper', 'spark', 'prism')
KINDS = ('line', 'curve', 'dot', 'ring', 'arc', 'glow', 'fill', 'spray')
PRIVATE = re.compile(
    r'(?:[~/\\]|[A-Za-z]:\\)|https?://|[\w.+-]+@[\w-]+\.[\w.]+'
    r'|\b[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}\b|\b[0-9a-fA-F]{16,}\b'
    r'|\b(?:opr|ses|run|sess|trig|req)_[A-Za-z0-9]{8,}\b'
    r'|\b(?:prompt|reasoning|tool result|tool output|session id|api key|password)\s*:', re.I)


def number(v, lo, hi, field, integer=False):
    if type(v) not in (int, float) or not lo <= v <= hi or not math.isfinite(v) or (integer and type(v) is not int):
        raise ValueError('Invalid ' + field)


def text(v, limit, field, empty=False):
    if (not isinstance(v, str) or len(v) > limit or (not empty and not v.strip())
            or v != v.strip() or any(not c.isprintable() for c in v) or PRIVATE.search(v)):
        raise ValueError('Invalid or potentially private ' + field)


def validate(raw, owner='keeper', reading=False):
    """Reject whole invalid compositions; never clamp. Folder credit is authoritative on read."""
    if owner not in OWNERS or not isinstance(raw, dict):
        raise ValueError('Invalid painting')
    if reading:
        # Keep only a bounded numeric usage count, never arbitrary metadata.
        tokens=raw.get('tokens')
        raw = {k:v for k,v in raw.items() if k not in ('tokens', 'v')}
        if type(tokens) is int and 0<=tokens<=1000000000:raw['tokens']=tokens
    required = {'title', 'mood', 'mirror', 'marks', 'at'}
    allowed = required | {'model', 'by', 'shape', 'thought', 'opening', 'tokens'}
    if set(raw) - allowed or not required <= set(raw):
        raise ValueError('Unknown or missing painting fields')
    if not reading and not {'model', 'by', 'shape'} <= set(raw):
        raise ValueError('Missing painting identity or shape')
    text(raw['title'], 48, 'title'); text(raw['mood'], 24, 'mood')
    if 'thought' in raw: text(raw['thought'], 160, 'thought', empty=True)
    if 'model' in raw: text(raw['model'], 32, 'model', empty=True)
    if not reading and (raw.get('by') != 'keeper' or raw.get('model') != 'keeper'):
        raise ValueError('Only Keeper paintings may be saved')
    if 'by' in raw and not isinstance(raw['by'], str): raise ValueError('Invalid credit')
    if raw.get('shape', 'wide') not in ('wide', 'square', 'tall') or raw['mirror'] not in (None, 'x', 'y', 'xy'):
        raise ValueError('Invalid shape or mirror')
    if 'opening' in raw and type(raw['opening']) is not bool: raise ValueError('Invalid opening')
    if 'tokens' in raw:number(raw['tokens'],0,1000000000,'token count',integer=True)
    number(raw['at'], .000001, 9999999999, 'timestamp')
    marks = raw['marks']
    if not isinstance(marks, list) or not 1 <= len(marks) <= 96: raise ValueError('Provide 1-96 marks')
    for m in marks:
        if not isinstance(m, dict) or m.get('k') not in KINDS: raise ValueError('Unknown mark kind')
        k = m['k']; needed = {'k', 'c', 'a'}
        needed |= {'pts', 'grad' if k == 'fill' else 'w'} if k in ('line', 'curve', 'fill') else {'x', 'y', 'r'}
        if k in ('ring', 'arc'): needed.add('w')
        if k == 'arc': needed |= {'a0', 'a1'}
        if k == 'spray': needed |= {'n', 's'}
        optional = {'c2'} | ({'seed'} if k == 'spray' else set())
        if not needed <= set(m) or set(m) - needed - optional: raise ValueError('Unknown or missing mark fields')
        for key in ('c', 'c2'):
            if key not in m: continue
            if not isinstance(m[key], list) or len(m[key]) != 3: raise ValueError('Invalid colour')
            for v in m[key]: number(v, 0, 1, 'colour')
        for key, lo, hi in [('a',0,1),('x',0,1),('y',0,1),('w',.003,.12),('r',.004,.7),('a0',-4,4),('a1',-4,4),('grad',-4,4),('s',.002,.06)]:
            if key in m: number(m[key], lo, hi, key)
        for key, hi in [('n',200),('seed',999999)]:
            if key in m: number(m[key], 1, hi, key, integer=True)
        if 'pts' in m:
            pts = m['pts']
            if not isinstance(pts, list) or not (3 if k == 'fill' else 2) <= len(pts) <= 24: raise ValueError('Invalid point count')
            for p in pts:
                if not isinstance(p, list) or len(p) != 2: raise ValueError('Invalid point')
                for v in p: number(v, 0, 1, 'point')
    out = copy.deepcopy(raw)
    if reading: out['by'] = owner; out.setdefault('shape', 'wide')
    return out


def decode(data, limit=MAX_BYTES):
    if len(data) > limit: raise ValueError('Painting exceeds 256 KiB')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    def invalid(_): raise ValueError('Non-finite JSON value')
    try: return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)
    except (UnicodeError, RecursionError) as e: raise ValueError('Invalid painting JSON') from e


@contextmanager
def open_project(path):
    """Explicit CLI path; MCP instead supplies an inherited, verified project descriptor."""
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try: yield fd
    finally: os.close(fd)


@contextmanager
def folder(project, owner, create=False):
    if owner not in OWNERS or (create and owner != 'keeper'): raise ValueError('Invalid painting owner')
    name = owner + '-paintings'
    if create:
        try: os.mkdir(name, 0o700, dir_fd=project)
        except FileExistsError: pass
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=project)
    try: yield fd
    finally: os.close(fd)


def load(fd, name, owner):
    if '/' in name or not name.endswith('.json'): raise ValueError('Invalid painting filename')
    filefd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC | getattr(os, 'O_NOATIME', 0), dir_fd=fd)
    with os.fdopen(filefd, 'rb') as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES: raise ValueError('Unsafe painting file')
        return validate(decode(f.read(MAX_BYTES + 1)), owner, reading=True)


def entries(fd):
    # Bound directory work; refuse saves rather than choose a wrong sequence number.
    out = []
    with os.scandir(fd) as scan:
        for entry in scan:
            out.append(entry.name)
            if len(out) > 10000: raise ValueError('Painting folder is too large')
    return sorted(out)


def read(project, owner, name=None):
    if owner not in OWNERS: raise ValueError('Invalid painting owner')
    result = []
    try:
        with folder(project, owner) as fd:
            names = [name] if name is not None else entries(fd)
            for filename in names:
                try: p = load(fd, filename, owner)
                except (OSError, ValueError, TypeError, OverflowError): continue
                result.append({'filename': filename, 'painting': p})
                if len(result) == 200: break
    except (OSError, ValueError): return []
    return result


def save(project, raw, guard=lambda: None):
    p = validate(raw)
    # Optional seed has a shared deterministic default; materialise it for a clean Studio check.
    for index, mark in enumerate(p['marks']):
        if mark['k'] == 'spray': mark.setdefault('seed', index + 1)
    p['at'] = float(p['at'])
    data = (json.dumps(p, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode()
    if len(data) > MAX_BYTES: raise ValueError('Painting exceeds 256 KiB')
    guard()
    with folder(project, 'keeper', create=True) as fd:
        deadline = time.monotonic() + 2
        while True:
            try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); break
            except BlockingIOError:
                if time.monotonic() >= deadline: raise ValueError('Painting folder is busy; retry')
                time.sleep(.005)
        try:
            names = entries(fd); highest = 0
            for name in names:
                match = re.match(r'^([0-9]+)-.*\.json$', name)
                if match: highest = max(highest, int(match.group(1)))
                try: old = load(fd, name, 'keeper')
                except (OSError, ValueError, TypeError, OverflowError): continue
                if old['title'] == p['title'] and abs(old['at'] - p['at']) < 1:
                    guard()
                    return name
            slug = re.sub('[^a-z0-9]+', '-', p['title'].lower()).strip('-') or 'painting'
            temp = '.tmp-' + secrets.token_hex(16)
            tmpfd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=fd)
            try:
                with os.fdopen(os.dup(tmpfd), 'wb') as f:
                    f.write(data); f.flush(); os.fsync(f.fileno())
                for _ in range(100):
                    guard()
                    current = os.stat('keeper-paintings', dir_fd=project, follow_symlinks=False)
                    pinned = os.fstat(fd)
                    if not stat.S_ISDIR(current.st_mode) or (current.st_dev,current.st_ino) != (pinned.st_dev,pinned.st_ino):
                        raise ValueError('Painting folder changed; retry')
                    highest += 1; name = f'{highest:02d}-{slug}.json'
                    try: os.link(f'/proc/self/fd/{tmpfd}', name, dst_dir_fd=fd, follow_symlinks=True)
                    except FileExistsError: continue
                    os.fsync(fd)
                    return name
                raise ValueError('Painting names are busy; retry')
            finally:
                os.close(tmpfd)
                try: os.unlink(temp, dir_fd=fd)
                except FileNotFoundError: pass
        finally: fcntl.flock(fd, fcntl.LOCK_UN)
