#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""海豚Radar · REST API（FastAPI）。

读 SQLite（events / ratings / alerts / snapshots / meta），
给前端和第三方提供实时数据。CORS 全开，方便 DeWeb 静态站跨域读。
"""
import json
from contextlib import closing

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from service import db

app = FastAPI(title="海豚Radar API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _conn():
    return db.connect()


def _rating_dict(r):
    d = db.to_dict(r)
    d["risk"] = json.loads(d["risk"]) if d.get("risk") else []
    return d


@app.get("/health")
def health():
    with closing(_conn()) as c:
        last_block = db.get_meta(c, "lastBlock")
        n_events = c.execute("SELECT COUNT(*) n FROM events").fetchone()["n"]
        n_ratings = c.execute("SELECT COUNT(*) n FROM ratings").fetchone()["n"]
    return {"status": "ok", "last_block": last_block, "events": n_events, "ratings": n_ratings}


@app.get("/api/stats")
def stats():
    with closing(_conn()) as c:
        latest = c.execute("SELECT * FROM snapshots ORDER BY id DESC LIMIT 1").fetchone()
        by_status = {r["status"]: r["n"] for r in
                     c.execute("SELECT status, COUNT(*) n FROM ratings GROUP BY status").fetchall()}
        by_grade = {r["grade"]: r["n"] for r in
                    c.execute("SELECT grade, COUNT(*) n FROM ratings GROUP BY grade").fetchall()}
        last_block = db.get_meta(c, "lastBlock")
    return {
        "latest": db.to_dict(latest),
        "by_status": by_status,
        "by_grade": by_grade,
        "last_block": last_block,
    }


@app.get("/api/ratings")
def ratings(status: str = None, grade: str = None, q: str = None,
            limit: int = Query(2000, le=5000), offset: int = 0):
    sql = "SELECT * FROM ratings"
    where, args = [], []
    if status:
        where.append("status=?"); args.append(status)
    if grade:
        where.append("grade=?"); args.append(grade)
    if q:
        where.append("(CAST(circuit_id AS TEXT) LIKE ? OR processor LIKE ?)")
        args += [f"%{q}%", f"%{q}%"]
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY score ASC, circuit_id ASC LIMIT ? OFFSET ?"
    args += [limit, offset]
    with closing(_conn()) as c:
        rows = c.execute(sql, args).fetchall()
        total = c.execute("SELECT COUNT(*) n FROM ratings").fetchone()["n"]
    return {"total": total, "items": [_rating_dict(r) for r in rows]}


@app.get("/api/ratings/{cid}")
def rating_detail(cid: int):
    with closing(_conn()) as c:
        r = c.execute("SELECT * FROM ratings WHERE circuit_id=?", (cid,)).fetchone()
        if not r:
            raise HTTPException(404, "电路不存在")
        hist = c.execute("SELECT * FROM rating_history WHERE circuit_id=? ORDER BY at", (cid,)).fetchall()
        # 电路自身事件（Demoted / CounterexampleAdded 带 circuit_id）
        evs = c.execute("SELECT * FROM events WHERE circuit_id=? ORDER BY block", (cid,)).fetchall()
        # 撤销事件（Revoked 只带 key，经 miners.key → circuit_id 关联回来）
        revs = c.execute(
            "SELECT e.* FROM events e JOIN miners m ON e.key=m.key "
            "WHERE e.event='Revoked' AND m.circuit_id=? ORDER BY e.block", (cid,)).fetchall()
    ev_list = [db.to_dict(e) for e in evs] + [db.to_dict(e) for e in revs]
    ev_list.sort(key=lambda x: (x["block"], x["log_index"] or 0))
    return {
        "rating": _rating_dict(r),
        "history": [db.to_dict(h) for h in hist],
        "events": ev_list,
    }


@app.get("/api/risks")
def risks(suspect: str = None, level: str = None,
          limit: int = Query(2000, le=5000), offset: int = 0):
    sql = "SELECT * FROM risks"
    where, args = [], []
    if suspect:
        where.append("suspect=?"); args.append(suspect)
    if level:
        where.append("level=?"); args.append(level)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY risk DESC, circuit_id ASC LIMIT ? OFFSET ?"
    args += [limit, offset]
    with closing(_conn()) as c:
        rows = c.execute(sql, args).fetchall()
        total = c.execute("SELECT COUNT(*) n FROM risks").fetchone()["n"]
    items = []
    for r in rows:
        d = db.to_dict(r)
        d["labels"] = json.loads(d["labels"]) if d.get("labels") else []
        items.append(d)
    return {"total": total, "items": items}


@app.get("/api/alerts")
def alerts(limit: int = Query(50, le=500)):
    with closing(_conn()) as c:
        rows = c.execute("SELECT * FROM alerts ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    return {"items": [db.to_dict(r) for r in rows]}


@app.get("/api/events")
def events(event: str = None, limit: int = Query(100, le=1000)):
    sql = "SELECT * FROM events"
    args = []
    if event:
        sql += " WHERE event=?"; args.append(event)
    sql += " ORDER BY block DESC, log_index DESC LIMIT ?"
    args.append(limit)
    with closing(_conn()) as c:
        rows = c.execute(sql, args).fetchall()
    return {"items": [db.to_dict(r) for r in rows]}


@app.get("/api/snapshots")
def snapshots(limit: int = Query(100, le=1000)):
    with closing(_conn()) as c:
        rows = c.execute("SELECT * FROM snapshots ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return {"items": [db.to_dict(r) for r in rows]}
