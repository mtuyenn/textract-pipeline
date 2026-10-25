"""Deterministic synthetic English documents, never real personal data."""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import run_artifacts as runs


def generate(output, count=30):
    from PIL import Image, ImageDraw, ImageFont
    if count < 30:
        raise ValueError("Generate at least 30 documents for the project")
    output = runs.workspace_output(output)
    font_path = next((path for path in [Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")] if path.exists()), None)
    def font(size):
        return ImageFont.truetype(str(font_path), size) if font_path else ImageFont.load_default(size=size)
    regular, small, title = font(30), font(25), font(54)
    truth = []
    preview_pages = []
    for index in range(1, count + 1):
        invoice = index % 2 == 1
        name = f"{'invoice' if invoice else 'form'}-{index:03d}"
        key = f"input/{'invoices' if invoice else 'forms'}/{name}.png"
        image = Image.new("RGB", (1275, 1650), "white")
        draw = ImageDraw.Draw(image)
        draw.text((90, 80), "INVOICE" if invoice else "SUPPLY REQUEST FORM", fill="black", font=title)
        draw.text((90, 170), "SYNTHETIC DATA - NOT A REAL TRANSACTION", fill="black", font=small)
        draw.line((90, 220, 1185, 220), fill="black", width=3)
        dt = (date(2026, 1, 1) + timedelta(days=index)).isoformat()
        row_specs = [("A4 PAPER BOX", 1 + index % 3, 12.50), ("DESK NOTEBOOK", 2, 7.25)]
        total = sum(quantity * price for _, quantity, price in row_specs)
        fields, lines, cells = [], [], []
        if invoice:
            field_specs = [("VENDOR_NAME", "VENDOR NAME", f"SAMPLE OFFICE SUPPLY {index % 3 + 1}"),
                ("INVOICE_RECEIPT_ID", "INVOICE NUMBER", f"INV-{index:04d}"),
                ("INVOICE_RECEIPT_DATE", "INVOICE DATE", dt), ("TOTAL", "TOTAL", f"${total:.2f}")]
        else:
            field_specs = [("FORM ID", "FORM ID", f"FORM-{index:04d}"),
                ("FULL NAME", "FULL NAME", f"SYNTHETIC USER {index:03d}"),
                ("DEPARTMENT", "DEPARTMENT", ["FINANCE", "OPERATIONS", "SALES"][index % 3]),
                ("REQUEST DATE", "REQUEST DATE", dt)]
        for position, (canonical, label, value) in enumerate(field_specs):
            draw.text((100, 290 + position * 85), label + ":", font=regular, fill="black")
            draw.text((540, 290 + position * 85), value, font=regular, fill="black")
            fields.append({"field_name": canonical, "value": value, "page": 1})
        columns = [100, 670, 800, 990, 1185]
        header = ["ITEM DESCRIPTION", "QTY", "UNIT PRICE", "AMOUNT"]
        rows = [header] + [[item, str(quantity), f"${price:.2f}", f"${quantity * price:.2f}"] for item, quantity, price in row_specs]
        for row, values in enumerate(rows, 1):
            top = 720 + (row - 1) * 75
            for col, value in enumerate(values, 1):
                draw.rectangle((columns[col - 1], top, columns[col], top + 75), outline="black", width=2)
                draw.text((columns[col - 1] + 10, top + 20), value, font=small, fill="black")
                if not invoice:
                    cells.append({"table_number": 1, "page": 1, "row": row, "column": col, "value": value})
        if invoice:
            for row, (item, quantity, price) in enumerate(row_specs, 1):
                lines.append({"expense_index": 1, "group_index": 1, "line_number": row,
                              "fields": {"ITEM": item, "QUANTITY": str(quantity), "PRICE": f"${quantity * price:.2f}"}})
        draw.text((100, 1180), "Generated for Textract evaluation; all values are fabricated.", font=small, fill="black")
        destination = output / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, dpi=(150, 150))
        truth.append({"s3_key": key, "document_type": "invoice" if invoice else "form", "fields": fields,
                      "line_items": lines, "table_cells": cells})
        if not invoice and len(preview_pages) < 2:
            preview_pages.append(image)
    # Separate demo asset; the >=30-document evaluation set remains explicit.
    pdf = output / "async-demo" / "multipage-form.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    preview_pages[0].save(pdf, "PDF", save_all=True, append_images=preview_pages[1:], resolution=150)
    manifest = {"synthetic": True, "document_count": count, "language": "English", "documents": truth,
                "async_demo": {"local_path": "async-demo/multipage-form.pdf", "s3_key": "input/forms/multipage-form.pdf"}}
    (output / "ground_truth.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(Path(__file__).resolve().parents[1] / "artifacts/datasets/baseline-v1"))
    parser.add_argument("--count", type=int, default=30)
    args = parser.parse_args()
    manifest = generate(args.output, args.count)
    print(f"Created {manifest['document_count']} synthetic PNGs + multipage PDF + ground_truth.json in {args.output}")


if __name__ == "__main__":
    main()
