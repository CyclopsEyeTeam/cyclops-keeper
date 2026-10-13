#!/usr/bin/env python3
"""Installer-owned, reversible Bash registration; no separate setup mode."""
import argparse
import os
from pathlib import Path
import re
import shlex
import stat
import tempfile

START = '\n# >>> Cyclops Keeper shell >>>\n'
END = '# <<< Cyclops Keeper shell <<<\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['check', 'install', 'remove'])
    parser.add_argument('--integration', type=Path)
    parser.add_argument('--rc', type=Path, default=Path.home() / '.bashrc')
    args = parser.parse_args()
    path = args.rc
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            parser.error('Bash startup file must be a regular file owned by you.')
        original = path.read_text()
        mode = stat.S_IMODE(info.st_mode)
    else:
        original, mode = '', 0o600
    clean = original
    if START in clean or END in clean:
        if clean.count(START) != 1 or clean.count(END) != 1:
            parser.error('Keeper startup markers are incomplete; no file was changed.')
        start = clean.index(START)
        end = clean.index(END) + len(END)
        if end <= start:
            parser.error('Keeper startup markers are out of order; no file was changed.')
        clean = clean[:start] + clean[end:]
    if args.action in {'check', 'install'}:
        # Inspect ordinary direct definitions without executing arbitrary
        # startup code. Runtime guards cover indirect/sourced definitions.
        conflict = re.compile(r'(?m)^\s*(?:alias\s+(?:--\s+)?codex\s*=|(?:function\s+codex\b|codex\s*\(\s*\))\s*(?:\(\s*\))?\s*\{)')
        texts = [clean]
        aliases = path.parent / '.bash_aliases'
        if aliases.is_file():
            texts.append(aliases.read_text())
        if any(conflict.search(text) for text in texts):
            parser.error('An existing codex alias or function conflicts with Keeper. Remove that customisation before installing; it was preserved.')
    if args.action == 'check':
        return
    if args.action == 'install':
        if args.integration is None:
            from launcher import installed_plugin
            try:
                args.integration = installed_plugin() / 'scripts/integration.bash'
            except ValueError as error:
                parser.error(str(error))
        if not args.integration.is_file():
            parser.error('Installed Keeper terminal integration is missing.')
        integration = shlex.quote(str(args.integration.resolve()))
        clean += START + f'if [ -r {integration} ]; then\n    source {integration}\nfi\n' + END
    if clean == original:
        print('Keeper Bash setup already matches; no change.')
        return
    descriptor, name = tempfile.mkstemp(prefix='.keeper-shell-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(clean)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    print('Keeper terminal commands ' + ('installed. Open a new Bash terminal.'
                                  if args.action == 'install' else 'removed. Open a new terminal.'))


if __name__ == '__main__':
    main()
