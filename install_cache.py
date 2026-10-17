#!/usr/bin/env python3
"""Keep old session hooks available after Codex replaces its version cache."""
import fcntl
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import tempfile


def plain(path):
    for p in [path, *path.parents]:
        if p.is_symlink():
            raise ValueError('Refusing a linked Keeper installation path')


def refresh():
    home = Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))
    base = home/'plugins/cache/cyclops-keeper/cyclops-keeper'
    state = home/'plugins/data/cyclops-keeper-install'
    plain(base); plain(state)
    state.mkdir(parents=True, exist_ok=True)
    fd = os.open(state/'install.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        # Retained rollback data is installation state, kept outside Codex's replaced cache.
        backup = Path(tempfile.mkdtemp(prefix='before-', dir=state))
        for folder in base.iterdir() if base.is_dir() else []:
            if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', folder.name):
                continue
            plain(folder)
            for p in folder.rglob('*'):
                mode = p.lstat().st_mode
                if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                    raise ValueError('Refusing a non-regular Keeper cache entry')
            shutil.copytree(folder, backup/folder.name)
        try:
            return subprocess.run(['codex', 'plugin', 'add', 'cyclops-keeper@cyclops-keeper']).returncode
        finally:
            plain(base)
            base.mkdir(parents=True, exist_ok=True)
            for saved in backup.iterdir():
                target = base/saved.name
                if not target.exists():
                    # Build fully before making the old version visible again.
                    staging = Path(tempfile.mkdtemp(prefix='.keeper-restore-', dir=base.parent))
                    shutil.copytree(saved, staging/'version')
                    os.rename(staging/'version', target)
                    staging.rmdir()


if __name__ == '__main__':
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    raise SystemExit(refresh())
