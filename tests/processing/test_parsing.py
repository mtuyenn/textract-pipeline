import pytest

from textract_pipeline.processing.parsing import merge_pages, parse_document, parse_expense, records, text_of


def expense(name, value, page=1):
    return {"Type": {"Text": name, "Confidence": 98}, "ValueDetection": {"Text": value, "Confidence": 96}, "PageNumber": page}


def test_forms_checkbox_confidence_merged_spans(form_response):
    parsed = parse_document(form_response)
    assert parsed["fields"] == [{"field_name": "NAME", "label": "NAME:", "value": "SYNTHETIC SELECTED", "confidence": 97, "page": 1}]
    assert [cell["value"] for cell in parsed["table_cells"]] == ["SYNTHETIC", "SYNTHETIC"]
    assert parsed["table_cells"][1]["merged"] is True
    assert parsed["table_cells"][1]["column_span"] == 2
    assert [item["SK"] for item in records(parsed)] == ["FIELD#000001", "CELL#00000001", "CELL#00000002"]


def test_cross_fragment_relationships(form_response):
    first = {"DocumentMetadata": {"Pages": 2}, "Blocks": form_response["Blocks"][:3]}
    second = {"DocumentMetadata": {"Pages": 2}, "Blocks": form_response["Blocks"][3:]}
    result = parse_document(merge_pages([first, second], "form"))
    assert result["pages"] == 2
    assert result["fields"][0]["value"] == "SYNTHETIC SELECTED"


def test_duplicate_expense_types_and_fragmented_lines():
    def response(lines, summary):
        return {"ExpenseDocuments": [{"ExpenseIndex": 1, "SummaryFields": summary,
            "LineItemGroups": [{"LineItemGroupIndex": 1, "LineItems": lines}]}]}
    summary = [expense("OTHER", "A"), expense("OTHER", "B"), expense("TOTAL", "$25.00")]
    pages = [response([{"LineItemExpenseFields": [expense("ITEM", "PAPER"), expense("PRICE", "$10.00")]}], summary),
             response([{"LineItemExpenseFields": [expense("ITEM", "PEN", 2), expense("PRICE", "$15.00", 2)]}], summary)]
    parsed = parse_expense(merge_pages(pages, "invoice"))
    assert [field["value"] for field in parsed["fields"]] == ["A", "B", "$25.00"]
    assert [line["line_number"] for line in parsed["line_items"]] == [1, 2]
    assert parsed["line_items"][1]["page"] == 2
    assert parsed["line_items"][1]["fields"][1]["confidence"] == 96


def test_missing_relationship_and_cycles():
    blocks = {"a": {"Id": "a", "Relationships": [{"Type": "CHILD", "Ids": ["a", "missing"]}]}}
    assert text_of(blocks["a"], blocks) == ""
    assert parse_document({})["fields"] == []


@pytest.mark.parametrize("status,expected", [("SELECTED", "SELECTED"), ("NOT_SELECTED", "NOT_SELECTED")])
def test_selections(status, expected):
    assert text_of({"Id": "s", "BlockType": "SELECTION_ELEMENT", "SelectionStatus": status}, {}) == expected
