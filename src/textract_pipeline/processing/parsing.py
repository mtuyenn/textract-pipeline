"""Pure parsers: preserve confidence, pages, duplicate types, spans and selections."""

from collections import OrderedDict

from ..models import field_name, json_bytes


def text_of(block, index, seen=None):
    seen = set() if seen is None else seen
    identity = block.get("Id")
    if identity in seen:
        return ""
    seen.add(identity)
    if block.get("BlockType") == "WORD":
        return block.get("Text", "")
    if block.get("BlockType") == "SELECTION_ELEMENT":
        return "SELECTED" if block.get("SelectionStatus") == "SELECTED" else "NOT_SELECTED"
    values = []
    for relation in block.get("Relationships", []):
        if relation.get("Type") == "CHILD":
            for child in relation.get("Ids", []):
                text = text_of(index.get(child, {}), index, seen)
                if text:
                    values.append(text)
    return " ".join(values)


def linked(block, relation_type, index):
    return [index[identity] for relation in block.get("Relationships", [])
            if relation.get("Type") == relation_type for identity in relation.get("Ids", []) if identity in index]


def empty_result(response):
    return {"fields": [], "line_items": [], "table_cells": [],
            "pages": int(response.get("DocumentMetadata", {}).get("Pages", 1)),
            "warnings": response.get("Warnings", [])}


def parse_document(response):
    result = empty_result(response)
    blocks = response.get("Blocks", [])
    index = {block["Id"]: block for block in blocks if "Id" in block}
    for block in blocks:
        if block.get("BlockType") == "KEY_VALUE_SET" and "KEY" in block.get("EntityTypes", []):
            values = linked(block, "VALUE", index)
            confidences = [b["Confidence"] for b in [block] + values if "Confidence" in b]
            label = text_of(block, index)
            result["fields"].append({"field_name": field_name(label), "label": label,
                                     "value": " ".join(text_of(b, index) for b in values),
                                     "confidence": min(confidences) if confidences else None,
                                     "page": block.get("Page", 1)})
    table_number = 0
    for block in blocks:
        if block.get("BlockType") != "TABLE":
            continue
        table_number += 1
        title = " ".join(text_of(b, index) for b in linked(block, "TABLE_TITLE", index))
        footer = " ".join(text_of(b, index) for b in linked(block, "TABLE_FOOTER", index))
        for cell in linked(block, "CHILD", index) + linked(block, "MERGED_CELL", index):
            if cell.get("BlockType") not in {"CELL", "MERGED_CELL"}:
                continue
            result["table_cells"].append({
                "table_number": table_number, "page": cell.get("Page", block.get("Page", 1)),
                "row": int(cell.get("RowIndex", 1)), "column": int(cell.get("ColumnIndex", 1)),
                "row_span": int(cell.get("RowSpan", 1)), "column_span": int(cell.get("ColumnSpan", 1)),
                "value": text_of(cell, index), "confidence": cell.get("Confidence"),
                "merged": cell.get("BlockType") == "MERGED_CELL", "entity_types": cell.get("EntityTypes", []),
                "table_title": title, "table_footer": footer,
            })
    return result


def expense_field(field):
    detection = field.get("ValueDetection", {})
    return {"field_name": field.get("Type", {}).get("Text", "UNKNOWN"),
            "label": field.get("LabelDetection", {}).get("Text", ""),
            "value": detection.get("Text", ""), "confidence": detection.get("Confidence"),
            "type_confidence": field.get("Type", {}).get("Confidence"), "page": field.get("PageNumber", 1)}


def parse_expense(response):
    result = empty_result(response)
    for expense in response.get("ExpenseDocuments", []):
        expense_index = expense.get("ExpenseIndex", 1)
        for field in expense.get("SummaryFields", []):
            result["fields"].append({**expense_field(field), "expense_index": expense_index})
        for group in expense.get("LineItemGroups", []):
            for number, line in enumerate(group.get("LineItems", []), 1):
                fields = [expense_field(field) for field in line.get("LineItemExpenseFields", [])]
                result["line_items"].append({"expense_index": expense_index,
                    "group_index": group.get("LineItemGroupIndex", 1), "line_number": number,
                    "page": min((f["page"] for f in fields), default=1), "fields": fields})
    return result


def merge_pages(pages, kind):
    """Merge Get pagination; related blocks may be in different result fragments."""
    merged = {"DocumentMetadata": {"Pages": 1}, "Warnings": []}
    blocks = OrderedDict()
    expenses = OrderedDict()
    for response in pages:
        merged["DocumentMetadata"]["Pages"] = max(merged["DocumentMetadata"]["Pages"], response.get("DocumentMetadata", {}).get("Pages", 1))
        merged["Warnings"].extend(response.get("Warnings", []))
        for block in response.get("Blocks", []):
            blocks[block["Id"]] = block
        for expense in response.get("ExpenseDocuments", []):
            identity = expense.get("ExpenseIndex", 1)
            target = expenses.setdefault(identity, {"ExpenseIndex": identity, "summary": OrderedDict(), "groups": OrderedDict()})
            for field in expense.get("SummaryFields", []):
                target["summary"][json_bytes(field)] = field
            for group in expense.get("LineItemGroups", []):
                target["groups"].setdefault(group.get("LineItemGroupIndex", 1), []).extend(group.get("LineItems", []))
    if kind == "invoice":
        merged["ExpenseDocuments"] = [{"ExpenseIndex": target["ExpenseIndex"],
            "SummaryFields": list(target["summary"].values()),
            "LineItemGroups": [{"LineItemGroupIndex": group_id, "LineItems": rows} for group_id, rows in target["groups"].items()]}
            for target in expenses.values()]
    else:
        merged["Blocks"] = list(blocks.values())
    return merged


def parse(response, kind):
    return parse_expense(response) if kind == "invoice" else parse_document(response)


def records(result):
    for index, field in enumerate(result["fields"], 1):
        yield {"SK": f"FIELD#{index:06d}", "item_type": "FIELD", **field}
    for index, line in enumerate(result["line_items"], 1):
        yield {"SK": f"LINE#{index:06d}", "item_type": "LINE_ITEM", **line}
    for index, cell in enumerate(result["table_cells"], 1):
        yield {"SK": f"CELL#{index:08d}", "item_type": "TABLE_CELL", **cell}
