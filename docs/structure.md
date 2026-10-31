# Cấu trúc dự án hiện tại

Tài liệu này phản ánh mã nguồn, tài liệu và bằng chứng hiện có trong repository. `artifacts/`, môi trường Python và cache là dữ liệu phát sinh tại máy, được Git bỏ qua và không phải mã nguồn bàn giao.

## Cây thư mục

```text
textract-pipeline/
├── src/textract_pipeline/
│   ├── aws/                  # Adapter boto3 cho Textract, S3, DynamoDB, SNS
│   ├── handlers/             # Entry point cho Processor, Collector, Exporter
│   ├── processing/           # Xử lý tài liệu, parsing, finalize và CSV export
│   ├── config.py             # Đọc và kiểm tra cấu hình Lambda
│   └── models.py             # Kiểu dữ liệu và trạng thái nội bộ
├── infra/
│   └── template.yaml         # CloudFormation cho pipeline textract-full
├── tools/
│   ├── events/               # Event mẫu cho smoke test và gọi Exporter/Collector
│   ├── bundle_source.py      # Đóng gói snapshot mã nguồn
│   ├── cleanup_aws.py        # Backup và cleanup stack AWS
│   ├── cleanup.ps1           # Wrapper PowerShell cho cleanup
│   ├── deploy.py              # Điều phối deployment run
│   ├── deploy.ps1             # Wrapper PowerShell cho deploy
│   ├── evaluate.py            # Đối chiếu CSV với ground truth
│   ├── generate_samples.py   # Sinh tài liệu synthetic
│   ├── package.py             # Tạo gói Lambda
│   ├── run_artifacts.py      # Snapshot, manifest và hash của mỗi lượt chạy
│   ├── smoke_aws.py           # Smoke test trên AWS
│   └── verify_package.py     # Kiểm tra gói Lambda
├── tests/
│   ├── aws/                  # Kiểm tra adapter AWS
│   ├── handlers/             # Kiểm tra Lambda handlers
│   ├── processing/           # Kiểm tra parser, pipeline và exporter
│   └── tools/                # Kiểm tra package, run artifacts và evaluator
├── data/
│   ├── samples/baseline-v1/  # 30 ảnh synthetic, ground truth và PDF demo 2 trang
│   └── templates/            # Mẫu CSV ground truth
├── docs/
│   ├── assets/aws-architecture-icons-2026q3/ # Icon AWS và ghi nguồn
│   ├── guides/               # Hướng dẫn deploy, test, vận hành và cleanup
│   ├── week1/                # README, báo cáo PDF và evidence nền tảng
│   ├── week2/                # README, báo cáo DOCX, ảnh và evidence deploy/smoke
│   ├── week3/                # README, báo cáo DOCX, ảnh và evidence 30 tài liệu
│   ├── week4/                # Thư mục hiện có placeholder rỗng
│   ├── architecture-target.png # Sơ đồ kiến trúc pipeline đang chạy
│   ├── architecture.md       # Luồng xử lý, IAM, VPC tuần 1 và giới hạn
│   ├── dynamodb.md            # Mô hình khóa và item DynamoDB
│   ├── structure.md           # Tài liệu cấu trúc repository này
│   ├── verification.md       # Kết quả kiểm chứng local ngày 11/10/2026
│   └── video_demo.mp4        # Video demo
├── artifacts/                # Dữ liệu sinh khi build/test; bị Git bỏ qua
├── AGENTS.md                 # Quy tắc cộng tác trong repository
├── CLAUDE.md                 # Trỏ tới AGENTS.md
├── README.md                 # Giới thiệu, kiến trúc và hướng dẫn sử dụng
├── WORKLOG.md                # Công việc, phân công và giờ theo tuần
├── pyproject.toml            # Metadata package và cấu hình pytest
├── requirements-lambda.txt  # Dependency được đóng gói cho Lambda
└── .gitignore                # Quy tắc bỏ qua môi trường/cache/artifacts
```

## Trách nhiệm các phần chính

- **`src/textract_pipeline/`** chứa mã chạy trong Lambda: Processor nhận tài liệu từ S3, Collector lấy kết quả Textract bất đồng bộ, Exporter tạo các CSV tổng hợp.
- **`infra/template.yaml`** khai báo stack pipeline bằng CloudFormation. VPC tuần 1 là tài nguyên nền tảng riêng; Lambda không gắn vào VPC đó.
- **`tools/`** chứa các lệnh đóng gói, deploy, smoke test, đánh giá, lưu run artifacts và cleanup.
- **`tests/`** kiểm thử logic xử lý và công cụ ở máy local; các test này không thay thế bằng chứng chạy thật trên AWS.
- **`data/samples/baseline-v1/`** là bộ mẫu chuẩn trong source. Các bản sao tạo cho từng lượt chạy được lưu dưới `artifacts/`.
- **`docs/week1/`–`docs/week3/`** lưu báo cáo tuần và bằng chứng tương ứng; `WORKLOG.md` tổng hợp phân công và thời gian của cả bốn tuần.
- **`artifacts/`**, `.venv`, `__pycache__`, `.pytest_cache` và `*.egg-info` là dữ liệu/môi trường cục bộ; không được đưa vào ZIP mã Lambda.

## Ghi chú trạng thái tài liệu

- `docs/architecture-target.png` chỉ mô tả pipeline đang chạy; VPC tuần 1 được giải thích bằng chữ trong `docs/architecture.md`, không nằm trong sơ đồ pipeline.
- `docs/verification.md` là hồ sơ kiểm thử local tại ngày 11/10/2026, không phải trạng thái hiện tại của deployment AWS.
- `docs/week4/` hiện chỉ có README rỗng và thư mục `assets/` rỗng; nội dung tuần 4 được ghi trong `WORKLOG.md` và video ở `docs/video_demo.mp4`.
- `docs/week3/week3-output-check.csv` hiện chỉ chứa marker `week3,synthetic`; không phải kết quả kiểm thử hay bằng chứng AWS.