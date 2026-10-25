# Vận hành, bảo mật, chi phí và cleanup

## 1. Giám sát

CloudWatch log groups của 3 Lambda có retention14 ngày. IaC tạo sẵn log groups có tags, không đợi Lambda tạo untagged group. Logs chỉ có stage/document_id/status/counts/error_code, không dump event hay raw extracted text. SNS có s3_key: dùng tên file synthetic, không đưa tên người/thông tin nhạy cảm vào key.

Theo dõi Invocations, Errors, Throttles, Duration p95 và Max Memory Used. Hai alarms IaC: Lambda Errors tổng 3 functions và DocumentErrors từ structured log stage document_error. Alarm SNS có thể gửi thêm mail ngoài thông báo nghiệp vụ. Collector có stage collector_tick, job_submitted/document_completed/lease_lost/notification_failed phục vụ điều tra.

Lỗi đã được handler bắt và lưu FAILED không nhất thiết tăng AWS/Lambda Errors; vì vậy phải xem META và DocumentErrors cùng với Lambda Errors. notification_failed riêng cần tìm log/Scan META notification_status=FAILED; chưa có alarm riêng cho outbox exhaustion. Dashboard không phải bảng thống kê accuracy.

IaC gắn SNS TopicPolicy cho CloudWatch Publish giới hạn đúng account và hai alarm ARN của dự án; đây là resource policy của topic, không phải IAM policy/role mới. Nếu cấu hình thủ công, kiểm tra SNS Access policy cho alarm theo [CloudWatch alarm notifications](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Notify_Users_Alarm_Changes.html), giữ nguyên statements đang cần và không public topic.

Logs Insights, đúng log groups và khoảng thời gian:

```text
fields @timestamp, @message
| filter @message like /document_completed|document_error|notification_failed|lease_lost/
| sort @timestamp desc
| limit 100
```

Log format Lambda mặc định có prefix text; không giả định trường stage luôn được CloudWatch tự parse thành top-level field. Có thể lọc thêm chuỗi document_id. Kiểm tra mọi log stream thay vì chỉ stream đã mở từ lần Test cũ.

## 2. Xử lý sự cố

| Dấu hiệu | Kiểm tra | Hành động |
|---|---|---|
| Không có META sau upload | prefix invoices/forms, S3 notification, same region, Lambda permission, event age/throttle | sửa routing/permission trong phạm vi lab; file input/root không được route |
| META SUBMITTED lâu | Poller Enabled, Collector invocation, WorkIndex Active, due_at/lease_until | invoke Collector `{}`; xem Textract error, không Start job mới tùy tiện |
| PROCESSING quá lease | Collector, GSI, raw checkpoint | Collector tự recover sau lease; không tăng timeout quá lease |
| FAILED AccessDenied | error_code và request thật trong AWS | ghi evidence, hỏi giảng viên; không tạo IAM role mới |
| InvalidS3ObjectException | same region, S3 object/version, LabRole GetObjectVersion, KMS | ưu tiên SSE-S3; không thêm KMS tùy ý |
| PARTIAL | raw Warnings/pages | báo phần thiếu, không coi đủ tài liệu; sửa input rồi upload revision mới |
| COMPLETED nhưng không nhận mail | topic/email Confirmed, outbox PENDING/FAILED, SNS Publish | không xóa OCR result; retry outbox/replay có kiểm soát |
| CSV trống | META status, counts, dataset, include_partial, export đúng bucket/version | xem parsed/raw, không kết luận model lỗi chỉ từ file header |
| Max Memory/timeout | raw bytes/pages/maxjobs, lớn hơn lab guard? | giảm kích thước/tách tài liệu, không tăng giới hạn chưa đo |

Terminal FAILED/REJECTED không tự chạy lại khi replay event cùng revision. Muốn thử lại sau khi sửa phải upload revision mới vào bucket versioned. Giữ nguyên META cũ để audit; không xóa trạng thái để giấu lỗi đánh giá.

## 3. Bảo mật

- S3 private, Block Public Access toàn bộ, BucketOwnerEnforced, SSE-S3 và TLS-only policy trong IaC. Không tạo public URL/function URL/website.
- DynamoDB dùng encryption mặc định của dịch vụ; code không xuất credentials. Không tạo customer-managed KMS key trong lab.
- LabRole có sẵn có thể rộng hơn least privilege của production; ghi rõ đây là constraint. Danh sách action ở architecture.md dùng để review, không tự tạo/attach policy trong lab.
- Versioning bảo vệ overwrite nhưng không thay thế backup; raw/parsed chứa dữ liệu tài liệu, áp dụng retention/cleanup theo yêu cầu môn học.
- CSV UTF-8 BOM, quote bằng csv module, chặn formula injection cho các cell chuỗi bắt đầu =,+,-,@/tab/newline. Mở file trong Excel vẫn cần chính sách xử lý file tin cậy; list JSON không trở thành formula vì bắt đầu '['.
- Người bạn dùng lab/account khác không thấy tài nguyên của account này. Cùng làm code qua Git/review source; không chia sẻ session AWS/cookies/credentials. Nếu giảng viên cung cấp team account thì dùng quyền được cấp, không tạo user mới để chia sẻ.

## 4. Chi phí

Không tạo NAT Gateway/EC2/RDS/OpenSearch. Chi phí chính là Textract theo số trang và feature; AnalyzeDocument FORMS+TABLES cộng chi phí các feature, OCR đã được bao gồm. Đừng gọi DetectDocumentText thêm chỉ để lấy cùng chữ. Xem [AWS Textract pricing](https://aws.amazon.com/textract/pricing/) theo region/volume thực tế; không giả định Learner Lab được hưởng Free Tier như account mới.

Ước tính trước demo: tổng tiền ≈ invoice_pages × rate_AnalyzeExpense + form_pages × (rate_Forms + rate_Tables) + Lambda GB-seconds + requests/storage S3 + DDB/index + SNS + EventBridge + CloudWatch logs/custom metrics/alarms/dashboard. Dùng [AWS Pricing Calculator](https://calculator.aws/) và ngân sách hiện trên tab lab. Không đưa giá ví dụ thành hóa đơn thực tế.

Lịch mỗi phút tương đương1440 Collector invocations/ngày ngay cả không có tài liệu. Disable Poller khi nghỉ dài; bật lại để async/retry hoạt động. Chạy 2 PNG +1 PDF trước, chỉ chạy batch30 sau khi smoke ổn. DDB On-demand phù hợp tải nhỏ biến động; GSI ALL thêm write/storage cost. Logs retention14, versioned outputs/raw có thể tích lũy khi retry/re-export.

End Lab chỉ kết thúc phiên truy cập, **không phải xóa S3/table/topic/rule**. Tài nguyên persistent có thể còn phí. Đọc hướng dẫn cụ thể của course và không để budget cạn. Tắt máy Windows cũng không tắt tài nguyên AWS.

## 5. Cleanup an toàn

Chỉ thực hiện sau demo/lưu evidence, không chạy cleanup tự động khi kết thúc phiên code. Các script cleanup này **chưa được chạy** trong quá trình viết source.

### Stack mới

1. Tải CSV/raw/parsed/ảnh report cần lưu. Dừng mọi upload/worker bên ngoài.
2. Chạy script; nó in account/region/stack/bucket/table, kiểm tra project tag và ownership stack, yêu cầu gõ đúng bucket. Nó disable rule/S3 notifications, chờ240 giây để invocation cũ kết thúc, tạo run `YYYYMMDD-HHMMSS-cleanup-<suffix>` mới và backup mọi S3 object version/DDB items vào `backup/` bên trong run. Manifest ghi hash backup trước delete; thành công đóng PASS, lỗi/cancel đóng FAILED. Có thể chỉ định `-RunDir` mới; không tái sử dụng run cũ.
3. Nếu backup/quyền lỗi, script dừng **trước delete** nhưng triggers đã disabled: muốn tiếp tục dự án phải enable rule và khôi phục notification như template. Không coi backup lỗi là đã cleanup xong.
4. Mặc định delete stack compute/SNS/logs/alarms/dashboard, **retain bucket/table**. Dữ liệu còn nguyên, storage vẫn có thể tính phí. Không deploy lại cùng tên trước khi xử lý retained resources vì CF không tự import chúng.

```powershell
./tools/cleanup.ps1 -Stack textract-full -Region us-east-1
```

Muốn xóa luôn dữ liệu sau khi đã chắc chắn có backup:

```powershell
./tools/cleanup.ps1 -Stack textract-full -Region us-east-1 -PurgeData
```

Phải chọn PurgeData ngay lần chạy stack còn tồn tại, không chạy lại sau khi stack mặc định đã bị xóa. Purge xóa **mọi version và delete marker** của bucket mục tiêu, xóa bucket/table; chỉ khôi phục nội dung được từ backup, không giữ VersionId cũ. Không xóa artifact bucket (có thể đang là bucket tuần 1) hoặc LabRole. Backup là JSON nội dung và numbered binaries, không phải DynamoDB PITR/backup giao dịch; giữ file s3-versions.json để ánh xạ key. Muốn restore hãy đọc schema/manifest, upload dữ liệu và reprocess trong môi trường mới, không tự batch-write checkpoint jobs hết hạn vào hệ thống đang chạy.

Nếu còn writer tạo version mới sau snapshot, delete bucket có thể thất bại thay vì xóa rộng hơn dự kiến; xem lỗi và kiểm tra lại mục tiêu. Script không xóa prefix/bucket khác để “chữa” lỗi.

### Tài nguyên tuần 1 thủ công

Không dùng cleanup stack mới để xóa nhầm tài nguyên tuần 1. Ghi resource inventory trước; disable đúng scheduled rule → bỏ đúng S3 event notification → tải dữ liệu/versions → xóa 3 Lambda → xóa SNS subscriptions/topic → logs/alarms/dashboard của dự án → table → empty versioned bucket rồi delete nếu đã có xác nhận. Không xóa default VPC hoặc LabRole. Ghi lại tài nguyên còn giữ và lý do.

## 6. Báo cáo cuối kỳ

Nêu mục tiêu/ràng buộc → kiến trúc và vai trò của VPC nền tảng (Lambda không gắn vào VPC) → schema → từng chức năng/code path → evidence AWS thực → accuracy 30 tài liệu và sai lệch → chi phí → giới hạn/cải thiện → cleanup. Ghi NOT_RUN hoặc “chưa có ảnh” ở mục chưa có bằng chứng; không dùng test local thay ảnh triển khai AWS thật.
