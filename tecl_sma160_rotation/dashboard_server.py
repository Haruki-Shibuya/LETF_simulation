from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from canonical_chart_data import DASHBOARD_DIR, build_canonical_chart_payload
from position_dashboard_data import build_position_dashboard_payload


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/canonical_chart":
            self.respond_canonical_chart()
            return
        if parsed.path == "/api/position":
            self.respond_position(parsed.query)
            return
        if parsed.path in {"", "/"}:
            self.redirect("/index.html")
            return
        self.respond_static(parsed.path)

    def redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def respond_canonical_chart(self) -> None:
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            variant = (params.get("start") or ["2005"])[0]
            body = json.dumps(build_canonical_chart_payload(variant=variant), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
        except Exception as exc:
            body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
            self.send_response(500)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_common_headers(self, content_type: str, length: int) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(length))

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_common_headers("text/plain; charset=utf-8", 0)
        self.end_headers()

    def respond_position(self, query: str = "") -> None:
        try:
            params = parse_qs(query)
            mode = (params.get("mode") or ["latest"])[0]
            variant = (params.get("start") or ["2005"])[0]
            body = json.dumps(build_position_dashboard_payload(mode=mode, variant=variant), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
        except Exception as exc:
            body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
            self.send_response(500)
        self._send_common_headers("application/json; charset=utf-8", len(body))
        self.end_headers()
        self.wfile.write(body)

    def respond_static(self, path: str) -> None:
        relative = path.lstrip("/")
        target = (DASHBOARD_DIR / relative).resolve()
        dashboard_root = DASHBOARD_DIR.resolve()
        if dashboard_root not in target.parents and target != dashboard_root:
            self.send_error(403)
            return
        if not target.exists() or not target.is_file():
            self.send_error(404)
            return
        body = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    display_host = "127.0.0.1" if args.host in {"", "0.0.0.0"} else args.host
    print(f"Dashboard: http://{display_host}:{args.port}/index.html", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
