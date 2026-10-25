# WORKLOG DỰ ÁN — TIẾN ĐỘ TUẦN 1, TUẦN 2 VÀ TUẦN 3

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

### Kế hoạch tuần 3

- Chạy pipeline với bộ ít nhất 30 tài liệu mẫu có dữ liệu chuẩn (ground truth) để đánh giá kết quả trích xuất trên Textract thật.
- Đối chiếu kết quả với ground truth, tổng hợp độ chính xác theo loại tài liệu và nhóm trường, rồi lưu kết quả đánh giá làm minh chứng.
- Phân tích các trường hợp trích xuất sai, hoàn thiện chuẩn hóa dữ liệu nếu cần và bổ sung kiểm thử hồi quy cho các lỗi đã tìm thấy.
- Cập nhật báo cáo kết quả, giới hạn của bộ dữ liệu, độ chính xác và chi phí AWS ghi nhận được.

### Commit liên quan đến công việc tuần 2

- Hoàn thiện mã Lambda, xử lý Textract, xuất CSV và kiểm thử — `9894e142186feae14948effc3670087c8f06e928`: https://github.com/mtuyenn/textract-pipeline/commit/9894e142186feae14948effc3670087c8f06e928
- Bổ sung Worklog và tài liệu triển khai tuần 2 — `d54211aefbc5ca4678b4197d1e60ace764cca5a5`: https://github.com/mtuyenn/textract-pipeline/commit/d54211aefbc5ca4678b4197d1e60ace764cca5a5
- Bổ sung báo cáo và ảnh minh chứng tuần 2 — `bbe3342d6e9421f12fdee9a24f39dccc3845b9bf`: https://github.com/mtuyenn/textract-pipeline/commit/bbe3342d6e9421f12fdee9a24f39dccc3845b9bf

## Tuần 3 — Tích hợp, bảo mật, giám sát và đánh giá trên AWS

### Công việc có bằng chứng thực hiện

| Hạng mục | Công việc và kết quả đã ghi nhận | Bằng chứng |
| --- | --- | --- |
| Công cụ đánh giá và quản lý run | Cập nhật smoke để xác nhận phiên Learner Lab, account và dữ liệu synthetic; evaluator nhận run thật, lưu snapshot/provenance, đối chiếu bảng theo vị trí hàng/cột cùng trang | `tools/smoke_aws.py`, `tools/evaluate.py`, manifest các run |
| Batch 30 tài liệu | Ngày 24/10 lúc 00:28, chạy 15 hóa đơn và 15 biểu mẫu qua stack `textract-full`; cả 30 COMPLETED, xuất năm CSV | `20261024-002810-aws-smoke-accuracy-fc93f0c6` |
| Phân tích độ chính xác | Fields 105/120 (87,5%); line item fields 90/90; table cells sau sửa cách ghép bảng 180/180. Giữ precision và 15 mismatch VENDOR_NAME; không tuyên bố toàn hệ thống chính xác 100% | `20261024-003342-evaluation-table-remap-a35eb328` và các evaluation tiếp theo |
| Bảo mật | Đối chiếu Console: S3 chặn public, HTTPS-only policy, SSE-S3, Versioning Enabled, tags Project/Owner; ba Lambda chính dùng LabRole. Ghi nhận giới hạn `iam:GetPolicy` của lab | Ảnh Console do nhóm cung cấp trong buổi làm việc; phần bảo mật trong báo cáo tuần 3 |
| CloudWatch và SNS | Xem dashboard/log groups, retention, hai alarms và lịch sử thay đổi trạng thái; xác nhận subscription của topic chính và email COMPLETED đã nhận | Ảnh CloudWatch/Gmail/SNS trong `docs/week3/assets` và ảnh bổ sung trong cuộc trao đổi |
| IaC và quản lý tài nguyên | Tiếp tục dùng CloudFormation stack tuần 2; phân biệt bộ `textract-full-*` với bộ tuần 1, xác định bucket cũ vẫn chứa ZIP triển khai; chưa thực hiện cleanup | Deployment manifest và báo cáo tuần 2/3 |
| Demo sản phẩm trên AWS | Ngày 24/10 từ 01:48:38 đến 01:50:51, chạy 30 ảnh + PDF hai trang: 31/31 COMPLETED, duplicate được chặn, xuất/tải CSV. Evaluation lúc 01:51:02–01:51:03 chấm 30 ảnh và tái lập kết quả trước đó | `20261024-014837-week3-product-demo-3988825a`, `20261024-015102-evaluation-b21f4135` |
| Tổng hợp hồ sơ | Viết báo cáo tuần 3, liên kết run/ảnh, cập nhật tiến độ vốn còn ghi NOT_RUN từ 11/10; kiểm tra hash/size các run được đối chiếu | `docs/week3/README.md`, `docs/plan.md`, các manifest |

### Phân công và số giờ

Hai thành viên của nhóm là Ninh Nguyễn Minh Tuyên (24110372) và Nguyễn Quốc Việt (24110381). Bằng chứng hiện có xác nhận các kết quả chung ở bảng trên; không đủ để xác định chính xác phần việc và số giờ thực tế của từng người. Phiên CLI trong minh chứng sử dụng tài khoản Learner Lab có MSSV 24110372, nhưng thời gian bắt đầu/kết thúc run là thời gian thực thi chương trình, không phải tổng giờ làm việc của cá nhân.

| MSSV | Họ và tên | Phân bổ công việc thực tế theo cá nhân | Số giờ thực tế tuần 3 |
| --- | --- | --- | --- |
| 24110372 | Ninh Nguyễn Minh Tuyên | Chưa có nguồn xác nhận đầy đủ; tham chiếu các kết quả chung đã ghi nhận ở trên | Chưa xác nhận |
| 24110381 | Nguyễn Quốc Việt | Chưa có nguồn xác nhận đầy đủ; tham chiếu các kết quả chung đã ghi nhận ở trên | Chưa xác nhận |

Yêu cầu tối thiểu của môn học là 8 giờ/SV/tuần. Không dùng số giờ tối thiểu làm số giờ thực tế nếu chưa có nhật ký xác nhận. Phần này được ghi nhận là thông tin hồ sơ còn thiếu, không suy diễn từ số phút script chạy.

### Phần AI hỗ trợ

AI hỗ trợ đọc source/bằng chứng, cập nhật công cụ smoke/evaluation, phân tích mismatch và cách ghép bảng, hướng dẫn thao tác Console, soạn báo cáo/worklog và kiểm tra tính toàn vẹn file. Các lượt AWS được sinh viên thực thi trong phiên Learner Lab của mình. Việc chấm lại offline của trợ lý được ghi riêng, không thay thế bằng chứng chạy Textract thật. Sinh viên cần giải thích được cấu hình/mã nguồn và cách tính số liệu khi vấn đáp.

**Báo cáo tuần 3:** [README](docs/week3/README.md). Phép thử độc lập upload output để đo invocation trước/sau chưa có kết quả hoàn chỉnh và không được ghi PASS. Chi phí cuối kỳ, video demo và cleanup được theo dõi trong kế hoạch tuần 4.

**Bộ minh chứng demo mới:** [20261024-014837-product-demo](docs/week3/evidence/20261024-014837-product-demo/README.md), gồm 30 ảnh tổng hợp + PDF + ground truth, năm CSV thật, kết quả smoke/evaluation, manifest và terminal; có lệnh tái lập chấm offline.
