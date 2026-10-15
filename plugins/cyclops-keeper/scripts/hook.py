#!/usr/bin/env python3
"""Observational hook: never returns context or permission decisions; failures use safe reason codes."""
import json
import os
import select
import signal
import sys
import time

sys.dont_write_bytecode = True


def main():
    recorded=False
    started=time.monotonic()
    old_handler=signal.getsignal(signal.SIGALRM)
    old_timer=signal.getitimer(signal.ITIMER_REAL)
    def expired(_signal,_frame):
        from activity import ObservationRejected
        raise ObservationRejected('observation_timeout')
    try:
        from activity import update, ObservationRejected
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
                    # Keep the configured runner's 3s limit unchanged. Reserve
                    # .6s for signal handling and the inert reply; the complete
                    # budget includes input, durability and optional adapters.
                    signal.signal(signal.SIGALRM,expired)
                    remaining=2.4-(time.monotonic()-started)
                    if remaining<=0:expired(None,None)
                    signal.setitimer(signal.ITIMER_REAL,remaining)
                    receipt=update(data, payload)
                    recorded=isinstance(receipt,dict) and receipt.get('status')=='accepted'
                    try:
                        from launcher_link import observe as attach_launcher
                        attach_launcher(payload)
                    except ObservationRejected:
                        raise
                    except Exception:
                        pass
                break
    except Exception as error:
        from activity import ObservationRejected
        reason=str(error) if isinstance(error,ObservationRejected) else 'storage_error' if isinstance(error,OSError) else 'observer_error'
        # No session/call ID, path, tool arguments, prompts or exception detail.
        print('Keeper observer: '+reason+('; observation recorded; hook incomplete.' if recorded else '; event not acknowledged.'),file=sys.stderr)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,old_handler)
        if old_timer[0]:signal.setitimer(signal.ITIMER_REAL,*old_timer)
    # Stop requires a JSON object. The same inert object works for every hook.
    print('{}')


if __name__ == '__main__':
    main()
