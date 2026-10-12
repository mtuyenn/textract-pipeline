import copy

import pytest

from textract_pipeline.processing.collect_result import handle as collect
from textract_pipeline.models import LostLease
from textract_pipeline.processing.process_document import handle, process_claimed
from conftest import client_error


def event(key="input/forms/test.png"):
    return {"Records": [{"eventSource": "aws:s3", "eventName": "ObjectCreated:Put",
                         "s3": {"bucket": {"name": "test-bucket"}, "object": {"key": key, "eTag": "etag"}}}]}


def metadata(setup):
    return next(item for item in setup.table.data.values() if item["SK"] == "META")


def test_sync_end_to_end_and_duplicate(setup, form_response):
    setup.services.analyze_response = form_response
    result = handle(event(), setup.context, setup.services, setup.store)
    assert result["results"][0]["status"] == "COMPLETED"
    item = metadata(setup)
    assert item["counts"] == {"fields": 1, "line_items": 0, "table_cells": 2}
    assert item["notification_status"] == "DELIVERED"
    assert "work_pk" not in item
    assert len(setup.services.csvs) == 5
    assert b"SYNTHETIC SELECTED" in setup.services.csvs[item["csv_prefix"] + "fields.csv"]
    assert handle(event(), setup.context, setup.services, setup.store)["results"][0]["status"] == "DUPLICATE_OR_IN_PROGRESS"
    assert setup.services.calls.count("analyze") == 1


@pytest.mark.parametrize("key", ["output/test.csv", "raw-results/test.json.gz", "input/", "input/test.png"])
def test_output_and_unrouted_events_are_ignored(setup, key):
    assert handle(event(key), setup.context, setup.services, setup.store)["results"][0]["status"] == "IGNORED"
    assert not setup.table.data and not setup.services.calls


def test_async_checkpoint_and_resume(setup, form_response):
    assert handle(event("input/forms/test.pdf"), setup.context, setup.services, setup.store)["results"][0]["status"] == "SUBMITTED"
    assert setup.services.calls == ["start"]
    setup.clock[0] += 60
    setup.services.responses = [{"JobStatus": "IN_PROGRESS"}]
    collect(setup.context, setup.services, setup.store)
    assert metadata(setup)["status"] == "SUBMITTED"
    setup.clock[0] += 60
    setup.services.responses = [{"JobStatus": "SUCCEEDED", "NextToken": "page-two", "Blocks": form_response["Blocks"][:3], "DocumentMetadata": {"Pages": 2}}]
    # handle budget, first get budget, next get budget -> defer with durable NextToken.
    budgets = iter([180000, 180000, 15000])
    setup.context.get_remaining_time_in_millis = lambda: next(budgets)
    collect(setup.context, setup.services, setup.store)
    assert metadata(setup)["result_next_token"] == "page-two"
    assert metadata(setup)["raw_chunk_count"] == 1
    setup.clock[0] += 60
    setup.context.get_remaining_time_in_millis = lambda: 180000
    setup.services.responses = [{"JobStatus": "SUCCEEDED", "Blocks": form_response["Blocks"][3:], "DocumentMetadata": {"Pages": 2}}]
    collect(setup.context, setup.services, setup.store)
    assert metadata(setup)["status"] == "COMPLETED"
    assert metadata(setup)["pages"] == 2
    assert ("get", "page-two") in setup.services.calls
    assert metadata(setup)["counts"]["fields"] == 1


def test_sns_failure_does_not_erase_success_and_recovers(setup):
    setup.services.notify_error = client_error()
    handle(event(), setup.context, setup.services, setup.store)
    assert metadata(setup)["status"] == "COMPLETED"
    assert metadata(setup)["notification_status"] == "PENDING"
    assert metadata(setup)["notification_attempts"] == 1
    setup.services.notify_error = None
    setup.clock[0] += 120
    collect(setup.context, setup.services, setup.store)
    assert metadata(setup)["notification_status"] == "DELIVERED"
    assert setup.services.calls.count("analyze") == 1


def test_retry_after_csv_failure_reuses_persisted_ocr(setup, form_response):
    setup.services.analyze_response = form_response
    setup.services.csv_error = client_error()
    handle(event(), setup.context, setup.services, setup.store)
    assert metadata(setup)["status"] == "RETRYABLE"
    setup.clock[0] += 60
    collect(setup.context, setup.services, setup.store)
    assert metadata(setup)["status"] == "COMPLETED"
    assert setup.services.calls.count("analyze") == 1
    assert len([i for i in setup.table.data.values() if i["item_type"] == "FIELD"]) == 1


def test_lease_competition_recovery_and_old_owner_fenced(setup):
    source = setup.services.inspect("test-bucket", "input/forms/test.pdf", {"eTag": "etag"})
    first = setup.store.claim_source(source, "old")
    assert setup.store.claim_source(source, "new") is None
    setup.clock[0] += 241
    second = setup.store.claim_source(source, "new")
    assert second["lease_owner"] == "new"
    with pytest.raises(LostLease):
        setup.store.update(first, "old", {"status": "FAILED"})
    result = process_claimed(setup.services, setup.store, second, "new")
    assert result["status"] == "SUBMITTED"


def test_failed_async_job_is_not_success(setup):
    handle(event("input/invoices/test.pdf"), setup.context, setup.services, setup.store)
    setup.clock[0] += 60
    setup.services.responses = [{"JobStatus": "FAILED"}]
    collect(setup.context, setup.services, setup.store)
    assert metadata(setup)["status"] == "FAILED"
    assert metadata(setup)["error_code"] == "TextractJobFailed"
    assert not setup.services.csvs


def test_partial_async_job_preserves_status(setup):
    handle(event("input/forms/test.pdf"), setup.context, setup.services, setup.store)
    setup.clock[0] += 60
    setup.services.responses = [{"JobStatus": "PARTIAL_SUCCESS", "Blocks": [], "Warnings": [{"ErrorCode": "PAGE_ERROR", "Pages": [2]}]}]
    collect(setup.context, setup.services, setup.store)
    assert metadata(setup)["status"] == "PARTIAL"
    assert metadata(setup)["warning_count"] == 1


def test_unsupported_file_rejected(setup):
    assert handle(event("input/forms/test.txt"), setup.context, setup.services, setup.store)["results"][0]["status"] == "REJECTED"
    assert not setup.services.calls


def test_large_child_is_offloaded(setup, form_response):
    form_response["Blocks"][3]["Text"] = "x" * 310000
    setup.services.analyze_response = form_response
    handle(event(), setup.context, setup.services, setup.store)
    field = next(item for item in setup.table.data.values() if item["item_type"] == "FIELD")
    assert "overflow_key" in field and "value" not in field
    assert setup.services.jsons[field["overflow_key"]]["value"].startswith("x" * 310000)


def test_notification_retry_exhaustion_keeps_extraction(setup):
    setup.services.notify_error = client_error()
    handle(event(), setup.context, setup.services, setup.store)
    for _ in range(7):
        setup.clock[0] += 1000
        collect(setup.context, setup.services, setup.store)
    assert metadata(setup)["status"] == "COMPLETED"
    assert metadata(setup)["notification_status"] == "FAILED"
    assert "work_pk" not in metadata(setup)


def test_processing_retry_exhaustion_becomes_failed(setup):
    setup.services.analysis_error = client_error()
    handle(event(), setup.context, setup.services, setup.store)
    for _ in range(4):
        setup.clock[0] += 1000
        collect(setup.context, setup.services, setup.store)
    assert metadata(setup)["status"] == "FAILED"
    assert metadata(setup)["error_attempts"] == 5
    assert setup.services.calls.count("analyze") == 5


def test_expired_async_result_is_rejected_before_api(setup):
    handle(event("input/forms/test.pdf"), setup.context, setup.services, setup.store)
    setup.clock[0] += 7 * 86400
    collect(setup.context, setup.services, setup.store)
    assert metadata(setup)["status"] == "REJECTED"
    assert setup.services.calls == ["start"]


def test_async_page_limit_stops_before_merge(setup):
    handle(event("input/forms/test.pdf"), setup.context, setup.services, setup.store)
    setup.clock[0] += 60
    setup.services.responses = [{"JobStatus": "SUCCEEDED", "DocumentMetadata": {"Pages": 101}, "Blocks": []}]
    collect(setup.context, setup.services, setup.store)
    assert metadata(setup)["status"] == "REJECTED"
    assert not setup.services.csvs


def test_key_decode_and_distinct_source_revisions(setup):
    source_event = event("input/forms/a+b%2Bc.png")
    handle(source_event, setup.context, setup.services, setup.store)
    assert metadata(setup)["s3_key"] == "input/forms/a b+c.png"
    source_event["Records"][0]["s3"]["object"]["eTag"] = "new-etag"
    handle(source_event, setup.context, setup.services, setup.store)
    metas = [item for item in setup.table.data.values() if item["SK"] == "META"]
    assert len(metas) == 2
    assert metas[0]["document_id"] != metas[1]["document_id"]


def test_oversized_sync_input_is_rejected_without_ocr(setup):
    source = setup.services.inspect("test-bucket", "input/forms/test.png", {"eTag": "etag"})
    source["size_bytes"] = 10 * 1024 ** 2 + 1
    claimed = setup.store.claim_source(source, setup.context.aws_request_id)
    assert process_claimed(setup.services, setup.store, claimed, setup.context.aws_request_id)["status"] == "REJECTED"
    assert not setup.services.calls
