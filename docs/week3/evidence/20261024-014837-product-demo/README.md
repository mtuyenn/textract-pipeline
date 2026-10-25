# Minh chứng demo sản phẩm ngày 24/10/2026

Đây là bản lưu các file có thật từ lượt AWS do sinh viên chạy, không phải một lượt chạy AWS mới.

- Smoke nguồn: `artifacts/runs/20261024-014837-week3-product-demo-3988825a`, PASS, 01:48:38–01:50:51 UTC+07:00, 31/31 COMPLETED.
- Evaluation nguồn: `artifacts/runs/20261024-015102-evaluation-b21f4135`, PASS, 01:51:02–01:51:03 UTC+07:00, chấm 30 ảnh có ground truth; PDF ngoài mẫu số accuracy.
- Account `535709085695`, Region `us-east-1`, stack `textract-full`.

## Nội dung

| File/thư mục | Ý nghĩa |
| --- | --- |
| [smoke.json](smoke.json) | Upload/document ID, trạng thái cuối, duplicate, kết quả export và cấu hình trigger thật |
| [evaluation.json](evaluation.json) | Accuracy, precision và mismatch của 30 ảnh |
| [dataset](dataset) | 30 ảnh tổng hợp, PDF và ground truth được snapshot từ run |
| [exports](exports) | Năm CSV thật dùng để chấm; export có cả revision cũ |
| [demo-terminal.txt](demo-terminal.txt) | Nội dung terminal do sinh viên cung cấp |
| [archive-manifest.json](archive-manifest.json) | Nguồn và SHA-256/size của 42 file khi lưu bản sao |
| `source-*-manifest.json` | Manifest gốc, tham chiếu cấu trúc thư mục run gốc |

Manifest gốc được giữ nguyên. Thư mục này không được đổi nhãn thành một run `aws_smoke` hay `evaluation`; các gói ZIP Lambda vẫn nằm trong run gốc. Đã đối chiếu byte của các file sao chép và kiểm tra hash/size trong hai run gốc trước khi lưu.

## Chấm lại offline

Chạy từ root dự án, sau khi đã cài dependencies như hướng dẫn dự án:

```powershell
.venv/Scripts/python.exe tools/evaluate.py --truth docs/week3/evidence/20261024-014837-product-demo/dataset/ground_truth.json --exports docs/week3/evidence/20261024-014837-product-demo/exports
```

Lệnh tạo evaluation run mới và không gọi AWS. Chấm từ CSV nhập qua `--truth/--exports` không tự chứng minh nguồn AWS; nguồn được đối chiếu với smoke/manifest/terminal lưu kèm trong bộ này.

Kết quả đã lưu: fields 105/120 (87,5%, precision 68,18%); line item fields 90/90 (100%, precision 60%); table cells 180/180 (100%, precision 60%). Các lượt `SUBMITTED` trong terminal là lúc PDF còn xử lý; trạng thái cuối của PDF là COMPLETED, pages=2 trong documents.csv.
