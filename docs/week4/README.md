# Tuần 4 — Demo và hoàn thiện đồ án

Trong tuần cuối, nhóm chạy lại bộ mẫu 30 tài liệu, tổng hợp kết quả, quay video demo và hoàn thiện báo cáo. Sau khi lưu dữ liệu cần dùng, nhóm dọn dẹp các tài nguyên AWS đã tạo và kiểm tra lại trạng thái.

## Công việc đã làm

- Chạy 30 ảnh PNG gồm hóa đơn và biểu mẫu trên AWS Learner Lab, account `535709085695`, Region `us-east-1`. Cả 30 tài liệu đều có trạng thái `COMPLETED`.
- So sánh kết quả trích xuất với ground truth. Fields khớp 105/120 giá trị; line-item rows khớp 30/30; line-item fields khớp 90/90 và table cells khớp 180/180. Textract trả thêm một số dự đoán ở fields, line-item fields và table cells nên Precision của các nhóm này thấp hơn Recall.
- Tính thời gian xử lý dựa trên `created_at` và `completed_at` trong dữ liệu xuất. Thời gian trung bình là 2,60 giây, trung vị 2,42 giây, thấp nhất 1,74 giây và cao nhất 4,22 giây. Lượt xử lý 30 tài liệu kéo dài khoảng 44 giây; nhóm chưa chạy stress test.
- Rà lại CloudWatch. Nhóm vẫn chưa xác định được nguyên nhân datapoint lỗi Collector xuất hiện ở lượt kiểm tra trước. Batch ngày 29/10 hoàn tất 30 tài liệu, nhưng không đủ để kết luận nguyên nhân lỗi Collector.
- Quay video demo luồng tải tài liệu lên S3, xử lý và xuất CSV. Video dài 8 phút 38 giây.
- Hoàn thiện báo cáo cuối kỳ, tổng hợp phần việc và giờ làm của hai thành viên. Tuần này mỗi người ghi nhận 8 giờ trong [worklog](../../WORKLOG.md).
- Lưu lại dữ liệu và minh chứng cần bàn giao, sau đó dọn dẹp tài nguyên AWS đã dùng và kiểm tra trạng thái tài nguyên.

## Phân công tuần 4

| Thành viên | Công việc | Thời gian |
| --- | --- | ---: |
| Ninh Nguyễn Minh Tuyên (24110372) | Chạy batch 30 tài liệu, kiểm tra CSV và kết quả evaluator, tổng hợp thời gian xử lý, rà lại lỗi Collector và quay video demo. | 8 giờ |
| Nguyễn Quốc Việt (24110381) | Hoàn thiện báo cáo, tổng hợp thông tin chi phí, dọn dẹp tài nguyên AWS và kiểm tra các tệp bàn giao. | 8 giờ |

## Mã nguồn và minh chứng trên GitHub

- **Commit tuần 4:** [Bổ sung báo cáo và minh chứng tuần 4](https://github.com/mtuyenn/textract-pipeline/commit/1e75abfdc0e77d4f95104666271b8584affee912).
- **Mã nguồn:** [Repository textract-pipeline](https://github.com/mtuyenn/textract-pipeline), [CloudFormation template](../../infra/template.yaml), [script chạy thử AWS](../../tools/smoke_aws.py) và [script đánh giá ground truth](../../tools/evaluate.py).
- **Báo cáo và quá trình làm:** [Báo cáo cuối kỳ DOCX](../BaoCaoCuoiKy.docx), [bản PDF](../BaoCaoCuoiKy.pdf) và [worklog tuần 1–4](../../WORKLOG.md).
- **Video demo:** [video_demo.mp4 — 8 phút 38 giây](../video_demo.mp4). File video được cấu hình Git LFS vì dung lượng vượt giới hạn file thông thường của GitHub.
- **Lượt chạy demo AWS ngày 29/10:** [Tóm tắt kết quả](evidence/20261029-172921-30-document-demo/demo-summary.json), [manifest của lượt chạy](evidence/20261029-172921-30-document-demo/manifest.json), [documents.csv](evidence/20261029-172921-30-document-demo/documents.csv), [fields.csv](evidence/20261029-172921-30-document-demo/fields.csv), [line_items.csv](evidence/20261029-172921-30-document-demo/line_items.csv), [table_cells.csv](evidence/20261029-172921-30-document-demo/table_cells.csv) và [table_rows.csv](evidence/20261029-172921-30-document-demo/table_rows.csv).
- **Lượt đánh giá ground truth ngày 29/10:** [Kết quả evaluator](evidence/20261029-175734-evaluation/evaluation.json), [manifest](evidence/20261029-175734-evaluation/manifest.json) và [ground_truth.json](../../data/samples/baseline-v1/ground_truth.json).

CSV là bản xuất dữ liệu đang có trong DynamoDB tại thời điểm chạy; số dòng trong CSV không phải số tài liệu dùng để tính độ chính xác. Evaluator tính trên 30 ảnh có ground truth. Manifest cũng ghi rõ các bước cần kiểm tra thủ công chưa được xác nhận trong lượt smoke này.

Ảnh Cost Explorer nằm trong Phụ lục C của [báo cáo PDF](../BaoCaoCuoiKy.pdf); phần dọn dẹp tài nguyên được ghi trong [worklog tuần 4](../../WORKLOG.md).
