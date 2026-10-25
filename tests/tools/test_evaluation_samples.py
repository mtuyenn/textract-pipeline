import json

import pytest

from tools.evaluate import evaluate, normalized_value
from tools.generate_samples import generate


def exports():
    return {"documents": [], "fields": [], "line_items": [], "table_cells": []}


def test_missing_and_failed_documents_remain_denominator():
    truth = [{"s3_key": "one", "fields": [{"field_name": "TOTAL", "value": "$12.50"}]},
             {"s3_key": "missing", "fields": [{"field_name": "NAME", "value": "X"}]}]
    actual = exports()
    actual["documents"] = [{"document_id": "ok", "s3_key": "one", "status": "COMPLETED"}]
    actual["fields"] = [{"document_id": "ok", "field_name": "TOTAL", "value": "12.5"}]
    result = evaluate(truth, actual)
    assert result["metrics"]["fields"] == {"correct": 1, "expected": 2, "predicted": 1, "accuracy": .5, "precision": 1}
    # Newer failed revision cannot be hidden by older successful one, even if stale children are supplied.
    actual["documents"].append({"document_id": "failed", "s3_key": "one", "status": "FAILED", "created_at": "later"})
    actual["fields"].append({"document_id": "failed", "field_name": "TOTAL", "value": "12.5"})
    assert evaluate(truth, actual)["metrics"]["fields"]["correct"] == 0


def test_duplicates_do_not_inflate_accuracy_and_extras_reduce_precision():
    truth = [{"s3_key": "one", "fields": [{"field_name": "NAME", "value": "X"}]}]
    actual = exports()
    actual["documents"] = [{"document_id": "ok", "s3_key": "one", "status": "COMPLETED"}]
    actual["fields"] = [{"document_id": "ok", "field_name": "NAME", "value": "X"}] * 2
    result = evaluate(truth, actual)
    assert result["metrics"]["fields"]["accuracy"] == 1
    assert result["metrics"]["fields"]["precision"] == .5


def test_line_and_cell_accuracy_wrong_value_wrong_position():
    truth = [{"s3_key": "one", "line_items": [{"line_number": 1, "fields": {"ITEM": "PAPER", "QUANTITY": "2"}}],
              "table_cells": [{"table_number": 1, "row": 1, "column": 1, "value": "A"}]}]
    actual = exports()
    actual["documents"] = [{"document_id": "ok", "s3_key": "one", "status": "COMPLETED"}]
    actual["line_items"] = [{"document_id": "ok", "line_number": "1", "fields": json.dumps([
        {"field_name": "ITEM", "value": "paper"}, {"field_name": "QUANTITY", "value": "3"}])}]
    actual["table_cells"] = [{"document_id": "ok", "table_number": "1", "row": "1", "column": "2", "value": "A"}]
    result = evaluate(truth, actual)
    assert result["metrics"]["line_item_fields"]["accuracy"] == .5
    assert result["line_items"]["accuracy"] == 0
    assert result["metrics"]["table_cells"]["accuracy"] == 0


def test_normalization_keeps_invoice_leading_zeros():
    assert normalized_value("00123", "INVOICE_RECEIPT_ID") != normalized_value("123", "INVOICE_RECEIPT_ID")
    assert normalized_value("$1,200.00", "TOTAL") == normalized_value("1200", "TOTAL")
    assert normalized_value(0, "QUANTITY") == "0"


def test_generate_30_images_pdf_and_truth(tmp_path):
    from PIL import Image
    manifest = generate(tmp_path, 30)
    assert len(manifest["documents"]) == 30
    assert len(list(tmp_path.rglob("*.png"))) == 30
    assert len({doc["s3_key"] for doc in manifest["documents"]}) == 30
    assert sum(len(doc["fields"]) for doc in manifest["documents"]) == 120
    assert sum(len(doc["table_cells"]) for doc in manifest["documents"]) == 180
    for doc in manifest["documents"]:
        with Image.open(tmp_path / doc["s3_key"]) as image:
            assert image.size == (1275, 1650)
    assert (tmp_path / manifest["async_demo"]["local_path"]).read_bytes().startswith(b"%PDF")


def test_sample_count_cannot_be_less_than_30(tmp_path):
    with pytest.raises(ValueError):
        generate(tmp_path, 29)
