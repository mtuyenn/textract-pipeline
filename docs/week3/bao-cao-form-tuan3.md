# Báo cáo tuần 3 — Tích hợp, bảo mật và giám sát pipeline Textract

## Nội dung báo cáo

### 1. Mục tiêu

Tuần 3, nhóm tiếp tục hoàn thiện và kiểm tra sản phẩm số hóa hóa đơn, biểu mẫu trên AWS. Mục tiêu là xác nhận luồng S3 → Lambda → Textract → DynamoDB, xuất dữ liệu CSV, đánh giá ít nhất 30 tài liệu mẫu, kiểm tra cấu hình bảo mật, theo dõi hoạt động bằng CloudWatch và kiểm tra thông báo SNS. Nhóm sử dụng stack `textract-full` đã triển khai bằng CloudFormation từ tuần trước, không dựng một pipeline khác.

Môi trường demo chính: AWS Academy Learner Lab, account `535709085695`, Region `us-east-1`.

### 2. Tích hợp và chạy demo

- Lambda Processor nhận tài liệu từ prefix `input/`, phân loại loại tài liệu và gọi Textract: hóa đơn dùng `AnalyzeExpense`; biểu mẫu dùng `AnalyzeDocument` với `FORMS` và `TABLES`. Tác vụ PDF được xử lý bất đồng bộ; Lambda Collector lấy kết quả và cập nhật DynamoDB.
- Chạy batch baseline gồm **30 ảnh PNG** (15 hóa đơn, 15 biểu mẫu). Cả 30 tài liệu hoàn tất. Nhóm kiểm tra trạng thái và dữ liệu trong DynamoDB, đồng thời phát lại sự kiện của tài liệu đã xử lý để kiểm tra chống trùng; kết quả là `DUPLICATE_OR_IN_PROGRESS`.
- Chạy demo đầu-cuối ngày **24/10/2026** với 30 ảnh và **01 PDF hai trang**. Smoke run `20261024-014837-week3-product-demo-3988825a` ghi nhận **31/31 tài liệu `COMPLETED`**. PDF được Textract xử lý bất đồng bộ; trạng thái `SUBMITTED` trong lúc chờ là trạng thái trung gian, kết quả cuối là `COMPLETED`.

### 3. Đánh giá độ chính xác

Evaluator chấm 30 ảnh có ground truth; PDF được kiểm tra luồng xử lý nhưng không nằm trong mẫu số đánh giá. Kết quả của run `20261024-015102-evaluation-b21f4135`:

| Nhóm chỉ tiêu | Khớp / kỳ vọng | Dự đoán | Accuracy (recall) | Precision |
|---|---:|---:|---:|---:|
| Fields | 105 / 120 | 154 | 87,50% | 68,18% |
| Line item fields | 90 / 90 | 150 | 100% | 60% |
| Table cells | 180 / 180 | 300 | 100% | 60% |
| Line item rows | 30 / 30 | 30 | 100% | 100% |

Accuracy/recall là tỷ lệ giá trị ground truth được khớp; precision là tỷ lệ dự đoán khớp. Các giá trị precision thấp hơn cho thấy hệ thống còn trả thêm trường ngoài ground truth. 15 mismatch ở nhóm fields thuộc `VENDOR_NAME`; một số giá trị được đọc ra nhưng Textract gán nhãn `OTHER`. Lần chấm table cells ban đầu bị 0% do ghép bảng theo số thứ tự khác nhau; evaluator được chỉnh để ghép bảng theo tài liệu/trang và vị trí hàng/cột rồi chấm lại. Kết quả 100% table cells cần được hiểu trong giới hạn cách ghép có tham chiếu ground truth, không phải phép đo độc lập về phát hiện bảng.

### 4. CSV và lưu trữ

Lambda Exporter tạo năm tệp tổng hợp trong `output/exports/` trên S3: `documents.csv`, `fields.csv`, `line_items.csv`, `table_cells.csv` và `table_rows.csv`. Smoke run cũng tải các CSV về thư mục `exports/` cục bộ của lượt chạy. CSV tổng hợp có dữ liệu các lần chạy/revision trước đó; evaluator chỉ chấm 30 source key có ground truth. Việc upload lên S3 không tự tải file về máy tính.

### 5. Bảo mật, giám sát và chi phí

- Kiểm tra bucket dữ liệu: bật đủ bốn tùy chọn Block Public Access, versioning, mã hóa mặc định SSE-S3 và bucket policy từ chối `s3:*` khi `aws:SecureTransport=false` (yêu cầu HTTPS). Các Lambda Processor, Collector và Exporter sử dụng `LabRole` có sẵn của Learner Lab; quyền gọi Processor từ S3 được giới hạn theo account và bucket nguồn.
- Theo dõi dashboard `textract-full-pipeline`, log group Lambda (retention 14 ngày), hai alarm Lambda/document errors và SNS email. CloudWatch ghi nhận datapoint lỗi: alarm Lambda từng về `OK` ngày 24/10 sau datapoint bằng 0; ảnh ngày 25/10 cho thấy alarm document errors chuyển sang `ALARM` sau datapoint bằng 1. Dashboard cũng có Collector Errors khác 0. Nhóm chưa xác định nguyên nhân gốc, nên không kết luận pipeline không có lỗi chỉ dựa vào trạng thái `OK` ở một thời điểm.
- SNS đã gửi email `COMPLETED`, `REJECTED` và email cảnh báo alarm tới hộp thư subscription đã xác nhận.
- Cost Explorer tại thời điểm kiểm tra ngày 25/10 hiển thị tổng khoảng **0,21 USD** trong giai đoạn 18–25/10; khoản Textract được ghi nhận vào ngày 18/10. Đây là số liệu tại thời điểm truy vấn và có thể thay đổi khi AWS cập nhật billing.

### 6. Kết luận

Các yêu cầu chức năng chính đã được demo: xử lý hóa đơn, biểu mẫu và PDF; lưu kết quả DynamoDB; xuất năm CSV; chống xử lý trùng; đánh giá 30 tài liệu có ground truth; kiểm tra bảo mật S3 và giám sát CloudWatch/SNS. Kết quả fields đạt 87,50% accuracy/recall, chưa đạt 100%; bộ mẫu là tài liệu tổng hợp tiếng Anh theo template nên chưa đại diện cho ảnh chụp thực tế hoặc tài liệu tiếng Việt. Nhóm sẽ tiếp tục phân tích Collector/document errors, rà soát chất lượng trích xuất, chi phí và chuẩn bị demo/nghiệm thu tuần 4.

### 7. Mã nguồn và minh chứng trên GitHub

- [Báo cáo tuần 3 chi tiết](https://github.com/mtuyenn/textract-pipeline/blob/main/docs/week3/README.md)
- [Kết quả smoke test AWS](https://github.com/mtuyenn/textract-pipeline/blob/main/docs/week3/evidence/20261024-014837-product-demo/smoke.json)
- [Kết quả đánh giá 30 tài liệu](https://github.com/mtuyenn/textract-pipeline/blob/main/docs/week3/evidence/20261024-014837-product-demo/evaluation.json)
- [Ground truth của bộ 30 tài liệu](https://github.com/mtuyenn/textract-pipeline/blob/main/docs/week3/evidence/20261024-014837-product-demo/dataset/ground_truth.json)
- [CSV kết quả xuất](https://github.com/mtuyenn/textract-pipeline/blob/main/docs/week3/evidence/20261024-014837-product-demo/exports/documents.csv)
- [CloudFormation template](https://github.com/mtuyenn/textract-pipeline/blob/main/infra/template.yaml)

## Khai báo sử dụng AI trong form

**Có sử dụng LLM/AI code/AI agent:** Có.

**Công cụ AI:** ChatGPT/Codex.

**Phiên bản/model:** GPT-6 (phiên Codex hỗ trợ trong workspace).

**Prompt đã dùng (tóm tắt):** “Rà soát dự án Textract và kết quả smoke/evaluation tuần 3; giải thích các số liệu; đối chiếu cấu hình AWS và ảnh minh chứng; giúp tổng hợp báo cáo tuần 3 trung thực, nêu rõ giới hạn.” Đây là mô tả tóm tắt, không phải trích nguyên văn toàn bộ prompt trong các phiên.

**Nội dung AI tạo ra:** Hỗ trợ đọc và đối chiếu mã nguồn, run artifacts và ảnh AWS; cập nhật/hỗ trợ evaluator và smoke tooling; tính/diễn giải accuracy, precision; soạn nháp nội dung và cấu trúc báo cáo.

**Phần sinh viên đã thực hiện, kiểm tra hoặc hoàn thiện:** Kích hoạt Learner Lab và chạy các lệnh AWS/demo trong phiên có credentials; thao tác và kiểm tra S3, Lambda, CloudWatch, SNS; cung cấp ảnh và kết quả thực tế; rà lại kết quả với dữ liệu chạy; xác nhận account sở hữu demo/CSV/alarm/chi phí và chỉnh báo cáo theo minh chứng. Không đưa credentials AWS vào báo cáo.
