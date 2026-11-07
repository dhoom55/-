#!/usr/bin/env python3
"""A tiny stand-in for the `ollama` program, used by the tests.

`fake_ollama.py serve` answers the same HTTP API Jarvis uses
(/api/tags, /api/pull, /api/chat) on port $FAKE_OLLAMA_PORT.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODELS = set(filter(None, os.environ.get("FAKE_OLLAMA_MODELS", "").split(",")))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/tags":
            return self._json({"models": [{"name": m} for m in sorted(MODELS)]})
        self.send_error(404)

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/api/pull":
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            total = 200_000_000
            for done in range(0, total + 1, total // 5):
                self.wfile.write((json.dumps({"status": "downloading", "total": total, "completed": done}) + "\n").encode())
            self.wfile.write(b'{"status": "success"}\n')
            name = data["model"]
            MODELS.add(name if ":" in name else name + ":latest")
            return
        if self.path == "/api/chat":
            question = data["messages"][-1]["content"]
            return self._json({"message": {"role": "assistant", "content": f"ollama({data['model']}) says: {question}"}})
        self.send_error(404)


if __name__ == "__main__" and sys.argv[1:] == ["serve"]:
    ThreadingHTTPServer(("127.0.0.1", int(os.environ["FAKE_OLLAMA_PORT"])), Handler).serve_forever()
