"""Validate S3 source events and start or resume document extraction."""

from pathlib import PurePosixPath
from urllib.parse import unquote_plus

from ..models import InvalidDocument
from .finalize_document import complete, failure, log


def process_claimed(services, store, metadata, owner):
    try:
        extension = PurePosixPath(metadata["s3_key"]).suffix.lower()
        if extension not in {".png", ".jpg", ".jpeg", ".pdf", ".tif", ".tiff"}:
            raise InvalidDocument("Unsupported file format")
        mode = metadata.get("processing_mode", "auto")
        if mode not in {"auto", "sync", "async"}:
            raise InvalidDocument("Invalid processing-mode metadata")
        asynchronous = mode == "async" or (mode == "auto" and extension in {".pdf", ".tif", ".tiff"})
        image = extension in {".png", ".jpg", ".jpeg"}
        limit_mb = 10 if image or not asynchronous else services.config.max_async_mb
        if not 0 < metadata["size_bytes"] <= limit_mb * 1024 ** 2:
            raise InvalidDocument("File is empty or exceeds configured size limit")
        if asynchronous:
            job_id = services.start(metadata)
            submitted = store.defer(metadata, owner, {"status": "SUBMITTED", "job_id": job_id,
                "submitted_at_epoch": int(store.clock()), "raw_chunk_count": 0, "raw_bytes": 0})
            log("job_submitted", submitted)
            return submitted
        # Resume the same persisted extraction after a downstream S3/DDB/CSV retry.
        # This prevents new OCR results leaving stale deterministic child records.
        if metadata.get("raw_chunk_count") == 1:
            response = services.load_json(f"{services.config.raw_prefix}{metadata['document_id']}/chunks/000000.json.gz")
            return complete(services, store, metadata, owner, response)
        response = services.analyze(metadata)
        size = services.save_json(f"{services.config.raw_prefix}{metadata['document_id']}/chunks/000000.json.gz", response)
        if size > services.config.max_result_mb * 1024 ** 2:
            raise InvalidDocument("Raw result exceeds configured memory limit")
        metadata = store.update(metadata, owner, {"raw_chunk_count": 1, "raw_bytes": size})
        return complete(services, store, metadata, owner, response)
    except Exception as exc:
        return failure(services, store, metadata, owner, exc)


def handle(event, context, services, store):
    outcomes = []
    for record in event.get("Records", []):
        if record.get("eventSource") != "aws:s3" or not record.get("eventName", "").startswith("ObjectCreated:"):
            continue
        data = record["s3"]
        bucket = data["bucket"]["name"]
        key = unquote_plus(data["object"]["key"])
        if key.endswith("/") or not key.startswith(("input/invoices/", "input/forms/")):
            outcomes.append({"status": "IGNORED", "key": key})
            continue
        source = services.inspect(bucket, key, data["object"])
        if source is None:
            outcomes.append({"status": "STALE_EVENT", "key": key})
            continue
        owner = context.aws_request_id
        metadata = store.claim_source(source, owner)
        if metadata is None:
            outcomes.append({"document_id": source["document_id"], "status": "DUPLICATE_OR_IN_PROGRESS"})
            continue
        result = process_claimed(services, store, metadata, owner)
        outcomes.append({"document_id": result["document_id"], "status": result["status"]})
    return {"results": outcomes}


