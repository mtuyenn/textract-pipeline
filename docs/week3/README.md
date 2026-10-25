# Báo cáo tuần 3 — Tích hợp, bảo mật và giám sát pipeline Textract

**Môn học:** Điện toán đám mây
**Giảng viên hướng dẫn:** TS. Huỳnh Xuân Phụng
**Nhóm sinh viên:** Ninh Nguyễn Minh Tuyên (24110372), Nguyễn Quốc Việt (24110381)
**Học kỳ:** 1, năm học 2026–2027

## Tóm tắt kết quả

Trong tuần 3, nhóm hoàn thiện và vận hành pipeline số hóa tài liệu trên AWS. Lượt demo đầu-cuối xử lý thành công 31 tài liệu, gồm 15 hóa đơn, 15 biểu mẫu và một PDF hai trang. Nhóm đánh giá bộ baseline 30 ảnh bằng ground truth, kiểm tra xử lý trùng và routing, xuất CSV, theo dõi dashboard CloudWatch và kiểm tra email SNS. Fields đạt 87,50% recall theo evaluator; line item rows và table cells đạt 100% recall trên bộ mẫu.

Nhóm sử dụng AWS Academy Learner Lab và stack `textract-full` đã triển khai bằng CloudFormation ở tuần 2. Các kết quả `COMPLETED` cho biết xử lý đã kết thúc; độ chính xác được đánh giá riêng bằng ground truth.

## 1. Mục tiêu và phạm vi

Trong tuần 3, nhóm tập trung kiểm tra luồng S3 → Lambda → Textract → DynamoDB, xuất dữ liệu CSV, đánh giá tối thiểu 30 tài liệu, rà soát bảo mật, giám sát bằng CloudWatch và xác nhận thông báo SNS. Nhóm tiếp tục sử dụng hạ tầng hiện có, không tạo một pipeline riêng.

**Môi trường:** AWS Academy Learner Lab, account `535709085695`, Region `us-east-1`.

## 2. Kiến trúc và tài nguyên AWS

Khi tài liệu được tải lên prefix `input/` của S3, sự kiện tạo object kích hoạt Lambda Processor. Processor nhận diện loại tài liệu và gọi `AnalyzeExpense` cho hóa đơn hoặc `AnalyzeDocument` với `FORMS` và `TABLES` cho biểu mẫu. Kết quả và trạng thái được lưu vào DynamoDB. Với tác vụ bất đồng bộ, Lambda Collector lấy kết quả Textract và cập nhật dữ liệu. SNS gửi thông báo trạng thái; Lambda Exporter tổng hợp dữ liệu thành CSV trong `output/exports/`.

| Tài nguyên | Giá trị |
| --- | --- |
| CloudFormation stack | `textract-full` |
| S3 bucket dữ liệu | `textract-full-535709085695-us-east-1` |
| DynamoDB table | `textract-full-results` |
| Lambda | `textract-full-processor`, `textract-full-collector`, `textract-full-exporter` |
| SNS topic | `textract-full-notifications` |
| Execution role | `LabRole` có sẵn trong Learner Lab |

Stack được triển khai thành công ở tuần 2. Trong tuần 3, nhóm kiểm tra template và cập nhật stack; lần cập nhật hoàn tất với trạng thái `UPDATE_COMPLETE`. Một số tài nguyên dữ liệu có chính sách `Retain`, vì vậy cần kiểm tra riêng trước khi dọn môi trường AWS.

## 3. Triển khai và chạy thử

Trước khi thao tác, nhóm khởi động Learner Lab, dùng temporary credentials của phiên hiện tại và xác nhận danh tính bằng AWS STS. Credentials không được ghi vào báo cáo.

Bộ baseline gồm 30 ảnh PNG tổng hợp, gồm 15 hóa đơn và 15 biểu mẫu. Nhóm tải ảnh lên `input/`, theo dõi trạng thái trong DynamoDB, phát lại một sự kiện cùng `VersionId` để kiểm tra chống trùng, rồi chạy Exporter. Lượt smoke `20261024-002810-aws-smoke-accuracy-fc93f0c6` hoàn tất 30/30 ảnh. Khi phát lại sự kiện, Processor trả `DUPLICATE_OR_IN_PROGRESS`.

Ngày 24/10/2026, nhóm chạy demo đầu-cuối gồm 30 ảnh và một PDF hai trang. Run `20261024-014837-week3-product-demo-3988825a` hoàn tất 31/31 tài liệu. PDF có trạng thái `SUBMITTED` trong lúc Textract xử lý bất đồng bộ, sau đó chuyển thành `COMPLETED`. Hai tài liệu đầu vào không hợp lệ được pipeline ghi nhận `REJECTED`.

Nhóm cũng kiểm tra routing bằng cách đưa một CSV vào `output/`. Trong khoảng thời gian theo dõi, không thấy Processor bắt đầu xử lý object này; kết quả phù hợp với cấu hình chỉ kích hoạt xử lý từ prefix `input/`.

## 4. Đánh giá độ chính xác

Evaluator sử dụng 30 ảnh có ground truth. PDF hai trang được dùng để kiểm tra xử lý bất đồng bộ, không tính vào mẫu số đánh giá. Kết quả của run `20261024-015102-evaluation-b21f4135`:

| Nhóm chỉ tiêu | Khớp / kỳ vọng | Dự đoán | Recall | Precision |
| --- | ---: | ---: | ---: | ---: |
| Fields | 105 / 120 | 154 | 87,50% | 68,18% |
| Line item fields | 90 / 90 | 150 | 100,00% | 60,00% |
| Table cells | 180 / 180 | 300 | 100,00% | 60,00% |
| Line item rows | 30 / 30 | 30 | 100,00% | 100,00% |

Recall là tỷ lệ giá trị ground truth được khớp; precision là tỷ lệ dự đoán khớp. Precision thấp hơn cho thấy Textract còn trả thêm trường ngoài ground truth. Trong nhóm fields có 15 giá trị chưa khớp, đều thuộc `VENDOR_NAME`; một số trường hợp Textract đọc được nội dung nhưng gán nhãn `OTHER`.

Lần chấm table cells đầu tiên không tìm được ô khớp do số thứ tự bảng giữa ground truth và Textract khác nhau. Nhóm điều chỉnh cách ghép bảng theo tài liệu, trang, hàng và cột rồi chấm lại. Kết quả 180/180 cần được hiểu trong giới hạn cách ghép có tham chiếu ground truth; đây không phải phép đo độc lập về khả năng phát hiện bảng.

Bộ mẫu là tài liệu tổng hợp bằng tiếng Anh theo template cố định, chưa đại diện cho ảnh chụp thực tế, tài liệu tiếng Việt, ảnh mờ hoặc bố cục khác.

## 5. Bảo mật

Nhóm kiểm tra bucket dữ liệu chính trên AWS Console:

- Bật đủ bốn tùy chọn S3 Block Public Access.
- Bật versioning và mã hóa mặc định SSE-S3.
- Bucket policy từ chối `s3:*` khi `aws:SecureTransport=false`, yêu cầu kết nối HTTPS.
- Ba Lambda chính sử dụng `LabRole` do Learner Lab cấp.
- Quyền gọi Processor từ S3 giới hạn theo account nguồn và ARN bucket.

Khi kiểm tra IAM policy trên Console, phiên `voclabs` gặp explicit deny với quyền `iam:GetPolicy`. Đây là giới hạn đọc policy của Learner Lab; nhóm kiểm tra riêng hoạt động của pipeline và không suy rộng thành lỗi của các API xử lý tài liệu.

## 6. Giám sát, cảnh báo và SNS

Nhóm theo dõi dashboard `textract-full-pipeline`, log group Lambda với retention 14 ngày và hai alarm `textract-full-lambda-errors`, `textract-full-document-errors`. CloudWatch ghi nhận Collector Errors khác 0 trong khoảng thời gian hiển thị. Nhóm chưa xác định được nguyên nhân gốc của các datapoint lỗi.

History của alarm Lambda ghi nhận datapoint bằng 1 lúc 19:20 ngày 17/10/2026; alarm chuyển về `OK` lúc 00:18 ngày 24/10 sau datapoint bằng 0 lúc 00:13. Các mốc này xác nhận thay đổi trạng thái, nhưng chưa giải thích nguyên nhân hoặc diễn biến liên tục ở giữa. Tìm `ERROR` trong log Processor/Collector và `document_error` trong Collector không trả về sự kiện khớp trong phạm vi đã kiểm tra; điều đó không phủ nhận metric lỗi lịch sử.

SNS topic `textract-full-notifications` có email subscription ở trạng thái `Confirmed`. Hộp thư nhận được email `COMPLETED`, `REJECTED` và cảnh báo CloudWatch. Cost Explorer ngày 25/10 hiển thị tổng khoảng **0,21 USD** trong giai đoạn 18–25/10; chi phí Textract được ghi nhận ngày 18/10. Đây là số liệu tại thời điểm truy vấn và có thể thay đổi khi AWS cập nhật billing.

## 7. CSV và lưu trữ

Lambda Exporter tạo năm CSV trong `output/exports/`: `documents.csv`, `fields.csv`, `line_items.csv`, `table_cells.csv` và `table_rows.csv`. Smoke script tải bản sao về thư mục kết quả của lượt chạy trên máy tính. Upload tài liệu lên S3 không tự tải CSV về máy.

CSV tổng hợp có thể chứa dữ liệu từ các lượt xử lý trước. Evaluator chỉ dùng 30 source key có ground truth để tính điểm; số dòng của CSV tổng hợp không phải số tài liệu được đánh giá.

## 8. Kết luận và kế hoạch tuần 4

Trong tuần 3, nhóm đã demo luồng xử lý 31 tài liệu, đánh giá 30 ảnh, kiểm tra chống xử lý trùng, routing, xuất CSV, cấu hình bảo mật S3, CloudWatch và SNS. Kết quả fields đạt 87,50% recall; line item rows và table cells đạt 100% recall trên bộ mẫu hiện tại. Các kết quả này có giới hạn do bộ mẫu tổng hợp và chưa đại diện cho tài liệu thực tế đa dạng.

Sang tuần 4, nhóm tiếp tục phân tích Collector Errors và mismatch `VENDOR_NAME`, chạy kiểm thử hồi quy, theo dõi chi phí, chuẩn bị demo nghiệm thu và rà soát tài nguyên AWS có chính sách `Retain` trước khi dọn môi trường.