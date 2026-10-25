# Hướng dẫn triển khai đầy đủ

## 0. Chọn một trong hai đường triển khai

**A — CloudFormation stack tên riêng:** dễ tái lập và có alarms/dashboard/cleanup script. Tạo tài nguyên `textract-full-*`, không chiếm các tài nguyên tuần 1. Đề xuất khi lab cho phép CloudFormation/EventBridge.

**B — nâng cấp tài nguyên tuần 1 bằng Console:** giữ bucket `textract-pipeline-535709085695`, table `textract-pipeline-results`, topic `textract-pipeline-notifications`, hai Lambda cũ; thêm Collector/WorkIndex/EventBridge. Không chạy script deploy với Prefix=textract-pipeline để cố ghi đè tài nguyên đã tạo thủ công. CloudFormation không tự import tài nguyên trùng tên.

Chỉ thực hiện một đường cho bản demo chính để tránh gọi Textract hai lần/nhầm bucket. Không deploy tự động từ bộ source nếu chưa Start Lab và chưa xác định tài khoản.

## 1. Mở lab và kiểm tra nền tảng chung

1. AWS Academy → khóa AWS Academy Learner Lab → Modules → Launch AWS Academy Learner Lab.
2. Bấm Start Lab; chờ trạng thái sẵn sàng rồi bấm AWS để vào Console. Giữ tab lab để xem thời gian/budget.
3. Chọn region N. Virginia `us-east-1` (hoặc Oregon `us-west-2`), dùng thống nhất cho S3, Lambda, Textract, DynamoDB, SNS, EventBridge.
4. Kiểm tra Account ID. Với lab hiện tại: `535709085695`. IAM → Roles → LabRole → copy ARN `arn:aws:iam::535709085695:role/LabRole`. Không sửa role/trust policy, không chọn tạo role mới.
5. Ghi lại Project=`TextractDocumentDigitization`; Owner=`24110372-24110381`. Giữ nguyên hoa/thường tên key.
6. Có thể gặp explicit deny iam:GetPolicy trên trang Permissions dù execution role đã đúng. Đó chưa chứng minh S3/Textract bị deny; kiểm tra API cần dùng qua smoke và CloudWatch. Không cố thêm quyền vượt hạn chế của lab.

## 2A. Chuẩn bị máy cho IaC

1. Cài Python 3.12+ và AWS CLI v2 từ [AWS CLI install guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html). Mở PowerShell tại C:\textract-pipeline.
2. Chạy các lệnh install/tests/package trong README. Không cần VS Code để Lambda chạy; VS Code chỉ là editor tùy chọn.
3. Trong tab lab, AWS Details → AWS CLI credentials. Đặt temporary AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN trong môi trường PowerShell hiện tại hoặc profile riêng ngoài repo. Không gửi keys cho người khác, không lưu vào file dự án, ảnh báo cáo hoặc Git. Cần đủ cả session token; hết phiên phải lấy bộ mới.
4. Kiểm tra danh tính/region, không in credentials:

```powershell
aws sts get-caller-identity --region us-east-1 --no-cli-pager
aws configure get region
```

5. Artifact bucket có sẵn phải cùng region, private và SSE-S3; có thể dùng bucket tuần 1 `textract-pipeline-535709085695`. Package chỉ upload `artifacts/...`, không khớp trigger input/. Nếu tạo bucket artifact mới, bật Block all public access, SSE-S3, gắn Project/Owner.
6. Script deploy không tạo role. Session vẫn cần quyền CloudFormation và iam:PassRole cho **LabRole**. Nếu AccessDenied/explicit deny, lưu lỗi và chuyển sang Console nếu được phép; không có workaround bảo đảm vượt quyền lab.

## 3A. Deploy stack mới

Tạo deployment run mới, build và verify tại chỗ trước khi gọi AWS:

```powershell
$deploymentRun = "artifacts/runs/$(Get-Date -Format yyyyMMdd-HHmmss)-aws-deployment-$([guid]::NewGuid().ToString('N').Substring(0,8))"
.venv/Scripts/python.exe tools/package.py --run-dir $deploymentRun --kind aws_deployment
.venv/Scripts/python.exe tools/verify_package.py --run-dir $deploymentRun
.venv/Scripts/python.exe tools/bundle_source.py --run-dir $deploymentRun
./tools/deploy.ps1 -RunDir $deploymentRun -ArtifactBucket textract-pipeline-535709085695 -Region us-east-1 -Prefix textract-full -Owner 24110372-24110381 -Email 'EMAIL_THAT_CUA_BAN'
```

`deploy.ps1` gọi `deploy.py`, kiểm tra STS/account, region artifact bucket, project tag, template snapshot và hash package. Script upload đúng ZIP trong run đã verify, dùng SHA256 làm artifact key, deploy stack có tags và lưu Outputs trong `evidence/deployment.json`. **Không build lại hoặc dùng ZIP làm việc.** Thành công đóng manifest PASS; lỗi ghi FAILED, retry tạo run mới. Source ZIP phải khớp toàn bộ source/requirements đã build và template deploy. Không sửa các đầu vào giữa những bước này. Không cần CAPABILITY_NAMED_IAM vì template không tạo IAM resources. Giá trị Email là email nhận thông báo, không dùng literal EMAIL_THAT_CUA_BAN.

Script mặc định yêu cầu Account=535709085695. Chỉ truyền `-ExpectedAccount <ID_mới>` khi đã kiểm tra và chủ động triển khai vào lab khác; không sửa để bỏ qua lỗi nhầm account. Script kiểm tra artifact region và từ chối update stack trùng tên nhưng khác Project tag.

Nếu PowerShell chặn script theo chính sách thiết bị, đọc và thực hiện lệnh tương đương bên trong script hoặc làm theo quy định của trường; không tự sửa chính sách máy toàn cục.

Đợi CloudFormation → Stacks → textract-full → CREATE_COMPLETE. Nếu CREATE_FAILED/ROLLBACK, mở Events để tìm resource đầu tiên lỗi. Không nhận stack đang rollback là thành công. Sau deploy:

1. Outputs: lưu BucketName, TableName, TopicArn, 3 function names, PollerName.
2. SNS → Topics → topic mới → Subscriptions; mở email xác nhận. Phải Confirmed. Nếu bỏ trống Email khi deploy thì tạo email subscription thủ công.
3. S3 → bucket mới → Properties: Versioning Enabled; SSE-S3; event prefix input/. Permissions: Block all public access ON; TLS-only bucket policy.
4. DynamoDB → table → Settings: Active/On-demand; Indexes → WorkIndex Active.
5. Lambda → từng function → Configuration → Permissions: LabRole; Environment variables theo bảng dưới; VPC không gắn.
6. EventBridge → Rules (không phải Scheduler) → textract-full-poller: Enabled, rate(1 minute), target Collector.
7. CloudWatch → Log groups/Alarms/Dashboards: logs retention14, hai alarms, dashboard mới; Tags cho resource hỗ trợ.

Để hạn chế lịch chạy khi chưa demo, deploy `-PollingState DISABLED`; smoke script vẫn invoke Collector thủ công. Bật lại khi cần vận hành nền.

## 2B. Chuẩn bị S3/table/SNS tuần 1

1. S3 → bucket `textract-pipeline-535709085695` → Properties → Bucket Versioning → Edit → Enable → Save changes. Giữ SSE-S3; Bucket Key không có tác dụng với SSE-S3. Permissions → giữ toàn bộ Block public access.
2. Objects → Create folder → `input` nếu chưa có. Mở input → Create folder `invoices`, rồi `forms`. Tạo `output` ở root nếu muốn; raw-results/parsed-results sẽ xuất hiện khi code ghi object, không cần tạo trước.
3. Properties → Tags → Add: Project/Owner như trên. Không bật S3 Bucket ABAC chỉ để thêm tag thông thường.
4. DynamoDB → Tables → `textract-pipeline-results` → Settings: PK=PK String, SK=SK String, capacity On-demand. **Giữ bảng cũ, không xóa/tạo lại.**
5. Table → Indexes → Create index: partition key `work_pk`, type String; sort key `due_at`, type Number; Index name `WorkIndex`; projection All. Theo capacity của On-demand table. Create index, đợi Active. Attribute work_pk/due_at chỉ cần có trên META đang làm việc; không thêm field thủ công cho mọi item.
6. Table → Settings → kéo xuống Tags (giao diện có thể nằm phần dưới cùng) → Manage tags → thêm Project, Owner → Save. Không nhầm menu Settings của service với tab Settings của bảng.
7. SNS → Topics → topic cũ Standard → Tags: đủ hai tags. Subscriptions Confirmed. Publish message một thông báo synthetic để kiểm tra mail; chụp email, không chứa credentials.

## 3B. Upload code cho Processor và Exporter

1. Tạo package run riêng tại máy, verify và đóng để có snapshot dùng upload thủ công:

```powershell
$manualPackageRun = "artifacts/runs/$(Get-Date -Format yyyyMMdd-HHmmss)-manual-package-$([guid]::NewGuid().ToString('N').Substring(0,8))"
.venv/Scripts/python.exe tools/package.py --run-dir $manualPackageRun
.venv/Scripts/python.exe tools/verify_package.py --run-dir $manualPackageRun
.venv/Scripts/python.exe tools/run_artifacts.py finish --run-dir $manualPackageRun
```

Manifest này chỉ xác nhận package, không chứng minh deployment Console. Khi upload, lưu screenshot/version và CodeSha256 của Lambda để đối chiếu SHA256 trong manifest.

2. Lambda → Functions → textract-pipeline-processor → Code → Upload from/Update → .zip file → chọn `$manualPackageRun/packages/textract-pipeline.zip` → Save. ZIP có nhiều module, **không chỉ copy processor.py vào lambda_function.py**.
3. Code → Runtime settings → Edit: Python 3.13; Handler=`textract_pipeline.handlers.processor.lambda_handler`; giữ x86_64 hoặc ARM64 nếu đã có (dependencies pure Python), Save.
4. Configuration → General configuration → Edit: Memory=1024 MB, Timeout=3 min → Save.
5. Configuration → Permissions: execution role LabRole. Không sửa resource-based permission S3 đang hoạt động. VPC không cấu hình; Function URL không tạo.
6. Configuration → Environment variables → Edit → thêm các biến trong bảng. Giữ biến cần thiết khác, không dùng credential như env vars của Lambda.
7. Configuration → Tags → Edit → Project/Owner.
8. Làm tương tự Exporter: cùng ZIP, handler exporter, memory512 MB, timeout3 min; không gắn S3 trigger cho Exporter.

| Function | Handler | Environment variables bắt buộc |
|---|---|---|
| Processor | textract_pipeline.handlers.processor.lambda_handler | RESULTS_TABLE=textract-pipeline-results; DATA_BUCKET=textract-pipeline-535709085695; NOTIFICATION_TOPIC_ARN=arn:aws:sns:us-east-1:535709085695:textract-pipeline-notifications; LEASE_SECONDS=240 |
| Collector | textract_pipeline.handlers.collector.lambda_handler | cùng Processor; WORK_INDEX=WorkIndex (mặc định đã đúng) |
| Exporter | textract_pipeline.handlers.exporter.lambda_handler | RESULTS_TABLE, DATA_BUCKET như trên; không cần SNS |

AWS_REGION do Lambda cung cấp, không đặt thủ công trong Lambda. Có thể để trống NOTIFICATION_TOPIC_ARN khi test local/no SNS, nhưng nghiệm thu hệ thống phải bật SNS.

## 4B. Tạo Collector và lịch polling

1. Lambda → Create function → Author from scratch → name `textract-pipeline-collector`, Runtime Python3.13.
2. Mở Additional settings: bật Custom execution role → Use existing role → LabRole. ARM64 optional; VPC/Function URL/Durable execution/EC2 capacity provider không bật. Bật Tags rồi thêm Project/Owner. Create function.
3. Upload cùng ZIP; handler `textract_pipeline.handlers.collector.lambda_handler`; memory1024 MB; timeout3 min; env theo bảng; xác nhận LabRole.
4. EventBridge → Rules → chọn default event bus → Create rule. Name `textract-pipeline-poller`, loại Schedule. Nếu giao diện khuyến nghị Scheduler, chọn tiếp tạo **scheduled rule/legacy scheduled rule**, không tạo Scheduler execution role mới.
5. Schedule expression: rate(1 minute). Target AWS service → Lambda → textract-pipeline-collector; input `{}`. Lambda target không cần execution role. Nếu Console yêu cầu role kiểu Scheduler, đang ở sai loại tài nguyên; quay lại Rules.
6. Tags Project/Owner; Create rule. Sau đó Lambda Collector → Configuration → Permissions → Resource-based policy phải cho events.amazonaws.com invoke từ ARN đúng rule.
7. Nếu Console không tự thêm permission, dùng AWS CLI (chỉ permission của function, không IAM role):

```powershell
aws lambda add-permission --function-name textract-pipeline-collector --statement-id EventBridgePoll --action lambda:InvokeFunction --principal events.amazonaws.com --source-arn arn:aws:events:us-east-1:535709085695:rule/textract-pipeline-poller --source-account 535709085695 --region us-east-1
```

Nếu StatementId đã tồn tại, đọc policy trước, không chạy add lặp hoặc xóa permission khác. Nếu lab không cho EventBridge rule, Collector vẫn có thể Test với `{}` định kỳ thủ công cho demo, nhưng báo cáo phải ghi rõ **chưa có asynchronous automation** cho đến khi được quyền tạo lịch.

## 5B. Xác nhận S3 trigger

Processor → Configuration → Triggers → S3 → Details: đúng bucket, Event s3:ObjectCreated:*, prefix input/, suffix trống. Nếu đã có trigger đúng thì **không tạo thêm**.

Nếu chưa có: Add trigger → S3 → bucket → All object create events → Prefix `input/` → xác nhận cảnh báo cùng bucket input/output → Add. Prefix tách output/raw/parsed giúp tránh recursive invoke; không ghi bất cứ kết quả nào vào input/.

Lỗi “Unable to validate destination configurations”: kiểm tra bucket/Lambda cùng region, resource-based permission S3, ARN SourceAccount và các event notification cũ trỏ function đã xóa. Không chữa bằng việc đổi LabRole một cách suy đoán. Không xóa toàn bộ notifications nếu bucket còn workflow khác.

## 6. Test từng thành phần và toàn hệ thống

1. Sinh 30 mẫu bằng lệnh README. Upload 1 invoice PNG vào input/invoices/, 1 form PNG vào input/forms/ (không smoke-test.txt, vì code mới từ chối txt).
2. Processor → Monitor → View CloudWatch logs → stream gần nhất: tìm document_completed/status=COMPLETED, document_id. Không tìm content PII trong log.
3. DDB → Explore items → Query PK DOC#<id>: META COMPLETED, counts >0 và FIELD/LINE/CELL tương ứng. Không chỉ nhìn invocation Succeeded để kết luận dữ liệu đúng.
4. S3 output/<id>/ có 5 CSV; mở kiểm tra data, raw-results/parsed-results có gzip; SNS email thông báo hoàn tất.
5. Upload data/samples/baseline-v1/async-demo/multipage-form.pdf vào input/forms/. Processor log job_submitted, META SUBMITTED. Theo dõi Collector cho tới COMPLETED/PARTIAL/FAILED; kiểm tra pages=2 nếu thành công. Không để Lambda Processor sleep chờ Textract.
6. Test duplicate/invalid/output, sau đó chạy ≥30 docs/evaluation theo docs/guides/testing.md.

Smoke script tự lấy Outputs chỉ dành cho **đường A CloudFormation**. Đường B dùng Console kiểm tra hoặc gọi boto3/CLI theo tên tài nguyên cũ; không chạy `--stack textract-full` rồi tưởng nó kiểm tra tài nguyên tuần 1.

## 7. Giám sát thủ công nếu dùng đường B

CloudWatch → Log groups → từng /aws/lambda/textract-pipeline-* → retention Edit 14 days; Tags Project/Owner. Exporter chỉ sinh log group sau invocation đầu tiên nếu chưa tạo trước. Tạo alarm Lambda Errors >=1 /5 min, Treat missing data notBreaching, action SNS topic cũ; tag alarm. Thêm dashboard Invocations/Errors/Throttles/Duration của 3 functions. Chi tiết docs/guides/operations.md.

IaC đường A đã có cấu hình này; không cần tạo bản trùng thủ công. Lưu screenshot theo từng bước để báo cáo, không dùng ảnh tuần 1 để chứng minh chức năng Textract mới đã chạy.
