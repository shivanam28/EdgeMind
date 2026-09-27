import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "edge_sync.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS edge_sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            point_id TEXT NOT NULL,
            mutation_type TEXT NOT NULL CHECK (mutation_type IN ('INSERT', 'UPDATE', 'DELETE')),
            payload_snapshot TEXT,
            vector_snapshot TEXT,
            version INTEGER NOT NULL DEFAULT 1,
            dirty_flag INTEGER NOT NULL DEFAULT 1,
            last_sync_attempt TIMESTAMP,
            retry_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    print(f"SQLite sync log initialized at {DB_PATH}")

if __name__ == "__main__":
    init_db()