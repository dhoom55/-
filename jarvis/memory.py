"""Long-term memory in SQLite: facts, learned answers, conversations, errors.

The database checks itself on open. If it is corrupted, it is moved aside
and restored from the newest good backup (or recreated empty), so a damaged
file never stops Jarvis from starting.
"""
from __future__ import annotations

import shutil
import sqlite3
import time
from pathlib import Path

from .text import keywords, normalize, similarity

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    key TEXT PRIMARY KEY, value TEXT NOT NULL,
    created REAL, updated REAL, uses INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS qa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL, normalized TEXT NOT NULL, answer TEXT NOT NULL,
    source TEXT DEFAULT 'taught', score REAL DEFAULT 1.0,
    uses INTEGER DEFAULT 0, created REAL);
CREATE INDEX IF NOT EXISTS qa_norm ON qa(normalized);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL, role TEXT, text TEXT, source TEXT);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, text TEXT, done INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, component TEXT,
    error_type TEXT, message TEXT, traceback TEXT, signature TEXT,
    fixed INTEGER DEFAULT 0, fix_note TEXT);
CREATE TABLE IF NOT EXISTS fix_stats (
    signature TEXT, strategy TEXT, successes INTEGER DEFAULT 0, failures INTEGER DEFAULT 0,
    PRIMARY KEY (signature, strategy));
"""


class Memory:
    def __init__(self, path: Path, backups: Path, keep: int = 5):
        self.path = Path(path)
        self.backups = Path(backups)
        self.keep = keep
        self.recovered_from: str | None = None   # set when a repair happened on open
        self.conn = self._open()

    # ---- opening / integrity / backups ---------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _open(self) -> sqlite3.Connection:
        try:
            conn = self._connect()
            ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if ok != "ok":
                raise sqlite3.DatabaseError(f"integrity_check: {ok}")
            conn.executescript(SCHEMA)
            return conn
        except sqlite3.DatabaseError as exc:
            try:
                conn.close()
            except Exception:
                pass
            return self._recover(exc)

    def _recover(self, exc: Exception) -> sqlite3.Connection:
        broken = self.backups / f"memory.broken.{int(time.time())}.db"
        if self.path.exists():
            shutil.move(str(self.path), broken)
        restored = None
        for candidate in self.list_backups():
            try:
                shutil.copy(candidate, self.path)
                conn = self._connect()
                if conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok":
                    conn.executescript(SCHEMA)
                    restored = candidate.name
                    self.recovered_from = f"restored {candidate.name} after: {exc}"
                    return conn
                conn.close()
            except sqlite3.DatabaseError:
                continue
        if restored is None:
            if self.path.exists():
                self.path.unlink()
            self.recovered_from = f"started a fresh memory after: {exc}"
        conn = self._connect()
        conn.executescript(SCHEMA)
        return conn

    def list_backups(self) -> list[Path]:
        return sorted(self.backups.glob("memory.*.bak.db"), reverse=True)

    def backup(self) -> Path:
        dest = self.backups / f"memory.{time.strftime('%Y%m%d-%H%M%S')}.bak.db"
        target = sqlite3.connect(dest)
        with target:
            self.conn.backup(target)
        target.close()
        for old in self.list_backups()[self.keep:]:
            old.unlink(missing_ok=True)
        return dest

    def integrity_ok(self) -> bool:
        try:
            return self.conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        except sqlite3.DatabaseError:
            return False

    def reopen(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
        self.conn = self._open()

    def close(self) -> None:
        self.conn.close()

    # ---- facts -----------------------------------------------------------
    def set_fact(self, key: str, value: str) -> None:
        now = time.time()
        k = normalize(key)
        self.conn.execute(
            "INSERT INTO facts(key,value,created,updated) VALUES(?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated=excluded.updated",
            (k, value.strip(), now, now))
        self.conn.commit()

    def get_fact(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM facts WHERE key=?", (normalize(key),)).fetchone()
        return row["value"] if row else None

    def forget_fact(self, key: str) -> int:
        k = normalize(key)
        cur = self.conn.execute("DELETE FROM facts WHERE key=? OR key LIKE ?", (k, f"%{k}%"))
        cur2 = self.conn.execute("DELETE FROM qa WHERE normalized LIKE ?", (f"%{k}%",))
        self.conn.commit()
        return cur.rowcount + cur2.rowcount

    def all_facts(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT key, value FROM facts ORDER BY updated DESC").fetchall()

    def search_facts(self, text: str, limit: int = 5) -> list[tuple[str, str]]:
        words = keywords(text)
        if not words:
            return []
        scored = []
        for row in self.all_facts():
            kw = keywords(row["key"]) | keywords(row["value"])
            hit = len(words & kw)
            if hit:
                scored.append((hit, row["key"], row["value"]))
        scored.sort(reverse=True)
        return [(k, v) for _, k, v in scored[:limit]]

    # ---- learned question/answer pairs ---------------------------------
    def learn_answer(self, question: str, answer: str, source: str = "taught") -> int:
        norm = normalize(question)
        row = self.conn.execute("SELECT id FROM qa WHERE normalized=?", (norm,)).fetchone()
        if row:
            # A taught answer always wins over one cached from an LLM or learned by Agent X.
            if source != "taught":
                existing = self.conn.execute("SELECT source FROM qa WHERE id=?", (row["id"],)).fetchone()
                if existing["source"] == "taught":
                    return row["id"]
            self.conn.execute("UPDATE qa SET answer=?, source=?, score=1.0 WHERE id=?",
                              (answer.strip(), source, row["id"]))
            self.conn.commit()
            return row["id"]
        cur = self.conn.execute(
            "INSERT INTO qa(question,normalized,answer,source,created) VALUES(?,?,?,?,?)",
            (question.strip(), norm, answer.strip(), source, time.time()))
        self.conn.commit()
        return cur.lastrowid

    def recall(self, question: str, threshold: float = 0.82) -> tuple[sqlite3.Row, float] | None:
        """Best learned answer for a question, if it is similar enough."""
        norm = normalize(question)
        exact = self.conn.execute(
            "SELECT * FROM qa WHERE normalized=? AND score > 0 LIMIT 1", (norm,)).fetchone()
        if exact:
            self._used(exact["id"])
            return exact, 1.0
        best, best_score = None, 0.0
        for row in self.conn.execute("SELECT * FROM qa WHERE score > 0"):
            s = similarity(question, row["question"]) * min(1.0, 0.7 + 0.3 * row["score"])
            if s > best_score:
                best, best_score = row, s
        if best is not None and best_score >= threshold:
            self._used(best["id"])
            return best, best_score
        return None

    def _used(self, qa_id: int) -> None:
        self.conn.execute("UPDATE qa SET uses=uses+1 WHERE id=?", (qa_id,))
        self.conn.commit()

    def rate_answer(self, qa_id: int, delta: float) -> None:
        self.conn.execute("UPDATE qa SET score=MAX(0, MIN(3, score+?)) WHERE id=?", (delta, qa_id))
        self.conn.commit()

    def correct_answer(self, qa_id: int, answer: str) -> None:
        self.conn.execute("UPDATE qa SET answer=?, source='taught', score=1.5 WHERE id=?", (answer, qa_id))
        self.conn.commit()

    def learned(self, limit: int = 20) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT question, answer, source, uses FROM qa ORDER BY created DESC LIMIT ?", (limit,)).fetchall()

    # ---- conversation log ----------------------------------------------
    def log(self, role: str, text: str, source: str = "") -> None:
        self.conn.execute("INSERT INTO conversations(ts,role,text,source) VALUES(?,?,?,?)",
                          (time.time(), role, text, source))
        self.conn.commit()

    def recent(self, n: int = 10) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            "SELECT role, text, source FROM conversations ORDER BY id DESC LIMIT ?", (n,)).fetchall()
        return list(reversed(rows))

    # ---- notes -----------------------------------------------------------
    def add_note(self, text: str) -> int:
        cur = self.conn.execute("INSERT INTO notes(ts,text) VALUES(?,?)", (time.time(), text))
        self.conn.commit()
        return cur.lastrowid

    def notes(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT id, text FROM notes WHERE done=0 ORDER BY id").fetchall()

    def done_note(self, note_id: int) -> bool:
        cur = self.conn.execute("UPDATE notes SET done=1 WHERE id=?", (note_id,))
        self.conn.commit()
        return cur.rowcount > 0

    # ---- errors / repair statistics (used by the healer) ----------------
    def log_error(self, component, error_type, message, tb, signature) -> int:
        cur = self.conn.execute(
            "INSERT INTO errors(ts,component,error_type,message,traceback,signature) VALUES(?,?,?,?,?,?)",
            (time.time(), component, error_type, message, tb, signature))
        self.conn.commit()
        return cur.lastrowid

    def mark_fixed(self, error_id: int, note: str) -> None:
        self.conn.execute("UPDATE errors SET fixed=1, fix_note=? WHERE id=?", (note, error_id))
        self.conn.commit()

    def recent_errors(self, limit: int = 10) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM errors ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

    def error_count(self, component: str, since: float = 0) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM errors WHERE component=? AND ts>=? AND fixed=0",
            (component, since)).fetchone()[0]

    def record_fix(self, signature: str, strategy: str, success: bool) -> None:
        col = "successes" if success else "failures"
        self.conn.execute(
            f"INSERT INTO fix_stats(signature,strategy,{col}) VALUES(?,?,1) "
            f"ON CONFLICT(signature,strategy) DO UPDATE SET {col}={col}+1",
            (signature, strategy))
        self.conn.commit()

    def fix_ranking(self, signature: str) -> dict[str, float]:
        rows = self.conn.execute(
            "SELECT strategy, successes, failures FROM fix_stats WHERE signature=?", (signature,))
        return {r["strategy"]: (r["successes"] + 1) / (r["successes"] + r["failures"] + 2) for r in rows}
