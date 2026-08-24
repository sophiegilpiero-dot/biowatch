"""
SQLite 기반 중복 알림 방지 캐시
- 이미 알림을 보낸 공시 ID를 저장
- 30일 후 자동 만료
"""
import sqlite3
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "seen.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen_items (
            item_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            first_seen TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def make_id(source: str, raw_id: str) -> str:
    return hashlib.sha256(f"{source}:{raw_id}".encode()).hexdigest()[:16]


def is_new(source: str, raw_id: str) -> bool:
    """처음 보는 항목이면 True, 이미 본 항목이면 False"""
    item_id = make_id(source, raw_id)
    conn = _get_conn()
    now = datetime.utcnow().isoformat()
    
    # 만료된 항목 정리
    conn.execute("DELETE FROM seen_items WHERE expires_at < ?", (now,))
    
    row = conn.execute(
        "SELECT item_id FROM seen_items WHERE item_id = ?", (item_id,)
    ).fetchone()
    
    if row:
        conn.close()
        return False
    
    # 새 항목 등록
    expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
    conn.execute(
        "INSERT INTO seen_items (item_id, source, first_seen, expires_at) VALUES (?, ?, ?, ?)",
        (item_id, source, now, expires)
    )
    conn.commit()
    conn.close()
    return True


def mark_seen(source: str, raw_id: str):
    """항목을 이미 본 것으로 명시적 등록 (is_new 호출 후 필요 시)"""
    is_new(source, raw_id)  # is_new가 자동으로 등록함
