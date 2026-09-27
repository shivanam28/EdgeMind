# backend/mark_dirty.py
import sqlite3, sys
from pathlib import Path
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "edge_sync.db"
point_id = sys.argv[1]
conn = sqlite3.connect(DB_PATH)
conn.execute("UPDATE edge_sync_log SET dirty_flag = 1 WHERE point_id = ?", (point_id,))
conn.commit()
print("marked dirty")