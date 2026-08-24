from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ThreadState:
    thread_ts: str
    source_channel_id: str
    user_id: str
    original_text: str
    target_channel: str | None = None
    keyword: str | None = None
    priority: str = "Média"
    summary: str = ""
    questions: list[str] = field(default_factory=list)
    answers: list[str] = field(default_factory=list)
    pending_confirmation: bool = False
    status: str = "open"


class StateStore:
    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True) if Path(db_path).parent != Path(".") else None
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS thread_state (
                thread_ts TEXT PRIMARY KEY,
                payload TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def save(self, state: ThreadState) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO thread_state(thread_ts, payload) VALUES (?, ?)",
            (state.thread_ts, json.dumps(asdict(state), ensure_ascii=False)),
        )
        self.conn.commit()

    def get(self, thread_ts: str) -> ThreadState | None:
        row = self.conn.execute(
            "SELECT payload FROM thread_state WHERE thread_ts = ?",
            (thread_ts,),
        ).fetchone()
        if not row:
            return None
        data = json.loads(row[0])
        return ThreadState(**data)

    def close(self, thread_ts: str) -> None:
        state = self.get(thread_ts)
        if not state:
            return
        state.status = "closed"
        self.save(state)
