# backend/check_sync_log.py
import sqlite3
from pathlib import Path
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "edge_sync.db"
conn = sqlite3.connect(DB_PATH)
rows = conn.execute("SELECT point_id, mutation_type, dirty_flag, version FROM edge_sync_log").fetchall()
print(rows)