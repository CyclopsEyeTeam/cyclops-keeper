#!/usr/bin/env python3
"""Observational hook: never returns context, permission decisions, or errors."""
import json
import os
import select
import sys
import time

sys.dont_write_bytecode = True


def main():
    try:
        from activity import update
        data = os.environ.get('PLUGIN_DATA')
        if data:
            # Decode one complete object without depending on the runner closing
            # stdin. Installed Unix runtimes can keep their input pipe open.
            raw = bytearray()
            deadline = time.monotonic() + .7
            while len(raw) <= 2 * 1024 * 1024:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([sys.stdin], [], [], remaining)[0]:
                    break
                chunk = os.read(sys.stdin.fileno(), 8192)
                if not chunk:
                    break
                raw.extend(chunk)
                if len(raw) > 2 * 1024 * 1024:
                    break
                try:
                    payload = json.loads(raw)
                except (ValueError, UnicodeError):
                    continue
                if isinstance(payload, dict):
                    update(data, payload)
                break
    except Exception:
        # A decorative observer must never impede Codex or leak event contents.
        pass
    # Stop requires a JSON object. The same inert object works for every hook.
    print('{}')


if __name__ == '__main__':
    main()
