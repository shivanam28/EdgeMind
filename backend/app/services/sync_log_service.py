import json

from app.utils.db import get_connection


def log_mutation(point_id: str, mutation_type: str, payload: dict, vector: list[float],
                 version: int = 1, dirty_flag: int = 1):
    # dirty_flag: 1 = pending sync, 0 = synced, 2 = kept on device (LOCAL_ONLY, never syncs)
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO edge_sync_log
        (point_id, mutation_type, payload_snapshot, vector_snapshot, version, dirty_flag)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (point_id, mutation_type, json.dumps(payload), json.dumps(vector), version, dirty_flag),
    )
    conn.commit()
    conn.close()


def get_dirty_records():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM edge_sync_log WHERE dirty_flag = 1"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def mark_synced(log_id: int):
    conn = get_connection()
    conn.execute(
        "UPDATE edge_sync_log SET dirty_flag = 0, last_sync_attempt = CURRENT_TIMESTAMP, error_message = NULL WHERE id = ?",
        (log_id,),
    )
    conn.commit()
    conn.close()


def mark_sync_failed(log_id: int, error: str):
    conn = get_connection()
    conn.execute(
        """
        UPDATE edge_sync_log
        SET retry_count = retry_count + 1,
            last_sync_attempt = CURRENT_TIMESTAMP,
            error_message = ?
        WHERE id = ?
        """,
        (error, log_id),
    )
    conn.commit()
    conn.close()


def mark_local_only(log_id: int):
    conn = get_connection()
    conn.execute(
        "UPDATE edge_sync_log SET dirty_flag = 2, error_message = NULL WHERE id = ?",
        (log_id,),
    )
    conn.commit()
    conn.close()


def get_sync_status():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, point_id, mutation_type, version, dirty_flag, retry_count, error_message, last_sync_attempt, created_at FROM edge_sync_log ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    records = [dict(row) for row in rows]
    pending = [r for r in records if r["dirty_flag"] == 1]
    synced = [r for r in records if r["dirty_flag"] == 0]
    local_only = [r for r in records if r["dirty_flag"] == 2]
    failed = [r for r in records if r["retry_count"] > 0 and r["dirty_flag"] == 1]

    return {
        "total_records": len(records),
        "pending_count": len(pending),
        "synced_count": len(synced),
        "local_only_count": len(local_only),
        "failed_count": len(failed),
        "records": records,
    }