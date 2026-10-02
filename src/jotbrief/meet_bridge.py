"""Servidor local (127.0.0.1) que recebe da extensão do Chrome quem está falando no Google Meet."""
from __future__ import annotations

import json
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_PORT = 47821
HEADER = "X-JotBrief"  # header custom: páginas da web não conseguem enviá-lo (exigiria CORS, que não liberamos)


def make_handler(sink: Callable[[str, bool], bool], recording: Callable[[], bool]):
    class Handler(BaseHTTPRequestHandler):
        def _reply(self, code: int, body: dict | None = None):
            data = json.dumps(body or {}).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _allowed(self) -> bool:
            origin = self.headers.get("Origin", "")
            return bool(self.headers.get(HEADER)) and not origin.startswith(("http://", "https://"))

        def do_GET(self):  # noqa: N802
            if not self._allowed():
                return self._reply(403)
            self._reply(200, {"app": "jotbrief", "recording": recording()})

        def do_POST(self):  # noqa: N802
            if not self._allowed() or self.path != "/event":
                return self._reply(403)
            try:
                n = min(int(self.headers.get("Content-Length", 0)), 4096)
                e = json.loads(self.rfile.read(n) or b"{}")
                name, on = str(e["name"])[:120], bool(e["on"])
            except (ValueError, KeyError, TypeError):
                return self._reply(400)
            self._reply(200, {"stored": sink(name, on)})

        def log_message(self, *_):  # silencioso
            pass

    return Handler


def start(sink: Callable[[str, bool], bool], recording: Callable[[], bool], port: int = DEFAULT_PORT):
    """Sobe o servidor numa thread; retorna o servidor (ou None se a porta já está em uso)."""
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(sink, recording))
    except OSError:
        return None
    threading.Thread(target=srv.serve_forever, name="meet-bridge", daemon=True).start()
    return srv
