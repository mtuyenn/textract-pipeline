"""Collect async results, persist pagination checkpoints and recover pending work."""

from ..models import InvalidDocument, TERMINAL
from .parsing import merge_pages
from .finalize_document import complete, delivery, failure, log
from .process_document import process_claimed


def remaining(context):
    return context.get_remaining_time_in_millis() if context and hasattr(context, "get_remaining_time_in_millis") else 180_000


def collect(services, store, metadata, owner, context):
    try:
        if int(store.clock()) - int(metadata.get("submitted_at_epoch", store.clock())) > 6 * 24 * 3600:
            raise InvalidDocument("Textract job is near its seven-day result expiry")
        while not metadata.get("results_ready"):
            if remaining(context) < 20_000:
                return store.defer(metadata, owner)
            response = services.get_result(metadata)
            status = response.get("JobStatus")
            if status == "IN_PROGRESS":
                return store.defer(metadata, owner, {"status": "SUBMITTED"})
            if status == "FAILED":
                log("document_error", metadata, error_code="TextractJobFailed")
                failed = store.finish(metadata, owner, "FAILED", {"error_code": "TextractJobFailed"})
                return delivery(services, store, failed, owner)
            if status not in {"SUCCEEDED", "PARTIAL_SUCCESS"}:
                raise InvalidDocument("Unknown Textract job status")
            if response.get("DocumentMetadata", {}).get("Pages", 1) > services.config.max_pages:
                raise InvalidDocument("Too many pages for the configured lab limit")
            chunk = int(metadata.get("raw_chunk_count", 0))
            size = services.save_json(f"{services.config.raw_prefix}{metadata['document_id']}/chunks/{chunk:06d}.json.gz", response)
            total_size = int(metadata.get("raw_bytes", 0)) + size
            if total_size > services.config.max_result_mb * 1024 ** 2:
                raise InvalidDocument("Raw result exceeds configured memory limit")
            token = response.get("NextToken")
            metadata = store.update(metadata, owner, {"raw_chunk_count": chunk + 1, "raw_bytes": total_size,
                "result_next_token": token, "results_ready": not bool(token),
                "partial_result": bool(metadata.get("partial_result")) or status == "PARTIAL_SUCCESS"})
        if remaining(context) < 30_000:
            return store.defer(metadata, owner)
        pages = [services.load_json(f"{services.config.raw_prefix}{metadata['document_id']}/chunks/{index:06d}.json.gz")
                 for index in range(int(metadata["raw_chunk_count"]))]
        response = merge_pages(pages, metadata["document_type"])
        return complete(services, store, metadata, owner, response, partial=bool(metadata.get("partial_result")))
    except Exception as exc:
        return failure(services, store, metadata, owner, exc)


def handle(context, services, store):
    results = []
    for candidate in store.due():
        if remaining(context) < 25_000:
            break
        metadata = store.claim(candidate, context.aws_request_id)
        if not metadata:
            continue
        owner = context.aws_request_id
        if metadata["status"] in TERMINAL:
            result = delivery(services, store, metadata, owner)
        elif metadata.get("job_id"):
            result = collect(services, store, metadata, owner, context)
        else:
            # Recovers timeout/crash before Start... or before the JobId was saved.
            result = process_claimed(services, store, metadata, owner)
        results.append({"document_id": result["document_id"], "status": result["status"]})
    log("collector_tick", jobs=len(results))
    return {"results": results}


