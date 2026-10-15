"""Optional local view preferences, private to a verified live launch."""
import json
import os
from pathlib import Path
import stat
from launcher_link import alive, atomic, read_attachment


def owned(path):
    path=Path(path)
    try:
        info=path.parent.lstat()
        if (not path.parent.name.startswith('keeper-') or not stat.S_ISDIR(info.st_mode)
                or info.st_uid!=os.getuid() or info.st_mode & 0o077):return None
        value=read_attachment(path)
        return value['owner'] if value and alive(value.get('owner')) else None
    except (OSError,ValueError,TypeError,KeyError):return None


def load(path):
    owner=owned(path);file=Path(path).parent/'.keeper-view.json'
    if not owner:return {}
    try:
        if file.is_symlink() or file.stat().st_size>1024:return {}
        value=json.loads(file.read_text())
        if value.get('owner')!=owner:return {}
        if type(value.get('calm')) is not bool or type(value.get('reduced_motion')) is not bool:return {}
        return {key:value[key] for key in ['calm','reduced_motion']}
    except (OSError,ValueError,TypeError,AttributeError):return {}


def save(path,calm,reduced_motion):
    owner=owned(path)
    if not owner:return False
    try:
        atomic(Path(path).parent/'.keeper-view.json',{'v':1,'owner':owner,'calm':bool(calm),'reduced_motion':bool(reduced_motion)})
        return True
    except OSError:return False
