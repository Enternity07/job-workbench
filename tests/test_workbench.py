import http.client
import json
import sys
import tempfile
import threading
import unittest
import shutil
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import make_server
from workbench.analysis import compare, extract
from workbench.storage import Store


class TestDirectory:
    """Use inherited directory permissions, including on Windows sandboxes."""
    def __init__(self):
        self.base = Path(tempfile.gettempdir()).resolve()
        self.path = self.base / ("workbench-test-" + uuid.uuid4().hex)
        self.path.mkdir()
        self.name = str(self.path)

    def cleanup(self):
        if self.path.resolve().parent != self.base:
            raise RuntimeError("Test cleanup must stay within its temporary root")
        shutil.rmtree(self.path)


class AnalysisTests(unittest.TestCase):
    def test_aliases_and_case(self):
        self.assertEqual(set(extract("python JS HTML5 CSS3 sqlite3 ClaudeCode")),
                         {"Python", "JavaScript", "HTML", "CSS", "SQLite", "Claude Code"})

    def test_no_substring_collisions(self):
        result = extract("JavaScript MySQL GitHub Pythonista")
        self.assertEqual(set(result), {"JavaScript", "MySQL"})

    def test_evidence_and_ratio(self):
        result = compare("熟悉 Python、SQLite、Git", "用 Python 和 SQLite 做了小工具")
        self.assertEqual(result["coverage"], 67)
        self.assertEqual([x["skill"] for x in result["missing"]], ["Git"])
        self.assertIn("用 Python", result["covered"][0]["resume_evidence"][0])

    def test_unrecognized_is_not_zero_score(self):
        self.assertIsNone(compare("有主动性，擅长沟通", "组织过班会")["coverage"])

    def test_literal_mentions_do_not_imply_proficiency(self):
        result = compare("需要 Python", "暂时不会 Python")
        self.assertEqual(result["coverage"], 100)
        self.assertIn("否定语义", result["notice"])
        self.assertIn("不会", result["covered"][0]["resume_evidence"][0])


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = TestDirectory()
        self.path = Path(self.temp.name) / "jobs.sqlite3"
        self.store = Store(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_roundtrip_update_and_delete(self):
        item = self.store.save({"company":"虚构公司", "role":"实习生", "note":"中文备注"})
        self.assertEqual(Store(self.path).list()[0]["note"], "中文备注")
        updated = self.store.save({**item, "status":"面试中", "next_date":"2026-11-01"}, item["id"])
        self.assertEqual(updated["status"], "面试中")
        self.store.delete(item["id"])
        self.assertEqual(self.store.list(), [])

    def test_sql_special_chars_remain_data(self):
        text = "'); DROP TABLE applications; --"
        self.store.save({"company":text, "role":"<script>alert(1)</script>"})
        self.assertEqual(self.store.list()[0]["company"], text)

    def test_validation(self):
        for data in [{}, {"company":1, "role":"开发"}, {"company":"a", "role":"b", "status":"无效"},
                     {"company":"a", "role":"b", "next_date":"2026-02-30"},
                     {"company":"a", "role":"b", "note":"x" * 2001}]:
            with self.subTest(data=str(data)[:50]), self.assertRaises(ValueError):
                self.store.save(data)

    def test_missing_record(self):
        with self.assertRaises(LookupError): self.store.delete(999)
        with self.assertRaises(LookupError): self.store.save({"company":"a", "role":"b"}, 999)


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = TestDirectory()
        cls.server = make_server(0, Path(cls.temp.name) / "jobs.sqlite3")
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        _, session = cls.request("GET", "/api/session", authenticated=False)
        cls.token = session["token"]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(); cls.temp.cleanup()

    @classmethod
    def request(cls, method, path, data=None, authenticated=True, extra_headers=None, raw=None):
        conn = http.client.HTTPConnection("127.0.0.1", cls.server.server_port, timeout=5)
        headers = {"Content-Type":"application/json"}
        if authenticated: headers["X-Local-Token"] = cls.token
        if extra_headers: headers.update(extra_headers)
        body = raw if raw is not None else json.dumps(data).encode() if data is not None else None
        conn.request(method, path, body, headers)
        response = conn.getresponse(); payload = response.read()
        result = json.loads(payload) if "application/json" in response.getheader("Content-Type", "") else payload
        status = response.status; conn.close(); return status, result

    def test_assets_and_no_data_exposure(self):
        for path in ["/", "/style.css", "/main.js"]:
            self.assertEqual(self.request("GET", path)[0], 200)
        self.assertEqual(self.request("GET", "/data/applications.sqlite3")[0], 404)
        self.assertEqual(self.request("GET", "/../app.py")[0], 404)

    def test_http_crud(self):
        status, item = self.request("POST", "/api/applications", {"company":"API演示", "role":"实习"})
        self.assertEqual(status, 201)
        self.assertEqual(self.request("PUT", f"/api/applications/{item['id']}", {**item,"status":"已投递"})[1]["status"], "已投递")
        self.assertTrue(self.request("DELETE", f"/api/applications/{item['id']}")[1]["ok"])

    def test_analysis_http(self):
        status, result = self.request("POST", "/api/analyze", {"jd":"Python Git", "resume":"Python"})
        self.assertEqual(status, 200); self.assertEqual(result["coverage"], 50)

    def test_invalid_json_and_schema(self):
        for raw in [b"{", b"null", b"[]", b"\xff"]:
            self.assertEqual(self.request("POST", "/api/analyze", raw=raw)[0], 400)
        self.assertEqual(self.request("POST", "/api/analyze", {"jd":"x", "resume":""})[0], 400)
        self.assertEqual(self.request("POST", "/api/analyze", {"jd":"x"*20001, "resume":"y"})[0], 400)

    def test_cross_site_and_missing_token(self):
        data = {"company":"x", "role":"y"}
        self.assertEqual(self.request("POST", "/api/applications", data, authenticated=False)[0], 403)
        self.assertEqual(self.request("POST", "/api/applications", data, extra_headers={"Origin":"https://example.org"})[0], 403)
        self.assertEqual(self.request("GET", "/api/session", extra_headers={"Host":"example.org"})[0], 403)

    def test_payload_and_content_type(self):
        self.assertEqual(self.request("POST", "/api/analyze", raw=b"x"*131073)[0], 413)
        self.assertEqual(self.request("POST", "/api/analyze", raw=b"{}", extra_headers={"Content-Type":"text/plain"})[0], 415)


if __name__ == "__main__":
    unittest.main()
