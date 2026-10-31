# WORKLOG DỰ ÁN — TIẾN ĐỘ TUẦN 1–4

> **Dự án:** Số hóa hóa đơn và biểu mẫu với Amazon Textract  
> **Giảng viên hướng dẫn:** TS. Huỳnh Xuân Phụng  
> **Mã học phần:** 261CLCO332779_05  
> **Nhóm sinh viên thực hiện:**  
> - Ninh Nguyễn Minh Tuyên - MSSV: 24110372  
> - Nguyễn Quốc Việt - MSSV: 24110381  

---

## 1. Mục tiêu và Nội dung công việc Tuần 1 phải làm

Trong Tuần 1, nhóm tập trung thực hiện Giai đoạn 1 của đồ án (Thiết kế kiến trúc và dựng nền tảng hệ thống) với các nội dung trọng tâm:
1. **Tìm hiểu dịch vụ AWS:** Nghiên cứu cơ chế hoạt động của Amazon S3, AWS Lambda, Amazon Textract, DynamoDB, SNS và CloudWatch trên môi trường AWS Academy Learner Lab.
2. **Thiết kế kiến trúc hệ thống:** Phác thảo luồng xử lý tài liệu không máy chủ (Serverless), phân định rõ luồng xử lý đồng bộ (Sync cho ảnh) và bất đồng bộ (Async cho PDF nhiều trang), xác định phạm vi kiểm thử Tuần 1.
3. **Khởi tạo tài nguyên nền tảng trên AWS Console:**
   - Dựng VPC (`10.20.0.0/16`), 2 Subnet ở 2 Availability Zone (`us-east-1a`, `us-east-1b`) và Route Table.
   - Tạo S3 bucket (`textract-pipeline-535709085695`), bật mã hóa SSE-S3, tạo hai prefix `input/` và `output/`.
   - Tạo bảng DynamoDB (`textract-pipeline-results`) với khóa `PK`, `SK` kiểu String, chế độ On-demand.
   - Tạo SNS topic (`textract-pipeline-notifications`) và xác nhận Email Subscription.
   - Tạo 2 hàm Lambda skeleton: `textract-pipeline-processor` và `textract-pipeline-exporter` sử dụng execution role `LabRole`.
   - Gắn tag định danh thống nhất: `Project = TextractDocumentDigitization`, `Owner = 24110372-24110381`.
4. **Cấu hình tích hợp và kiểm thử khép kín (Smoke Test):**
   - Thiết lập S3 Event Notification để tự động kích hoạt Lambda Processor khi có file mới tải lên prefix `input/`.
   - Xử lý quyền gọi Lambda (Resource-based policy) từ dịch vụ S3.
   - Tải file kiểm thử `smoke-test.txt` vào `input/`, đối chiếu nhật ký ghi nhận `status: RECEIVED` trên CloudWatch Logs.
   - Tải file CSV giả vào prefix `output/` để xác nhận không phát sinh invocation lặp ngoài ý muốn.

---

## 2. Bảng phân công và khối lượng công việc thực tế (Worklog)

| MSSV | Họ Và Tên | Công việc thực tế trong tuần 1 | Số giờ thực tế |
|:---:|---|---|:---:|
| **24110372** | **Ninh Nguyễn Minh Tuyên** | - Nghiên cứu quy ước đặt tên tài nguyên và thiết lập các thẻ Project, Owner; kiểm tra môi trường AWS Academy Learner Lab, Region us-east-1 và IAM role LabRole.<br>- Khởi tạo các tài nguyên nền tảng trên AWS Console, bao gồm S3 bucket và các prefix input/, output/, DynamoDB table và SNS topic cùng email subscription.<br>- Cấu hình hàm Lambda Processor ở mức khung chức năng; kiểm tra và xử lý sự cố liên quan đến quyền gọi hàm Lambda từ S3.<br>- Thiết lập S3 event notification để kích hoạt Lambda Processor khi có đối tượng mới được tải lên prefix input/.<br>- Thực hiện kiểm thử bằng tệp smoke-test.txt, theo dõi nhật ký trên CloudWatch và đối chiếu invocation sau khi tải tệp vào prefix output/. | **10 giờ** |
| **24110381** | **Nguyễn Quốc Việt** | - Nghiên cứu tài liệu kỹ thuật về cơ chế hoạt động và vai trò của các dịch vụ AWS được sử dụng trong hệ thống, bao gồm S3, Lambda, Textract, DynamoDB, SNS và CloudWatch.<br>- Xây dựng bản phác thảo kiến trúc tổng thể, xác định phạm vi kiểm thử của tuần 1 và phân biệt các chức năng dự kiến triển khai trong các giai đoạn tiếp theo.<br>- Chuẩn bị mã nguồn khung cho hàm Lambda Exporter và các tệp dữ liệu giả phục vụ kiểm thử, bao gồm tệp văn bản và tệp CSV.<br>- Phối hợp kiểm thử luồng sự kiện, thu thập ảnh chụp minh chứng từ AWS Console và CloudWatch.<br>- Tổng hợp kết quả triển khai, ghi nhận các hạng mục đã hoàn thành và báo cáo tuần 1. | **8 giờ** |


## Tuần 2 — Triển khai và kiểm thử trên AWS

Trong tuần 2, nhóm hoàn thiện phần xử lý tài liệu bằng Lambda, đóng gói chương trình rồi triển khai lên AWS Learner Lab. Sau khi stack chạy, nhóm thử với hóa đơn, biểu mẫu và PDF nhiều trang để kiểm tra các bước xử lý và kết quả xuất ra.

### Công việc đã làm

- Đóng gói ba Lambda Processor, Collector và Exporter. Gói `textract-pipeline.zip` có dung lượng 16.661.135 byte; các bước kiểm tra gói và handler đều đạt.
- Triển khai stack `textract-full` trên account `535709085695`, Region `us-east-1`. Stack tạo thành công với trạng thái `CREATE_COMPLETE`.
- Thử `invoice-001.png`, `form-002.png` và `multipage-form.pdf`. Cả ba tài liệu đều xử lý xong với trạng thái `COMPLETED`; PDF hai trang được xử lý qua Collector.
- Gửi lại sự kiện hóa đơn để thử chống trùng. Hệ thống trả `DUPLICATE_OR_IN_PROGRESS`.
- Thử tệp `invalid-smoke.txt`. Hệ thống từ chối tệp với mã `InvalidDocument` và gửi email thông báo SNS.
- Chạy Exporter và tạo năm tệp CSV. Dữ liệu tổng hợp lúc xuất có 6 documents, 46 fields, 4 line_items, 120 table_cells và 42 table_rows.

### Phân công công việc tuần 2

| MSSV | Họ và tên | Công việc thực hiện | Số giờ |
|:---:|---|---|:---:|
| **24110372** | **Ninh Nguyễn Minh Tuyên** | Viết và hoàn thiện phần code Lambda xử lý tài liệu, đóng gói chương trình và triển khai stack bằng AWS CLI. | 12 giờ |
| **24110381** | **Nguyễn Quốc Việt** | Tham gia triển khai và kiểm tra tài nguyên trên AWS; chạy các bài test, kiểm tra email và file CSV; tổng hợp ảnh minh chứng và viết báo cáo tuần 2. | 10 giờ |

**Tài liệu tuần 2:** [README](docs/week2/README.md), [báo cáo](docs/week2/BaoCaoTuan2.docx), [bằng chứng và CSV](docs/week2/evidence/).

### Mục tiêu tuần 3

- Chạy pipeline với bộ ít nhất 30 tài liệu mẫu có dữ liệu chuẩn (ground truth) để đánh giá kết quả trích xuất trên Textract thật.
- Đối chiếu kết quả với ground truth, tổng hợp độ chính xác theo loại tài liệu và nhóm trường, rồi lưu kết quả đánh giá làm minh chứng.
- Phân tích các trường hợp trích xuất sai, hoàn thiện chuẩn hóa dữ liệu nếu cần và bổ sung kiểm thử hồi quy cho các lỗi đã tìm thấy.
- Cập nhật báo cáo kết quả, giới hạn của bộ dữ liệu, độ chính xác và chi phí AWS ghi nhận được.

### Commit liên quan đến công việc tuần 2

- Hoàn thiện mã Lambda, xử lý Textract, xuất CSV và kiểm thử — `9894e142186feae14948effc3670087c8f06e928`: https://github.com/mtuyenn/textract-pipeline/commit/9894e142186feae14948effc3670087c8f06e928
- Bổ sung Worklog và tài liệu triển khai tuần 2 — `d54211aefbc5ca4678b4197d1e60ace764cca5a5`: https://github.com/mtuyenn/textract-pipeline/commit/d54211aefbc5ca4678b4197d1e60ace764cca5a5
- Bổ sung báo cáo và ảnh minh chứng tuần 2 — `bbe3342d6e9421f12fdee9a24f39dccc3845b9bf`: https://github.com/mtuyenn/textract-pipeline/commit/bbe3342d6e9421f12fdee9a24f39dccc3845b9bf

## Tuần 3 — Tích hợp, bảo mật và giám sát

Trong tuần 3, nhóm tiếp tục dùng stack `textract-full` đã triển khai ở tuần 2. Nhóm chạy lại pipeline với bộ tài liệu mẫu, chấm kết quả bằng ground truth, kiểm tra cấu hình S3/Lambda và theo dõi CloudWatch, SNS.

### Công việc đã làm

- Chạy batch baseline gồm 30 ảnh tổng hợp: 15 hóa đơn và 15 biểu mẫu. Cả 30 tài liệu hoàn tất; phát lại sự kiện của một tài liệu đã xử lý trả về `DUPLICATE_OR_IN_PROGRESS`.
- Chạy demo đầu-cuối với 30 ảnh và một PDF hai trang. Cả 31 tài liệu đạt `COMPLETED`; PDF được xử lý bất đồng bộ qua Collector. Hai tệp không hợp lệ được ghi nhận `REJECTED`.
- Chạy evaluator trên 30 ảnh có ground truth. Fields khớp 105/120 (87,50% recall), line item fields 90/90, table cells 180/180 và line item rows 30/30. Nhóm rà soát mismatch `VENDOR_NAME` và cách ghép bảng theo trang/hàng/cột.
- Chạy Exporter, kiểm tra năm CSV `documents.csv`, `fields.csv`, `line_items.csv`, `table_cells.csv`, `table_rows.csv` trong `output/exports/`.
- Kiểm tra S3 Block Public Access, HTTPS-only bucket policy, SSE-S3, versioning, tags và execution role `LabRole` của ba Lambda.
- Theo dõi dashboard, log group, alarm và SNS. Subscription email đã xác nhận; hộp thư nhận thông báo hoàn tất, từ chối và cảnh báo. CloudWatch có datapoint Collector Errors khác 0; nhóm chưa xác định được nguyên nhân gốc.
- Thử tải CSV vào `output/`; trong khoảng thời gian quan sát không thấy Processor bắt đầu xử lý object đó.
- Cost Explorer ngày 25/10 hiển thị khoảng 0,21 USD cho giai đoạn 18–25/10; đây là số liệu tại thời điểm truy vấn và có thể thay đổi khi AWS cập nhật billing.

### Phân công và thời gian ước tính

Thời gian dưới đây là ước tính theo các đầu việc đã thực hiện trong tuần.

| MSSV | Họ và tên | Phần việc | Giờ ước tính |
|:---:|---|---|:---:|
| **24110372** | **Ninh Nguyễn Minh Tuyên** | Chạy batch 30 tài liệu và demo 31 tài liệu trên Learner Lab (3 giờ); kiểm tra trạng thái, chống trùng, tài liệu lỗi và CSV (2 giờ); đối chiếu ground truth, xem mismatch và kết quả evaluator (3 giờ); tổng hợp kết quả demo và viết báo cáo (2 giờ). | **10 giờ** |
| **24110381** | **Nguyễn Quốc Việt** | Rà soát stack, cấu hình bucket và quyền Lambda (2 giờ); kiểm tra dashboard, log group và alarm CloudWatch (2 giờ); xác nhận SNS subscription và email (1,5 giờ); đối chiếu CSV/chi phí và chuẩn bị phần tổng kết, kế hoạch tuần 4 (2,5 giờ). | **8 giờ** |

**Báo cáo tuần 3:** [Báo cáo Word](docs/week3/BaoCaoTuan3.docx) · [Báo cáo Markdown](docs/week3/README.md)

## Tuần 4 — Demo, đo lường và hoàn thiện bàn giao

Trong tuần 4, nhóm quay video demo trên AWS, chạy lượt kiểm thử thống kê gần nhất ngày 29/10, hoàn thiện báo cáo cuối kỳ và dọn dẹp tài nguyên sau khi lưu các dữ liệu cần bàn giao.

### Công việc đã làm

- Quay và rà soát video demo luồng xử lý trên AWS, từ tải tài liệu lên S3 đến trạng thái hoàn tất và các tệp CSV đầu ra.
- Chạy batch 30 ảnh PNG tổng hợp ngày 29/10 trên account `535709085695`, Region `us-east-1`. Cả 30 tài liệu hoàn tất; kiểm tra trạng thái và mã lỗi trong `documents.csv`.
- Tổng hợp kết quả đo: độ trễ mỗi ảnh tính từ `created_at` đến `completed_at` có trung vị 2,42 giây, trung bình 2,60 giây, khoảng 1,74–4,22 giây. Lượt batch kéo dài 44 giây; đây là tốc độ quan sát của một lô nhỏ, không phải kết quả stress test.
- Rà lại lịch sử CloudWatch Collector Errors và cập nhật báo cáo rằng nguyên nhân datapoint khác 0 chưa xác định; lượt chạy 29/10 không có lỗi cấp tài liệu nhưng không thay thế số đo Lambda Errors của Collector.
- Hoàn thiện báo cáo cuối kỳ, bổ sung kết quả hiệu năng, giới hạn kiểm thử, phân tích lỗi, cost evidence và tổng kết đóng góp theo thành viên.
- Ghi nhận Learner Lab hiển thị mức dùng `$4.10/$50`; Cost Explorer/Billing bị chặn quyền với role sinh viên, nên không kết luận số liệu này là breakdown chi phí theo dịch vụ/tag.
- Dọn dẹp tài nguyên AWS sau khi lưu dữ liệu và minh chứng cần bàn giao; rà soát trạng thái tài nguyên sau cleanup.

### Phân công công việc tuần 4

| MSSV | Họ và tên | Công việc thực hiện | Số giờ |
|:---:|---|---|:---:|
| **24110372** | **Ninh Nguyễn Minh Tuyên** | Quay và rà soát video demo; chạy batch 30 tài liệu ngày 29/10; kiểm tra trạng thái, CSV và kết quả evaluator; tổng hợp thống kê độ trễ; rà lịch sử Collector Errors và cập nhật phần kiểm thử trong báo cáo. | **8 giờ** |
| **24110381** | **Nguyễn Quốc Việt** | Viết và hoàn thiện báo cáo cuối kỳ; tổng hợp cost evidence và ghi nhận giới hạn quyền Billing; dọn dẹp tài nguyên AWS sau khi lưu dữ liệu cần bàn giao; kiểm tra trạng thái sau cleanup và rà soát tệp bàn giao. | **8 giờ** |

## Tổng kết công việc trong bốn tuần

| Tuần | Công việc và kết quả chính | Tuyên | Việt |
|:---:|---|:---:|:---:|
| **1** | Thiết kế kiến trúc và dựng nền tảng AWS: VPC, subnet, S3, DynamoDB, SNS, Lambda; cấu hình trigger `input/` và chạy smoke test. | 10 giờ | 8 giờ |
| **2** | Hoàn thiện pipeline, triển khai CloudFormation; tích hợp Textract đồng bộ/bất đồng bộ, Collector, DynamoDB, SNS và Exporter; kiểm tra PDF, chống trùng và năm CSV. | 12 giờ | 10 giờ |
| **3** | Chạy baseline 30 ảnh và demo 31 tài liệu có PDF; đánh giá với ground truth; kiểm tra bảo mật, routing, CloudWatch, alarm, SNS và CSV. | 10 giờ* | 8 giờ* |
| **4** | Quay video demo; chạy batch thống kê 30 ảnh; phân tích hiệu năng và lỗi; hoàn thiện báo cáo, tổng hợp cost evidence và dọn dẹp tài nguyên. | 8 giờ | 8 giờ |
| **Tổng cộng theo số giờ đang ghi** | Bốn tuần triển khai và hoàn thiện đồ án. | **40 giờ** | **34 giờ** |


### Kết quả chung sau bốn tuần

Nhóm đã thiết kế, triển khai và kiểm thử pipeline serverless tiếp nhận hóa đơn, biểu mẫu và PDF nhiều trang trên AWS. Hệ thống kết nối S3, Lambda, Textract, DynamoDB, EventBridge, SNS và CloudWatch; hỗ trợ xử lý đồng bộ/bất đồng bộ, chống xử lý trùng, từ chối đầu vào không hợp lệ và xuất năm CSV. Nhóm đã xử lý bộ baseline 30 ảnh tổng hợp, đánh giá kết quả với ground truth, quay video demo và hoàn thiện báo cáo. Các giới hạn còn lại được ghi rõ, gồm bộ dữ liệu synthetic, chưa kiểm thử tải đồng thời quy mô lớn, nguyên nhân Collector Errors lịch sử chưa xác định, và quyền Billing của Learner Lab không cho xem chi phí chi tiết theo dịch vụ/tag.
