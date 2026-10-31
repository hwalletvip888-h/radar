#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""海豚Radar · SQLite 数据层。

一个文件搞定：建库（schema）、幂等建表、连接、meta 键值读写。
所有表都带 UNIQUE 主键，重跑不重复（幂等）。
"""
import os
import sqlite3

from service.config import DB_PATH, DATA_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    tx           TEXT NOT NULL,
    log_index    INTEGER NOT NULL,
    event        TEXT NOT NULL,
    block        INTEGER NOT NULL,
    key          TEXT,
    circuits     TEXT,
    circuit_id   INTEGER,
    task_id      INTEGER,
    challenger   TEXT,
    vector_index INTEGER,
    by           TEXT,
    raw          TEXT,
    PRIMARY KEY (tx, log_index)
);
CREATE INDEX IF NOT EXISTS idx_events_event   ON events(event);
CREATE INDEX IF NOT EXISTS idx_events_circuit ON events(circuit_id);
CREATE INDEX IF NOT EXISTS idx_events_block   ON events(block);

CREATE TABLE IF NOT EXISTS miners (
    key         TEXT PRIMARY KEY,
    circuits    TEXT,
    circuit_id  INTEGER,
    task_id     INTEGER,
    gate_count  INTEGER,
    status      INTEGER,
    registrant  TEXT,
    debt        INTEGER,
    updated_at  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_miners_circuit ON miners(circuit_id);

CREATE TABLE IF NOT EXISTS ratings (
    circuit_id  INTEGER PRIMARY KEY,
    processor   TEXT,
    task_id     INTEGER,
    gate_count  INTEGER,
    score       INTEGER,
    grade       TEXT,
    status      TEXT,
    risk        TEXT,
    debt_bem    REAL,
    challenger  TEXT,
    registrant  TEXT,
    tx          TEXT,
    block       INTEGER,
    updated_at  INTEGER
);

CREATE TABLE IF NOT EXISTS rating_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    circuit_id  INTEGER NOT NULL,
    score       INTEGER NOT NULL,
    grade       TEXT NOT NULL,
    status      TEXT NOT NULL,
    at          INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rh_circuit ON rating_history(circuit_id, at);

CREATE TABLE IF NOT EXISTS alerts (
    id          TEXT PRIMARY KEY,
    type        TEXT,
    tier        TEXT,
    title       TEXT,
    detail      TEXT,
    impact      TEXT,
    tx          TEXT,
    block       INTEGER,
    ts          INTEGER,
    payload     TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(ts);

CREATE TABLE IF NOT EXISTS subscriptions (
    id               TEXT PRIMARY KEY,
    address          TEXT,
    tier             TEXT,
    channels         TEXT,
    telegram_chat_id TEXT,
    webhook_url      TEXT,
    expiry           INTEGER,
    filters          TEXT
);

CREATE TABLE IF NOT EXISTS snapshots (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    at             INTEGER NOT NULL,
    total_miners   INTEGER,
    revoked        INTEGER,
    demoted        INTEGER,
    stopped        INTEGER,
    counterexample INTEGER
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db():
    conn = connect()
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key, value):
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )


def to_dict(row):
    return {k: row[k] for k in row.keys()} if row else None
