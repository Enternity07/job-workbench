"""Small SQLite repository with request-scoped connections."""
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

STATUSES = ("待投递", "已投递", "面试中", "已录用", "已结束")


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL, role TEXT NOT NULL,
                status TEXT NOT NULL, next_date TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL)""")

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def list(self):
        with self.connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM applications ORDER BY id DESC")]

    def save(self, data, record_id=None):
        limits = {"company": 100, "role": 100, "status": 12, "next_date": 10, "note": 2000}
        if not isinstance(data, dict):
            raise ValueError("请求必须是 JSON 对象")
        values = {}
        for name, limit in limits.items():
            value = data.get(name, "待投递" if name == "status" else "")
            if not isinstance(value, str):
                raise ValueError(f"{name} 必须是文本")
            value = value.strip()
            if len(value) > limit:
                raise ValueError(f"{name} 超过长度限制 {limit}")
            values[name] = value
        if not values["company"] or not values["role"]:
            raise ValueError("请填写公司和岗位")
        if values["status"] not in STATUSES:
            raise ValueError("投递状态无效")
        if values["next_date"]:
            try:
                parsed = date.fromisoformat(values["next_date"])
                if parsed.isoformat() != values["next_date"]:
                    raise ValueError()
            except ValueError:
                raise ValueError("跟进日期应为 YYYY-MM-DD 格式的有效日期") from None
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.connect() as conn:
            if record_id is None:
                cursor = conn.execute("""INSERT INTO applications
                    (company, role, status, next_date, note, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""", (*values.values(), now, now))
                record_id = cursor.lastrowid
            else:
                cursor = conn.execute("""UPDATE applications
                    SET company=?, role=?, status=?, next_date=?, note=?, updated_at=? WHERE id=?""",
                    (*values.values(), now, record_id))
                if not cursor.rowcount:
                    raise LookupError("记录不存在")
            return dict(conn.execute("SELECT * FROM applications WHERE id=?", (record_id,)).fetchone())

    def delete(self, record_id):
        with self.connect() as conn:
            if not conn.execute("DELETE FROM applications WHERE id=?", (record_id,)).rowcount:
                raise LookupError("记录不存在")
