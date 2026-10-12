# Đồ án Cuối kỳ: Hệ thống Số hóa Hóa đơn và Biểu mẫu tự động với Amazon Textract

> **Môn học:** Điện toán đám mây (Cloud Computing)  
> **Giảng viên hướng dẫn:** TS. Huỳnh Xuân Phụng  
> **Mã học phần:** 261CLCO332779_05  
> **Nhóm sinh viên thực hiện:**  
> - Ninh Nguyễn Minh Tuyên - MSSV: 24110372  
> - Nguyễn Quốc Việt - MSSV: 24110381  

---

## 1. Giới thiệu đề tài & Bài toán thực tế

Trong công việc kế toán và hành chính văn phòng, việc nhập liệu thủ công từ hóa đơn giấy, biên lai thanh toán hay các biểu mẫu khảo sát tốn rất nhiều thời gian và rất dễ sai sót. 

Đề tài này của nhóm hướng đến việc xây dựng một **pipeline xử lý tài liệu thông minh và hoàn toàn tự động trên nền tảng AWS (Serverless Architecture)**. Hệ thống cho phép người dùng chỉ cần tải file scan (ảnh hoặc PDF) lên kho lưu trữ đám mây, toàn bộ quy trình nhận diện chữ, bóc tách bảng biểu, phân tích số tiền, lưu trữ và gửi thông báo qua email sẽ được thực hiện tự động trong vài giây.

Dự án được triển khai và tối ưu chi phí trong môi trường **AWS Academy Learner Lab**.

---

## 2. Hệ thống làm được những gì?

- ⚡ **Xử lý đa dạng định dạng:** Hỗ trợ cả file ảnh đơn trang (PNG, JPEG) và tài liệu nhiều trang phức tạp (PDF, TIFF).
- 🧠 **Trích xuất thông minh với Amazon Textract:**
  - Nhận diện các cặp `Key - Value` (Ví dụ: Tên khách hàng, Ngày lập, Mã số thuế).
  - Tự động bóc tách cấu trúc bảng biểu (`Tables`) mà không làm xáo trộn cột/hàng.
  - Phân tích chuyên sâu hóa đơn tài chính: Đọc tổng tiền, tiền thuế, danh sách các mặt hàng chi tiết (`Line Items`).
- 🔄 **Xử lý bất đồng bộ chống nghẽn (Async + Polling):** Với file PDF nhiều trang, hệ thống kích hoạt cơ chế đọc ngầm bất đồng bộ và dùng EventBridge quét định kỳ 1 phút/lần, khắc phục hoàn toàn giới hạn timeout 15 phút của Lambda.
- 📊 **Tự động xuất file CSV:** Sau khi đọc xong, hệ thống tự động xuất 5 file CSV cấu trúc chuẩn lưu về S3 để người dùng dễ dàng mở bằng Excel.
- 📩 **Thông báo tức thì qua Email:** Tích hợp Amazon SNS để gửi email báo ngay khi tài liệu xử lý xong hoặc báo lỗi khi gặp file hỏng.

---

## 3. Kiến trúc hệ thống trên AWS

```
[Người dùng tải file]
        │ (Hóa đơn / Form: PNG, JPG, PDF)
        ▼
  [S3: input/] 
        │ 
        ├─────────────────────────────────────────┐
        ▼ (Sự kiện ObjectCreated)                 ▼ (Quét định kỳ 1 phút/lần)
 [Processor Lambda]                        [Collector Lambda] (EventBridge)
        │                                         │
        ├─ Ảnh 1 trang: Textract Sync             └─ PDF nhiều trang: Textract Async
        └─ PDF nhiều trang: Gửi Job sang Textract     (Gom trang & xử lý tiếp)
        │                                         │
        └────────────────────┬────────────────────┘
                             ▼
              [Finalize & Parse kết quả]
              - Bóc tách Key-Value, Bảng biểu, Chi tiết hóa đơn
              - Nén JSON thô & JSON kết quả lưu lên S3
              - Ghi chi tiết vào Amazon DynamoDB
              - Xuất 5 file CSV tài liệu lên S3
              - Gửi email thông báo qua Amazon SNS
```

### Các dịch vụ AWS được sử dụng:
1. **Amazon S3:** Lưu trữ file scan đầu vào (`input/`), file kết quả JSON nén (`raw-results/`, `parsed-results/`) và các file CSV (`output/`).
2. **AWS Lambda:** Bộ não điều phối xử lý theo mô hình Serverless gồm 3 hàm: `Processor` (đón nhận file), `Collector` (gom trang PDF), `Exporter` (xuất báo cáo tổng).
3. **Amazon Textract:** Dịch vụ AI/ML nhận diện ký tự quang học (OCR) và bóc tách cấu trúc biểu mẫu.
4. **Amazon DynamoDB:** Cơ sở dữ liệu NoSQL lưu trữ trạng thái xử lý, trường dữ liệu, dòng hàng và chống trùng lặp (Lease lock).
5. **Amazon SNS:** Gửi thông báo kết quả xử lý về email sinh viên.
6. **Amazon EventBridge & CloudWatch:** Lập lịch gọi Lambda định kỳ, ghi log nhật ký và cảnh báo khi có sự cố.

---

## 4. Cấu trúc thư mục mã nguồn

Nhóm tổ chức cây thư mục chuẩn mực, phân tách rõ ràng giữa code chạy trên Lambda, hạ tầng CloudFormation và công cụ kiểm thử:

```text
├── docs/                        # Tài liệu báo cáo, sơ đồ kiến trúc, hướng dẫn vận hành
│   ├── week1/                   # Báo cáo, sơ đồ và bằng chứng thực hiện của Tuần 1
│   ├── architecture.md          # Tài liệu thiết kế kiến trúc chi tiết
│   ├── dynamodb.md              # Thiết kế bảng DynamoDB (PK, SK, WorkIndex)
│   └── guides/                  # Hướng dẫn deploy, test và dọn dẹp tài nguyên
├── infra/
│   └── template.yaml            # File CloudFormation tự động dựng toàn bộ hạ tầng AWS
├── src/textract_pipeline/       # Mã nguồn chính chạy trên AWS Lambda
│   ├── handlers/                # Các điểm vào của Lambda (Processor, Collector, Exporter)
│   ├── processing/              # Logic bóc tách dữ liệu Textract, xuất file CSV
│   └── aws/                     # Các module kết nối AWS SDK (Boto3)
├── tests/                       # Toàn bộ 88 bài unit test kiểm thử offline (Pass 100%)
├── tools/                       # Kịch bản tự động đóng gói ZIP, deploy và đánh giá
└── data/samples/                # Bộ dữ liệu 30 tài liệu mẫu (Invoices & Forms) để kiểm thử
```

---

## 5. Hướng dẫn chạy thử nghiệm tại Local

Dự án hỗ trợ chạy kiểm thử toàn bộ logic trích xuất trên máy local mà không tốn chi phí AWS:

```powershell
# 1. Khởi tạo môi trường ảo Python
python -m venv .venv
.venv\Scripts\activate

# 2. Cài đặt các thư viện phụ thuộc
pip install -e ".[dev]"

# 3. Chạy toàn bộ 88 unit tests
pytest -ra

# 4. Đóng gói code thành file ZIP nạp cho Lambda
python tools/package.py
```

---

## 6. Kế hoạch triển khai qua 4 tuần

- **Tuần 1:** Tìm hiểu dịch vụ AWS, thiết kế kiến trúc hệ thống, dựng nền tảng trên AWS (VPC, S3, DynamoDB, SNS, Lambda skeleton) và chạy smoke test ban đầu. *(Đã hoàn thành)*
- **Tuần 2:** Xây dựng chức năng lõi: Viết mã nguồn Lambda bóc tách dữ liệu Textract, xử lý bảng biểu, xuất CSV và chạy unit test. *(Đã hoàn thành code local)*
- **Tuần 3:** Tự động hóa hạ tầng (IaC) với CloudFormation, thiết lập giám sát CloudWatch Metrics, Alarms và tích hợp toàn diện.
- **Tuần 4:** Kiểm thử tổng thể trên bộ 30 tài liệu mẫu, đánh giá độ chính xác (Accuracy/F1-score), thống kê chi phí Learner Lab, hoàn thiện báo cáo và video demo.
