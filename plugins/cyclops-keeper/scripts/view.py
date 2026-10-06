#!/usr/bin/env python3
"""Optional local browser presentation; no files or payloads are exposed."""
import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlsplit

sys.dont_write_bytecode = True
from activity import default_data, public_snapshot


def main():
    parser = argparse.ArgumentParser(description='Cyclops Keeper: a local Codex presence panel')
    parser.add_argument('--data', type=Path, default=default_data())
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--session', help='Pin to one full SHA-256 session hash')
    parser.add_argument('--test-feed', action='store_true', help='Visibly label disposable fixture data')
    parser.add_argument('--calm', action='store_true', help='Open with the lower-contrast Calm treatment')
    args = parser.parse_args()
    if args.session and not re.fullmatch(r'[0-9a-f]{64}', args.session):
        parser.error('--session must be a full lowercase SHA-256 session hash')
    assets = Path(__file__).resolve().parents[1] / 'assets'
    files = {'/': ('index.html', 'text/html; charset=utf-8'),
             '/keeper.css': ('keeper.css', 'text/css; charset=utf-8'),
             '/keeper.js': ('keeper.js', 'text/javascript; charset=utf-8'),
             '/keeper.svg': ('keeper.svg', 'image/svg+xml'),
             '/presence-state.mjs': ('presence-state.mjs', 'text/javascript; charset=utf-8'),
             '/colour-engine.js': ('colour-engine.js', 'text/javascript; charset=utf-8')}
    content = {route: (assets.joinpath(name).read_bytes(), kind) for route, (name, kind) in files.items()}
    content['/keeper-sound.mjs']=(assets.joinpath('keeper-sound.mjs').read_bytes(),'text/javascript; charset=utf-8')
    content['/keeper-manifest.wav']=(assets.joinpath('keeper-manifest.wav').read_bytes(),'audio/wav')

    class Handler(BaseHTTPRequestHandler):
        def reply(self, code, content=b'', kind='text/plain; charset=utf-8'):
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
                return self.reply(403)
            url = urlsplit(self.path)
            if url.path == '/':
                options = parse_qs(url.query, keep_blank_values=True)
                if any(k not in {'size', 'mono', 'calm'} for k in options) or any(
                        v not in (['tiny'], ['expanded'], ['panel']) if k == 'size' else v != ['1']
                        for k, v in options.items()):
                    return self.reply(404)
                body, kind = content['/']
                if args.test_feed:
                    fixture = public_snapshot(args.data,session=args.session)
                    fixture['sessions'] = [s for s in fixture['sessions'] if s['session'] == args.session] if args.session else fixture['sessions'][:1]
                    fixture['selection'] = 'pinned' if args.session else 'latest'
                    fixture['test_feed'] = True
                    encoded = base64.b64encode(json.dumps(fixture,separators=(',',':')).encode()).decode()
                    marker = b'<meta name="keeper-fixture" content="">'
                    body = body.replace(marker, f'<meta name="keeper-fixture" content="{encoded}">'.encode(), 1)
                return self.reply(200, body, kind)
            if self.path == '/api/state':
                snapshot = public_snapshot(args.data,session=args.session)
                snapshot['sessions'] = [s for s in snapshot['sessions'] if s['session'] == args.session] if args.session else snapshot['sessions'][:1]
                snapshot['selection'] = 'pinned' if args.session else 'latest'
                snapshot['test_feed'] = args.test_feed
                data = json.dumps(snapshot).encode()
                return self.reply(200, data, 'application/json')
            if self.path in content:
                body, kind = content[self.path]
                return self.reply(200, body, kind)
            return self.reply(404)

        def do_POST(self):
            self.reply(405)

        do_PUT = do_DELETE = do_PATCH = do_POST

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    query='?calm=1' if args.calm else ''
    print(f'http://127.0.0.1:{server.server_port}/{query}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
