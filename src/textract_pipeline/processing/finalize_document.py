"""Shared completion, failure and notification delivery for sync and async work."""

import logging

from ..models import InvalidDocument, LostLease, TERMINAL, iso_now, json_bytes, retryable, safe_error
from .parsing import parse, records
from .exporting import export_parsed

LOG = logging.getLogger(__name__)


def log(stage, metadata=None, **values):
    LOG.info(json_bytes({"stage": stage, "document_id": (metadata or {}).get("document_id"), **values}).decode("utf-8"))


def delivery(services, store, metadata, owner):
    if metadata.get("notification_status") != "PENDING":
        return metadata
    try:
        services.notify(metadata)
        return store.notified(metadata, owner)
    except LostLease:
        raise
    except Exception as exc:
        attempts = int(metadata.get("notification_attempts", 0)) + 1
        LOG.error(json_bytes({"stage": "notification_failed", "document_id": metadata["document_id"], "error_code": safe_error(exc)}).decode())
        if attempts >= 8:
            return store.update(metadata, owner, {"notification_status": "FAILED", "notification_attempts": attempts, "lease_until": 0}, remove=("work_pk", "due_at"))
        return store.defer(metadata, owner, {"notification_attempts": attempts}, delay=min(900, 60 * 2 ** attempts))


def complete(services, store, metadata, owner, response, partial=False):
    config = services.config
    parsed = parse(response, metadata["document_type"])
    if parsed["pages"] > config.max_pages or len(json_bytes(parsed)) > config.max_result_mb * 1024 ** 2:
        raise InvalidDocument("Result exceeds configured page/memory guard for this lab")
    parsed_key = f"{config.parsed_prefix}{metadata['document_id']}.json.gz"
    services.save_json(parsed_key, parsed)
    children = []
    for record in records(parsed):
        item = {**record, "PK": metadata["PK"], "document_id": metadata["document_id"],
                "s3_key": metadata["s3_key"], "document_type": metadata["document_type"]}
        if len(json_bytes(item)) > 300_000:
            overflow_key = f"{config.parsed_prefix}{metadata['document_id']}/{record['SK'].replace('#', '-')}.json.gz"
            services.save_json(overflow_key, item)
            item = {name: item[name] for name in ("PK", "SK", "document_id", "s3_key", "document_type", "item_type")}
            item["overflow_key"] = overflow_key
        children.append(item)
    store.put_children(children)
    status = "PARTIAL" if partial else "COMPLETED"
    counts = {name: len(parsed[name]) for name in ("fields", "line_items", "table_cells")}
    csv_meta = {**metadata, "status": status, "completed_at": iso_now()}
    csv_prefix = export_parsed(services, csv_meta, parsed)
    metadata = store.finish(metadata, owner, status, {"pages": parsed["pages"], "counts": counts,
        "parsed_key": parsed_key, "csv_prefix": csv_prefix, "warning_count": len(parsed["warnings"])})
    log("document_completed", metadata, status=status, counts=counts)
    return delivery(services, store, metadata, owner)


def failure(services, store, metadata, owner, exc):
    if isinstance(exc, LostLease):
        log("lease_lost", metadata)
        return metadata
    current = store.get(metadata["document_id"]) or metadata
    if current["status"] in TERMINAL:
        return current  # Never downgrade a persisted extraction result because mail failed.
    attempts = int(current.get("error_attempts", 0)) + 1
    code = safe_error(exc)
    log("document_error", current, error_code=code, attempt=attempts)
    if retryable(exc) and attempts < services.config.max_attempts:
        return store.defer(current, owner, {"status": "SUBMITTED" if current.get("job_id") else "RETRYABLE",
                                           "error_attempts": attempts, "error_code": code}, delay=min(900, 30 * 2 ** attempts))
    status = "REJECTED" if isinstance(exc, InvalidDocument) else "FAILED"
    terminal = store.finish(current, owner, status, {"error_attempts": attempts, "error_code": code})
    return delivery(services, store, terminal, owner)


