# BÁO CÁO TIẾN ĐỘ TUẦN 1 — MÔN ĐIỆN TOÁN ĐÁM MÂY

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
