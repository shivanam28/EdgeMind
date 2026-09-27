import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "edge_sync.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT * FROM edge_sync_log ORDER BY id DESC").fetchall()

for row in rows:
    print(dict(row))
    print("-" * 40)

conn.close()