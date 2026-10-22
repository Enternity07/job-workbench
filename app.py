"""Python 3.10+ local-only portfolio demo. Run: python app.py"""
import argparse
import json
import re
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from workbench.analysis import compare
from workbench.storage import Store

ROOT = Path(__file__).resolve().parent
MAX_BODY = 128 * 1024


def make_server(port=8765, db=None):
    store = Store(db or ROOT / "data" / "applications.sqlite3")
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def send(self, status, value, content_type="application/json; charset=utf-8"):
            body = json.dumps(value, ensure_ascii=False).encode() if isinstance(value, (dict, list)) else value
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def safe_host(self):
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

        def do_GET(self):
            if not self.safe_host():
                return self.send(403, {"error": "仅允许本机地址访问"})
            path = urlsplit(self.path).path
            if path == "/api/session":
                return self.send(200, {"token": token})
            if path == "/api/applications":
                return self.send(200, {"items": store.list()})
            if path == "/api/health":
                return self.send(200, {"status": "ok", "mode": "local-rule-based"})
            assets = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8"),
                      "/main.js": ("main.js", "text/javascript; charset=utf-8")}
            if path not in assets:
                return self.send(404, {"error": "页面不存在"})
            name, mime = assets[path]
            self.send(200, (ROOT / "static" / name).read_bytes(), mime)

        def mutate(self):
            if not self.safe_host() or self.headers.get("X-Local-Token") != token:
                return self.send(403, {"error": "请从本机工作台页面提交操作"})
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}:
                return self.send(403, {"error": "不允许跨站请求"})
            try:
                path = urlsplit(self.path).path
                record = re.fullmatch(r"/api/applications/([1-9][0-9]*)", path)
                if self.command == "DELETE":
                    if not record:
                        return self.send(404, {"error": "接口不存在"})
                    store.delete(int(record[1]))
                    return self.send(200, {"ok": True})
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    return self.send(413, {"error": "请求为空或超过 128 KB"})
                if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                    return self.send(415, {"error": "请提交 JSON 数据"})
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("请求必须是 JSON 对象")
                if path == "/api/analyze" and self.command == "POST":
                    for field in ("jd", "resume"):
                        if not isinstance(data.get(field), str) or not data[field].strip():
                            raise ValueError("请同时填写岗位描述和简历文本")
                        if len(data[field]) > 20000:
                            raise ValueError("单段文本最多 20000 字符")
                    return self.send(200, compare(data["jd"], data["resume"]))
                if path == "/api/applications" and self.command == "POST":
                    return self.send(201, store.save(data))
                if record and self.command == "PUT":
                    return self.send(200, store.save(data, int(record[1])))
                return self.send(404, {"error": "接口不存在"})
            except (ValueError, UnicodeDecodeError) as error:
                return self.send(400, {"error": str(error) or "输入无效"})
            except LookupError as error:
                return self.send(404, {"error": str(error)})

        do_POST = mutate
        do_PUT = mutate
        do_DELETE = mutate

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", type=Path)
    args = parser.parse_args()
    server = make_server(args.port, args.db)
    print(f"Job workbench: http://127.0.0.1:{server.server_port}  (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
