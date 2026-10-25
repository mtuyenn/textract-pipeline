"""Ground-truth scoring: missing/failed documents remain in the denominator."""

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

import run_artifacts as runs


NUMERIC_FIELDS = {"TOTAL", "SUBTOTAL", "TAX", "PRICE", "UNIT_PRICE", "QUANTITY", "AMOUNT", "QTY"}


def normalized_name(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value or "").strip().rstrip(":")).upper()


def normalized_value(value, name=""):
    value = unicodedata.normalize("NFKC", "" if value is None else str(value)).strip()
    if value.startswith("'") and value[1:].lstrip().startswith(("=", "+", "-", "@")):
        value = value[1:]  # Remove only the exporter formula-protection prefix.
    if normalized_name(name) in NUMERIC_FIELDS:
        numeric = re.sub(r"[$€£,\s]", "", value)
        try:
            return str(Decimal(numeric).normalize())
        except InvalidOperation:
            pass
    return re.sub(r"\s+", " ", value).casefold()


def read_csv(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Missing required export: {path}")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def metrics(correct, expected, predicted):
    return {"correct": correct, "expected": expected, "predicted": predicted,
            "accuracy": correct / expected if expected else None,
            "precision": correct / predicted if predicted else (0.0 if expected else None)}


def evaluate(truth, exports):
    docs = exports["documents"]
    latest = {}
    for doc in sorted(docs, key=lambda item: (item.get("created_at", ""), item["document_id"])):
        latest[doc["s3_key"]] = doc  # Latest failed revision does not get replaced by an older success.
    selected = {doc["document_id"] for key, doc in latest.items()
                if key in {item["s3_key"] for item in truth} and doc.get("status") in {"COMPLETED", "PARTIAL"}}
    fields = Counter()
    line_fields = Counter()
    table_cells = Counter()
    table_groups = {}
    for row in exports["fields"]:
        if row["document_id"] in selected:
            fields[(row["document_id"], normalized_name(row["field_name"]), int(row.get("page") or 1), normalized_value(row["value"], row["field_name"]))] += 1
    for row in exports["line_items"]:
        if row["document_id"] not in selected:
            continue
        for field in json.loads(row["fields"]):
            # LINE_ITEM is an extra description Textract may return, not a required quantity/price field.
            if normalized_name(field["field_name"]) == "LINE_ITEM":
                continue
            identity = (row["document_id"], int(row.get("expense_index") or 1), int(row.get("group_index") or 1), int(row["line_number"]))
            line_fields[(*identity, normalized_name(field["field_name"]), normalized_value(field["value"], field["field_name"]))] += 1
    for row in exports["table_cells"]:
        if row["document_id"] in selected and str(row.get("merged", "")).lower() != "true":
            identity = (row["document_id"], int(row.get("page") or 1), int(row["table_number"]),
                        int(row["row"]), int(row["column"]), normalized_value(row["value"]))
            table_cells[identity] += 1
            table_groups.setdefault(identity[:3], []).append(identity[3:])
    counters = {"fields": fields, "line_item_fields": line_fields, "table_cells": table_cells}
    predicted = {name: sum(counter.values()) for name, counter in counters.items()}
    scores = {name: {"correct": 0, "expected": 0} for name in counters}
    missing = []
    status_counts = Counter()
    correct_lines = expected_lines = 0

    # Textract's TABLE block ordinal can include a key/value-looking layout before the
    # intended grid, so it is not a stable semantic table identifier. Map each
    # ground-truth table to the predicted table with the strongest page/row/column
    # overlap, then score the cell values within that table.
    expected_table_groups = {}
    for doc in truth:
        actual = latest.get(doc["s3_key"], {})
        doc_id = actual.get("document_id", "MISSING")
        for cell in doc.get("table_cells", []):
            group = (doc_id, int(cell.get("page", 1)), int(cell["table_number"]))
            expected_table_groups.setdefault(group, []).append(cell)
    table_mapping = {}
    for expected_group, expected_cells in expected_table_groups.items():
        document_id, page, _ = expected_group
        expected_positions = {(int(cell["row"]), int(cell["column"])) for cell in expected_cells}
        candidates = []
        for predicted_group, predicted_cells in table_groups.items():
            if predicted_group[:2] != (document_id, page):
                continue
            predicted_positions = {(row, column) for row, column, _ in predicted_cells}
            position_overlap = len(expected_positions & predicted_positions)
            if position_overlap:
                expected_values = Counter((int(cell["row"]), int(cell["column"]),
                                           normalized_value(cell["value"])) for cell in expected_cells)
                predicted_values = Counter((row, column, value) for row, column, value in predicted_cells)
                value_overlap = sum((expected_values & predicted_values).values())
                candidates.append(((position_overlap, value_overlap), predicted_group[2]))
        table_mapping[expected_group] = max(candidates)[1] if candidates else None

    def match(dataset, identity, detail):
        scores[dataset]["expected"] += 1
        if counters[dataset][identity] > 0:
            counters[dataset][identity] -= 1
            scores[dataset]["correct"] += 1
            return True
        missing.append({"dataset": dataset, **detail})
        return False

    for doc in truth:
        actual = latest.get(doc["s3_key"], {})
        doc_id = actual.get("document_id", "MISSING")
        status_counts[actual.get("status", "MISSING")] += 1
        for field in doc.get("fields", []):
            identity = (doc_id, normalized_name(field["field_name"]), int(field.get("page", 1)), normalized_value(field["value"], field["field_name"]))
            match("fields", identity, {"s3_key": doc["s3_key"], **field})
        for line in doc.get("line_items", []):
            expected_lines += 1
            good = True
            for name, value in line["fields"].items():
                identity = (doc_id, int(line.get("expense_index", 1)), int(line.get("group_index", 1)), int(line["line_number"]), normalized_name(name), normalized_value(value, name))
                good = match("line_item_fields", identity, {"s3_key": doc["s3_key"], "line_number": line["line_number"], "field_name": name, "value": value}) and good
            correct_lines += int(good)
        for cell in doc.get("table_cells", []):
            page = int(cell.get("page", 1))
            expected_group = (doc_id, page, int(cell["table_number"]))
            predicted_table = table_mapping.get(expected_group)
            identity = (doc_id, page, predicted_table, int(cell["row"]), int(cell["column"]), normalized_value(cell["value"]))
            match("table_cells", identity, {"s3_key": doc["s3_key"], **cell,
                                            "textract_table_number": predicted_table})
    return {"document_count": len(truth), "document_statuses": dict(status_counts),
            "metrics": {name: metrics(score["correct"], score["expected"], predicted[name]) for name, score in scores.items()},
            "line_items": metrics(correct_lines, expected_lines, len([r for r in exports["line_items"] if r["document_id"] in selected])),
            "mismatches": missing,
            "normalization": "NFKC, trim/case/whitespace; decimal normalization only for explicitly numeric field names",
            "table_matching": "Map each expected table to the Textract table on the same page with greatest row/column overlap; score cells by row, column, and normalized value. Textract table_number is an output ordinal, not a stable semantic identifier."}


def evaluation_run(truth_path=None, exports_path=None, directory=None, smoke_run=None):
    artifact_run = runs.Run.create(directory, "evaluation")
    print(f"Run: {artifact_run.path}")
    with artifact_run.step("evaluation"):
        source_smoke = None
        if smoke_run:
            source = runs.Run(smoke_run)
            source_smoke = source.read()
            if source_smoke["kind"] != "aws_smoke" or source_smoke["status"] != "PASS":
                raise ValueError("Accuracy evaluation requires a completed PASS aws_smoke run")
            source.validate_files()
            dataset_record = source_smoke["inputs"].get("dataset")
            exports_record = source_smoke["artifacts"].get("exports")
            smoke_record = source_smoke["artifacts"].get("smoke")
            if not dataset_record or not exports_record or not smoke_record:
                raise ValueError("Smoke run is missing its dataset, CSV exports, or smoke evidence")
            dataset_dir = artifact_run.capture("dataset", source.resolve(dataset_record["path"]),
                                               "inputs/dataset", dataset=True)
            truth_path = dataset_dir / "ground_truth.json"
            exports_path = artifact_run.capture("exports", source.resolve(exports_record["path"]),
                                                "inputs/exports")
            artifact_run.capture("source_smoke_manifest", source.manifest,
                                 "inputs/source-smoke-manifest.json")
            artifact_run.capture("source_smoke_evidence", source.resolve(smoke_record["path"]),
                                 "inputs/source-smoke.json")
            artifact_run.update_environment(region=source_smoke["environment"].get("region"),
                                            stack=source_smoke["environment"].get("stack"),
                                            account=source_smoke["environment"].get("account"))
        else:
            if not truth_path or not exports_path:
                raise ValueError("Provide --smoke-run or both --truth and --exports")
            truth_path = artifact_run.capture("ground_truth", truth_path, "inputs/ground_truth.json", dataset=True)
            exports_path = artifact_run.capture("exports", exports_path, "inputs/exports")
            source_manifest = Path(artifact_run.document["inputs"]["exports"]["source"]["path"])
            if artifact_run.document["inputs"]["exports"]["source"]["scope"] == "repository":
                source_manifest = runs.ROOT / source_manifest
            source_manifest = source_manifest.parent / "manifest.json"
            if source_manifest.is_file():
                artifact_run.capture("source_run_manifest", source_manifest, "inputs/source-run-manifest.json")
        manifest = json.loads(truth_path.read_text(encoding="utf-8"))
        truth = manifest["documents"]
        if len(truth) < 30:
            raise ValueError("Project evaluation requires >=30 ground-truth documents")
        if source_smoke:
            smoke_evidence = json.loads(artifact_run.resolve("inputs/source-smoke.json").read_text(encoding="utf-8"))
            uploaded_keys = {item.get("key") for item in smoke_evidence.get("uploads", [])}
            expected_keys = {item["s3_key"] for item in truth}
            missing_uploads = sorted(expected_keys - uploaded_keys)
            if missing_uploads:
                raise ValueError(
                    f"Smoke run did not upload the complete ground-truth dataset ({len(missing_uploads)} missing); "
                    "rerun smoke with --all before evaluating"
                )
        exports = {name: read_csv(exports_path / f"{name}.csv") for name in ("documents", "fields", "line_items", "table_cells")}
        report = evaluate(truth, exports)
        if source_smoke:
            report["source_smoke_run"] = {
                "run_id": source_smoke["run_id"],
                "status": source_smoke["status"],
                "region": source_smoke["environment"].get("region"),
                "stack": source_smoke["environment"].get("stack"),
                "account": source_smoke["environment"].get("account"),
            }
            report["dataset"] = {"synthetic": manifest.get("synthetic"),
                                 "document_count": manifest.get("document_count", len(truth)),
                                 "language": manifest.get("language")}
        output = artifact_run.output("evaluation.json")
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        artifact_run.register("evaluation", "evaluation.json")
        artifact_run.check("evaluation", documents=report["document_count"], meaning="Scoring completed; no accuracy threshold enforced")
    artifact_run.finish()
    return artifact_run, report


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--smoke-run", help="PASS aws_smoke run containing the 30-document dataset and real exports")
    source.add_argument("--truth", help="Ground-truth JSON for a manually collected export set")
    parser.add_argument("--exports", help="Directory containing documents/fields/line_items/table_cells CSVs")
    parser.add_argument("--run-dir", help="New run directory; timestamp ID generated by default")
    args = parser.parse_args()
    if args.smoke_run and args.exports:
        parser.error("--exports is only used with --truth")
    if args.truth and not args.exports:
        parser.error("--truth requires --exports")
    artifact_run, report = evaluation_run(args.truth, args.exports, args.run_dir, args.smoke_run)
    print(json.dumps({"document_count": report["document_count"], "metrics": report["metrics"]}, indent=2))
    print(f"Report saved to {artifact_run.path / 'evaluation.json'}; run sealed")


if __name__ == "__main__":
    main()
