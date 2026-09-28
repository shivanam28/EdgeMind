from app.services.network_state import is_online
from app.services.sync_log_service import (
    get_dirty_records,
    mark_synced,
    mark_sync_failed,
    mark_local_only,
)
from app.services.qdrant_service import (
    get_point_from_edge,
    push_point_to_cloud,
    pull_point_to_edge,
    detect_conflict,
)


def run_sync():
    if not is_online():
        return {"status": "skipped", "reason": "offline", "synced": 0, "failed": 0, "conflicts": 0}

    dirty_records = get_dirty_records()
    synced_count = 0
    failed_count = 0
    conflict_count = 0

    for record in dirty_records:
        point_id = int(record["point_id"])
        try:
            if record["mutation_type"] == "DELETE":
                mark_synced(record["id"])
                synced_count += 1
                continue

            point = get_point_from_edge(point_id)
            if point is None:
                raise Exception(f"Point {point_id} not found on Edge")

            # Data residency guard: LOCAL_ONLY data never leaves the device
            if point.payload.get("security_tier") == "LOCAL_ONLY":
                mark_local_only(record["id"])
                continue

            edge_version = point.payload.get("version", 1)
            conflict = detect_conflict(point_id, edge_version, point.vector)

            if conflict is None or conflict["type"] == "EDGE_NEWER":
                push_point_to_cloud(point_id, point.vector, point.payload)
                mark_synced(record["id"])
                synced_count += 1

            elif conflict["type"] == "CLOUD_NEWER":
                cloud_point = conflict["cloud_point"]
                pull_point_to_edge(point_id, cloud_point.vector, cloud_point.payload)
                mark_synced(record["id"])
                synced_count += 1
                conflict_count += 1

            else:  # SAME_VERSION_DIFFERENT_CONTENT
                similarity = conflict["similarity"]
                print(f"DEBUG: point {point_id} similarity = {similarity}")
                if similarity > 0.9:
                    push_point_to_cloud(point_id, point.vector, point.payload)
                    mark_synced(record["id"])
                    synced_count += 1
                    conflict_count += 1
                else:
                    mark_sync_failed(
                        record["id"],
                        f"CONFLICT: same version, low similarity ({similarity:.3f}) - needs manual review",
                    )
                    conflict_count += 1

        except Exception as e:
            mark_sync_failed(record["id"], str(e))
            failed_count += 1

    return {"status": "completed", "synced": synced_count, "failed": failed_count, "conflicts": conflict_count}