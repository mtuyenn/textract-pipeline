"""UTF-8 BOM CSV exports. Never export half-written child records."""

import csv
import io
from collections import defaultdict

from ..models import json_bytes

HEADERS = {
    "documents": ["document_id", "s3_key", "document_type", "status", "pages", "created_at", "completed_at", "error_code", "notification_status"],
    "fields": ["document_id", "s3_key", "field_name", "label", "value", "confidence", "page", "expense_index"],
    "line_items": ["document_id", "s3_key", "expense_index", "group_index", "line_number", "page", "fields"],
    "table_cells": ["document_id", "s3_key", "table_number", "page", "row", "column", "row_span", "column_span", "merged", "value", "confidence", "entity_types", "table_title", "table_footer"],
    "table_rows": ["document_id", "s3_key", "table_number", "page", "row", "cells"],
}


def csv_safe(value):
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json_bytes(value).decode("utf-8")
    if isinstance(value, str) and (value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n"))):
        return "'" + value
    return value


def encode_csv(dataset, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=HEADERS[dataset], extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: csv_safe(row.get(key)) for key in HEADERS[dataset]})
    return stream.getvalue().encode("utf-8-sig")


def table_rows(cells):
    rows = defaultdict(dict)
    for cell in cells:
        if cell.get("merged"):
            continue  # Merged overlays are preserved in table_cells.csv, not counted twice.
        identity = (cell["document_id"], cell["s3_key"], cell["table_number"], cell["page"], cell["row"])
        rows[identity][int(cell["column"])] = cell["value"]
    for (doc_id, key, table_number, page, row), columns in sorted(rows.items()):
        yield {"document_id": doc_id, "s3_key": key, "table_number": table_number, "page": page,
               "row": row, "cells": [columns.get(col, "") for col in range(1, max(columns) + 1)]}


def export_parsed(services, metadata, result):
    identity = {name: metadata[name] for name in ("document_id", "s3_key")}
    datasets = {"documents": [{**metadata, "pages": result["pages"]}],
                **{dataset: [{**record, **identity} for record in result[dataset]]
                   for dataset in ("fields", "line_items", "table_cells")}}
    datasets["table_rows"] = list(table_rows(datasets["table_cells"]))
    prefix = f"{services.config.output_prefix}{metadata['document_id']}/"
    for name, rows in datasets.items():
        services.put_csv(f"{prefix}{name}.csv", encode_csv(name, rows))
    return prefix


def export(services, store, event):
    dataset = event.get("dataset", "all")
    if dataset != "all" and dataset not in HEADERS:
        raise ValueError("dataset must be all/documents/fields/line_items/table_cells/table_rows")
    items = list(store.items(event.get("document_id")))
    metadata = {item["document_id"]: item for item in items if item.get("SK") == "META"}
    include_partial = bool(event.get("include_partial", False))
    allowed = {identity for identity, meta in metadata.items()
               if meta["status"] == "COMPLETED" or (include_partial and meta["status"] == "PARTIAL")}
    datasets = {name: [] for name in HEADERS}
    datasets["documents"] = sorted(metadata.values(), key=lambda row: (row.get("created_at", ""), row["document_id"]))
    mapping = {"FIELD": "fields", "LINE_ITEM": "line_items", "TABLE_CELL": "table_cells"}
    for item in items:
        if item.get("item_type") not in mapping or item["document_id"] not in allowed:
            continue
        if item.get("overflow_key"):
            item = services.load_json(item["overflow_key"])
        datasets[mapping[item["item_type"]]].append(item)
    datasets["table_rows"] = list(table_rows(datasets["table_cells"]))
    for name in ("fields", "line_items", "table_cells"):
        datasets[name].sort(key=lambda row: (row["document_id"], row["SK"]))
    # All names are generated internally so callers cannot write into input/.
    prefix = f"{services.config.output_prefix}exports/"
    outputs = {}
    for name in HEADERS if dataset == "all" else [dataset]:
        key = f"{prefix}{name}.csv"
        services.put_csv(key, encode_csv(name, datasets[name]))
        outputs[name] = {"rows": len(datasets[name]), "s3_uri": f"s3://{services.config.bucket_name}/{key}"}
    return outputs


