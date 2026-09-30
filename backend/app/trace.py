"""Per-request execution trace for Demo Mode.

When DEMO_MODE is on and a request carries `X-Debug-Trace: 1`, every
semantic step (auth, validation, business rules, broadcast) and every SQL
statement the request runs is recorded. The trace is kept in a small ring
buffer and fetched by id (`X-Trace-Id` response header), so large traces
never bloat response headers.
"""

import itertools
import time
from collections import OrderedDict
from contextvars import ContextVar
from threading import Lock

from sqlalchemy import event
from sqlalchemy.engine import Engine

_current: ContextVar[dict | None] = ContextVar("trace", default=None)
_store: OrderedDict[int, dict] = OrderedDict()
_lock = Lock()
_ids = itertools.count(1)
MAX_TRACES = 200
MAX_STEPS = 60


def start(method: str, path: str) -> dict:
    trace = {"id": next(_ids), "method": method, "path": path, "t0": time.perf_counter(), "steps": []}
    _current.set(trace)
    return trace


def finish(trace: dict, status: int) -> None:
    trace["status"] = status
    trace["duration_ms"] = round((time.perf_counter() - trace.pop("t0")) * 1000, 1)
    with _lock:
        _store[trace["id"]] = trace
        while len(_store) > MAX_TRACES:
            _store.popitem(last=False)


def get(trace_id: int) -> dict | None:
    with _lock:
        return _store.get(trace_id)


def step(tier: str, title: str, detail: str = "", feature: str | None = None, ok: bool = True) -> None:
    """tier: edge | api | auth | logic | db | realtime"""
    trace = _current.get()
    if trace is None or len(trace["steps"]) >= MAX_STEPS:
        return
    trace["steps"].append(
        {
            "t_ms": round((time.perf_counter() - trace["t0"]) * 1000, 1),
            "tier": tier,
            "title": title,
            "detail": detail,
            "feature": feature,
            "ok": ok,
        }
    )


def active() -> bool:
    return _current.get() is not None


def instrument(engine: Engine) -> None:
    """Record each SQL statement (and commits/rollbacks) of traced requests."""

    @event.listens_for(engine, "before_cursor_execute")
    def _sql(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        if not active():
            return
        sql = " ".join(statement.split())
        if len(sql) > 320:
            sql = sql[:320] + " …"
        verb = sql.split(" ", 1)[0].upper()
        step("db", f"SQL {verb}", sql)

    @event.listens_for(engine, "commit")
    def _commit(conn):  # noqa: ANN001
        if active():
            step("db", "COMMIT", "Transaction สำเร็จ บันทึกทุกการเปลี่ยนแปลงพร้อมกัน", feature="Transaction + Validation")

    @event.listens_for(engine, "rollback")
    def _rollback(conn):  # noqa: ANN001
        trace = _current.get()
        # Pool resets issue a rollback after every read-only request; only report it
        # when the request actually wrote something.
        if trace and any(s["title"].startswith(("SQL INSERT", "SQL UPDATE", "SQL DELETE")) for s in trace["steps"]):
            if not any(s["title"] == "COMMIT" for s in trace["steps"]):
                step("db", "ROLLBACK", "ยกเลิก transaction ข้อมูลไม่ถูกบันทึกครึ่งๆ กลางๆ", ok=False)
