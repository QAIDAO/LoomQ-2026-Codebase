#!/usr/bin/env python3
"""LoomQ web entry - a zero-background friendly quantum playground.

Run:  python starter_kit/webapp.py   (then open http://127.0.0.1:8765)

Endpoints:
  GET  /                -> web/index.html
  GET  /style.css|app.js-> static assets
  POST /api/chat        -> {"message": str} => {"reply": str, "qasm": str|null}
  POST /api/run         -> {"qasm": str, "target": str, "shots": int}
                           => {"counts": {...}, "target": str}

LLM configuration comes from LOOMQ_LLM_* environment variables (same as
agent_chat). For local demos, if those are unset and a sibling
loomq_secrets.json exists, we fill them in automatically (file stays
outside the repository and is never shipped).
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

WEB_DIR = os.path.join(HERE, 'web')
PORT = int(os.environ.get('LOOMQ_WEB_PORT', '8765'))


def _ensure_llm_env():
    """Fill LOOMQ_LLM_* from a local secrets file for demo convenience."""
    needed = ('LOOMQ_LLM_BASE_URL', 'LOOMQ_LLM_API_KEY', 'LOOMQ_LLM_MODEL')
    if all(os.environ.get(k) for k in needed):
        return
    candidates = [
        os.path.join(os.path.dirname(HERE), 'loomq_secrets.json'),
        os.path.join(os.path.dirname(HERE), os.pardir, 'loomq_secrets.json'),
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, encoding='utf-8-sig') as f:
                    sec = json.load(f)
                os.environ.setdefault('LOOMQ_LLM_BASE_URL',
                                      sec.get('web_base_url') or
                                      'https://api.stepfun.com/v1')
                os.environ.setdefault('LOOMQ_LLM_API_KEY',
                                      sec.get('stepfun_key', ''))
                os.environ.setdefault('LOOMQ_LLM_MODEL',
                                      sec.get('web_model') or
                                      'step-3.7-flash')
                print('[loomq-web] LLM env filled from', path, flush=True)
                return
            except Exception as e:  # noqa: BLE001
                print('[loomq-web] secrets load failed:', e, flush=True)
                return


_ensure_llm_env()
import adapter  # noqa: E402  (import after env setup on purpose)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    # ------------ helpers ------------
    def _send(self, code, body, ctype):
        data = body if isinstance(body, bytes) else body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False),
                   'application/json; charset=utf-8')

    def _static(self, rel, ctype):
        path = os.path.join(WEB_DIR, rel)
        if not os.path.isfile(path):
            self._json(404, {'error': 'not found'})
            return
        with open(path, 'rb') as f:
            self._send(200, f.read(), ctype)

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(n) if n else b'{}'
        return json.loads(raw.decode('utf-8'))

    # ------------ routes ------------
    def do_GET(self):  # noqa: N802
        route = self.path.split('?')[0]
        if route in ('/', '/index.html'):
            self._static('index.html', 'text/html; charset=utf-8')
        elif route == '/style.css':
            self._static('style.css', 'text/css; charset=utf-8')
        elif route == '/app.js':
            self._static('app.js', 'application/javascript; charset=utf-8')
        elif route == '/healthz':
            self._json(200, {'ok': True})
        else:
            self._json(404, {'error': 'not found'})

    def do_POST(self):  # noqa: N802
        route = self.path.split('?')[0]
        try:
            if route == '/api/chat':
                msg = (self._body().get('message') or '').strip()
                if not msg:
                    self._json(400, {'error': 'empty message'})
                    return
                reply = adapter.agent_chat(msg)
                qasm = None
                try:
                    qasm = adapter._l2_extract_qasm(reply)
                except Exception:  # noqa: BLE001
                    pass
                self._json(200, {'reply': reply, 'qasm': qasm})
            elif route == '/api/run':
                b = self._body()
                qasm = b.get('qasm') or ''
                target = b.get('target') or 'originq'
                shots = int(b.get('shots') or 1024)
                if target not in adapter.SUPPORTED_TARGETS:
                    self._json(400, {'error': 'unknown target: ' + target})
                    return
                res = adapter.run(qasm, target, min(shots, 8192))
                counts = res.get('counts') if isinstance(res, dict) else res
                self._json(200, {'counts': counts, 'target': target,
                                 'shots': shots})
            else:
                self._json(404, {'error': 'not found'})
        except Exception as e:  # noqa: BLE001
            self._json(500, {'error': str(e)[:400]})

    def log_message(self, fmt, *args):  # quieter console
        sys.stderr.write('[web] ' + fmt % args + '\n')


def main():
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    print(f'[loomq-web] serving at http://127.0.0.1:{PORT}', flush=True)
    print('[loomq-web] Ctrl+C to stop', flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
