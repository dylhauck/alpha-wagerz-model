"""Odds-API.io multi-event snapshots with safe single-event fallback.

The provider documents at most 10 events per /odds/multi call and does not
guarantee response order. Never substitute another event's odds.
"""
from concurrent.futures import ThreadPoolExecutor


def fetch_many(event_ids, fetch_single, fetch_multi, workers=4, batch_size=10):
    """Return event_id -> odds dict. Missing/malformed batches retry individually.

    fetch_single(event_id) and fetch_multi(list_of_event_ids) are provider
    adapters; failures of a single event remain isolated.
    """
    ids = list(dict.fromkeys(str(event_id) for event_id in event_ids if event_id))
    if not ids:
        return {}
    workers = max(1, min(6, int(workers)))
    batch_size = max(1, min(10, int(batch_size)))
    chunks = [ids[i:i + batch_size] for i in range(0, len(ids), batch_size)]

    def get_chunk(chunk):
        resolved = {}
        try:
            payload = fetch_multi(chunk)
            if isinstance(payload, dict):
                payload = payload.get("data", payload.get("events", payload))
            if isinstance(payload, dict):
                payload = list(payload.values()) if all(
                    isinstance(v, dict) for v in payload.values()
                ) else []
            if not isinstance(payload, list):
                payload = []
            for item in payload:
                if not isinstance(item, dict):
                    continue
                event_id = item.get("id", item.get("eventId"))
                if event_id is None and isinstance(item.get("event"), dict):
                    event_id = item["event"].get("id")
                if str(event_id) in chunk and isinstance(item.get("bookmakers"), (dict, list)):
                    resolved[str(event_id)] = item
        except Exception as exc:
            print(f"⚠️ Bulk odds request failed; retrying individually: {exc}", flush=True)
        for event_id in chunk:
            if event_id in resolved:
                continue
            try:
                item = fetch_single(event_id)
                if isinstance(item, dict) and isinstance(item.get("data"), dict):
                    item = item["data"]
                if isinstance(item, dict):
                    resolved[event_id] = item
            except Exception as exc:
                print(f"⚠️ Odds unavailable for event {event_id}: {exc}", flush=True)
        return resolved

    with ThreadPoolExecutor(max_workers=workers) as pool:
        chunks_results = list(pool.map(get_chunk, chunks))
    return {key: value for chunk in chunks_results for key, value in chunk.items()}
