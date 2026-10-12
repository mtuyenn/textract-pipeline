import csv
import io

import pytest

from textract_pipeline.processing.exporting import csv_safe, encode_csv, export, table_rows
from textract_pipeline.processing.process_document import handle


def rows(data):
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))


@pytest.mark.parametrize("value", ["=SUM(A1)", "+command", "-command", "@formula", "  =formula", "\ttab"])
def test_csv_formula_protection(value):
    assert csv_safe(value) == "'" + value


def test_csv_quotes_bom_unicode_and_null():
    data = encode_csv("fields", [{"value": 'Tiếng Việt, "test"\nline', "confidence": None}])
    assert data.startswith(b"\xef\xbb\xbf")
    assert rows(data)[0]["value"] == 'Tiếng Việt, "test"\nline'
    assert rows(data)[0]["confidence"] == ""


def test_export_excludes_half_written_and_partial_by_default(setup, form_response):
    setup.services.analyze_response = form_response
    event = {"Records": [{"eventSource": "aws:s3", "eventName": "ObjectCreated:Put", "s3": {
        "bucket": {"name": "test-bucket"}, "object": {"key": "input/forms/test.png", "eTag": "one"}}}]}
    handle(event, setup.context, setup.services, setup.store)
    meta = next(item for item in setup.table.data.values() if item["SK"] == "META")
    for status, included in [("PROCESSING", False), ("FAILED", False), ("PARTIAL", False), ("COMPLETED", True)]:
        meta["status"] = status
        result = export(setup.services, setup.store, {"dataset": "all"})
        assert result["fields"]["rows"] == int(included)
        assert len(rows(setup.services.csvs["output/exports/documents.csv"])) == 1
    meta["status"] = "PARTIAL"
    assert export(setup.services, setup.store, {"dataset": "fields", "include_partial": True})["fields"]["rows"] == 1


def test_table_rows_gaps_and_merged_overlay():
    base = {"document_id": "id", "s3_key": "key", "table_number": 1, "page": 1, "row": 1}
    values = list(table_rows([{**base, "column": 1, "value": "A"}, {**base, "column": 3, "value": "C"},
                             {**base, "column": 1, "value": "A C", "merged": True}]))
    assert values[0]["cells"] == ["A", "", "C"]


