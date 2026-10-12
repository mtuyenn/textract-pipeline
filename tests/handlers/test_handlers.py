"""Exercise the deployed entry points with local service boundaries."""

import csv
import io

import pytest

from textract_pipeline.handlers import collector, exporter, processor


@pytest.mark.parametrize("extension", ["png", "pdf"])
def test_handlers_process_collect_and_export(setup, form_response, monkeypatch, extension):
    for module in (processor, collector, exporter):
        monkeypatch.setattr(module, "runtime", lambda: (setup.services, setup.store, setup.config))
    setup.services.analyze_response = form_response
    event = {"Records": [{"eventSource": "aws:s3", "eventName": "ObjectCreated:Put", "s3": {
        "bucket": {"name": "test-bucket"}, "object": {"key": f"input/forms/test.{extension}", "eTag": "one"}}}]}
    processed = processor.lambda_handler(event, setup.context)
    if extension == "pdf":
        assert processed["results"][0]["status"] == "SUBMITTED"
        setup.clock[0] += 60
        setup.services.responses = [{"JobStatus": "SUCCEEDED", **form_response}]
        collected = collector.lambda_handler({}, setup.context)
        assert collected["results"][0]["status"] == "COMPLETED"
    else:
        assert processed["results"][0]["status"] == "COMPLETED"
    result = exporter.lambda_handler({"dataset": "all"}, setup.context)
    assert result["exports"]["fields"]["rows"] == 1
    assert result["exports"]["table_cells"]["rows"] == 2
    fields = list(csv.DictReader(io.StringIO(setup.services.csvs["output/exports/fields.csv"].decode("utf-8-sig"))))
    assert fields[0]["value"] == "SYNTHETIC SELECTED"
    assert processor.lambda_handler(event, setup.context)["results"][0]["status"] == "DUPLICATE_OR_IN_PROGRESS"
    assert len(setup.services.notifications) == 1
