# Cây thư mục và Quy tắc tổ chức dự án

Tài liệu này định nghĩa cấu trúc phân tầng và ranh giới trách nhiệm (Architecture Boundaries) của từng thành phần trong hệ thống pipeline xử lý tài liệu.

---

## 1. Cấu trúc cây thư mục tổng thể

```text
textract-pipeline/
├── src/textract_pipeline/
│   ├── handlers/       # Điểm vào của các hàm AWS Lambda
│   ├── processing/     # Logic nghiệp vụ xử lý bóc tách Textract và xuất file CSV
│   ├── aws/            # Giao tiếp với dịch vụ AWS (S3, DynamoDB, SNS)
│   ├── config.py       # Cấu hình tham số và biến môi trường
│   └── models.py       # Khai báo cấu trúc dữ liệu nội bộ
├── infra/
│   └── template.yaml   # Hạ tầng dạng mã (IaC) tự động hóa bằng CloudFormation
├── tools/              # Kịch bản đóng gói ZIP, deploy, test, chấm điểm và dọn dẹp
├── tests/              # Bộ kiểm thử tự động offline (Unit tests & Integration tests)
├── data/
│   ├── samples/baseline-v1/  # Bộ 30 tài liệu mẫu chuẩn hóa phục vụ nghiệm thu
│   └── templates/            # Bảng mẫu đối chiếu đáp án (Ground-truth template)
├── docs/
│   ├── architecture.md       # Thiết kế kiến trúc hoàn chỉnh và giải pháp mạng
│   ├── architecture-target.png # Sơ đồ luồng dịch vụ AWS tổng quan
│   ├── dynamodb.md           # Thiết kế cơ sở dữ liệu DynamoDB (PK, SK, WorkIndex)
│   ├── plan.md               # Kế hoạch thực hiện và nghiệm thu qua 4 giai đoạn
│   ├── verification.md       # Báo cáo kiểm chứng kết quả chạy test tự động
│   ├── guides/               # Hướng dẫn chi tiết: deploy, test và vận hành
│   └── week1/                # Báo cáo, sơ đồ và ảnh minh chứng thực tế Tuần 1
├── artifacts/          # Thư mục chứa file ZIP và kết quả chạy tạm (bị Git bỏ qua)
├── README.md           # Trang giới thiệu tổng quan đề tài và hướng dẫn cài đặt
├── .gitignore          # Danh sách chặn các file rác và môi trường tạm
├── pyproject.toml      # Cấu hình dự án Python và thư viện phát triển
└── requirements-lambda.txt # Danh sách thư viện Python đóng gói cho Lambda
```

---

## 2. Ranh giới kiến trúc mã nguồn (Code Boundaries)

Mã nguồn được phân tách theo mô hình kiến trúc phân tầng rõ ràng nhằm đảm bảo tính độc lập và dễ kiểm thử:

- **`handlers/` (Tầng tiếp nhận sự kiện - Presentation / Entry Layer):**  
  Là điểm đón nhận các sự kiện từ AWS (S3 Event, EventBridge Scheduled Rule, hoặc gọi thủ công qua Console). Tầng này chịu trách nhiệm bóc tách ngữ cảnh (Event/Context) từ Lambda rồi chuyển tiếp vào tầng xử lý nghiệp vụ, không chứa logic tính toán phức tạp.

- **`processing/` (Tầng nghiệp vụ lõi - Core Domain Layer):**  
  Nắm giữ toàn bộ logic xử lý chính của bài toán: điều phối luồng tài liệu, thuật toán bóc tách JSON Textract (Key-Value, Tables, Line Items), cơ chế khóa tránh chạy trùng (Lease Lock), và chuyển đổi kết quả thành 5 file CSV. Tầng này độc lập với môi trường ngoài và nhận các kết nối AWS thông qua tham số truyền vào.

- **`aws/` (Tầng hạ tầng kết nối - Infrastructure / Data Access Layer):**  
  Quản lý việc gọi SDK `boto3` để giao tiếp với các dịch vụ AWS (Textract, S3, DynamoDB, SNS). Chịu trách nhiệm lưu trữ an toàn, xử lý phân vùng dữ liệu và chia tách file lớn sang S3 để chống tràn giới hạn 400KB của DynamoDB.

- **`tools/` (Tầng công cụ hỗ trợ vận hành - DevOps / Utility Layer):**  
  Chứa các script dòng lệnh phục vụ đóng gói ZIP, tự động triển khai stack, sinh dữ liệu mẫu, kiểm thử E2E và dọn dẹp tài nguyên. Toàn bộ thư mục này **tuyệt đối không bị đóng gói vào file ZIP của Lambda** để giữ kích thước hàm luôn nhẹ nhất.

- **`data/samples/baseline-v1/` (Tập dữ liệu chuẩn hóa):**  
  Bộ dữ liệu chính thức gồm 30 tài liệu (15 hóa đơn, 15 biểu mẫu + 1 PDF nhiều trang) kèm đáp án chuẩn `ground_truth.json` dùng để đánh giá độ chính xác của hệ thống.

---

## 3. Trách nhiệm của các tài liệu kỹ thuật (Documentation Owners)

Mỗi file trong thư mục `docs/` đảm nhận một vai trò cụ thể trong kiến trúc hệ thống:

- **`docs/architecture.md`:** Bản thiết kế kiến trúc toàn diện mô tả luồng dữ liệu (Sync / Async), cơ chế xử lý lỗi, retry và quyết định đặt Lambda bên ngoài VPC để tối ưu chi phí.
- **`docs/dynamodb.md`:** Đặc tả chi tiết lược đồ NoSQL của bảng DynamoDB (khóa chính PK, khóa sắp xếp SK, các loại item META, FIELD, LINE, CELL và sparse GSI WorkIndex).
- **`docs/plan.md`:** Kế hoạch thực hiện đồ án, các ràng buộc của môn học trên AWS Academy Learner Lab và checklist nghiệm thu qua từng tuần.
- **`docs/guides/`:** Bộ cẩm nang thực hành từng bước bao gồm: hướng dẫn triển khai (`deployment.md`), hướng dẫn chạy test (`testing.md`), và hướng dẫn vận hành / dọn dẹp (`operations.md`).
- **`docs/verification.md`:** Báo cáo ghi nhận kết quả chạy 88 bài unit test cục bộ nhằm chứng minh độ tin cậy của mã nguồn.
- **`docs/week1/`:** Nơi lưu trữ tài liệu báo cáo, sơ đồ và bằng chứng ảnh chụp màn hình thực tế của Giai đoạn 1 (dựng nền tảng ban đầu).

---

## 4. Khu vực dữ liệu phát sinh tạm thời (Generated Artifacts)

- Thư mục **`artifacts/`** là nơi chứa các file phát sinh trong quá trình build và chạy test trên máy local, thư mục này được `.gitignore` chặn lại để không làm nặng kho Git.
- **`artifacts/packages/`:** Chứa file ZIP `textract-pipeline.zip` tạm thời sau mỗi lần chạy lệnh build.
- **`artifacts/runs/<run-id>/`:** Mỗi lần chạy thử nghiệm đánh giá hoặc deploy sẽ tự động tạo một thư mục riêng theo mã phiên chạy (Run ID) để lưu vết mã hash, file kết quả và bằng chứng kiểm thử một cách minh bạch.
