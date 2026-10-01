"""SQLite for one host; PostgreSQL for shared deployments."""
import os
from pathlib import Path
from sqlalchemy import Column, Float, Index, Integer, LargeBinary, MetaData, String, Table, Text, create_engine, event

ROOT = Path(__file__).resolve().parents[1]
url = os.environ.get("DATABASE_URL", f"sqlite:///{ROOT / 'shelfsense.db'}")
if url.startswith(("postgres://", "postgresql://")):
    url = "postgresql+psycopg://" + url.split("://", 1)[1]
engine = create_engine(url, pool_pre_ping=True, **({"connect_args": {"timeout": 20}} if url.startswith("sqlite") else {}))
if url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _):
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=20000")

metadata = MetaData()
scans = Table("scan_records", metadata,
    Column("id", Integer, primary_key=True), Column("created_at", Integer, nullable=False),
    Column("source", String(240)), Column("camera", String(80), nullable=False),
    Column("baseline", String(64), nullable=False), Column("occupancy", Float),
    Column("status", String(24)), Column("alerts", Integer), Column("result", Text),
    Column("image", LargeBinary), Column("fingerprint", String(64), unique=True))
Index("ix_scan_camera_time", scans.c.camera, scans.c.created_at, scans.c.id)
tasks = Table("restock_tasks", metadata,
    Column("id", Integer, primary_key=True), Column("camera", String(80)),
    Column("zone_id", String(80)), Column("zone_name", String(160)),
    Column("severity", String(24)), Column("missing", Integer),
    Column("state", String(24)), Column("assignee", String(80)),
    Column("created_at", Integer), Column("updated_at", Integer),
    Column("scan_id", Integer), Column("baseline", String(64)))
Index("ix_task_camera_state", tasks.c.camera, tasks.c.state)
events = Table("task_events", metadata, Column("id", Integer, primary_key=True),
    Column("task_id", Integer), Column("created_at", Integer), Column("actor", String(80)), Column("message", Text))
Index("ix_event_created", events.c.created_at)
users = Table("users", metadata, Column("id", Integer, primary_key=True),
    Column("username", String(80), unique=True), Column("password", Text), Column("role", String(20)))
sessions = Table("sessions", metadata, Column("token", String(64), primary_key=True),
    Column("user_id", Integer), Column("expires", Integer))
settings = Table("settings", metadata, Column("key", String(80), primary_key=True), Column("value", Text))


def init_db():
    if os.environ.get("VERCEL") and "DATABASE_URL" not in os.environ:
        raise RuntimeError("Set DATABASE_URL to persistent PostgreSQL before deployment.")
    metadata.create_all(engine)
