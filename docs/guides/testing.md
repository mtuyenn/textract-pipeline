# Kiểm thử và đánh giá độ chính xác

## 1. Các lớp bằng chứng

| Lớp | Công cụ | Chứng minh được | Không chứng minh được |
|---|---|---|---|
| Unit/component local | pytest, in-memory AWS boundaries, botocore Stubber | parser, API parameters, state transitions, CSV/evaluator | IAM thật, Textract OCR accuracy, billing, delivery email |
| IaC static | cfn-lint | template schema, references/dependency checks | lab có quyền deploy, resource creation runtime |
| AWS smoke | Console hoặc tools/smoke_aws.py | upload→processing→DDB→CSV, sync/async, duplicate core flow | ≥30-document accuracy, email receipt nếu chưa xác nhận thủ công |
| AWS evaluation | upload >=30, real CSV + ground_truth.json | accuracy/precision trên bộ mẫu cụ thể | chất lượng mọi layout hoặc tiếng Việt |

Không lấy output giả/mock để điền “độ chính xác Textract=100%”. Tests fixture chỉ kiểm tra chương trình.

## 2. Chạy tests local

```powershell
.venv/Scripts/python.exe -m pytest -v
.venv/Scripts/python.exe -m compileall -q src tools tests
.venv/Scripts/python.exe -m pip install cfn-lint==1.57.2
.venv/Scripts/cfn-lint.exe infra/template.yaml
```

Phạm vi: KVP relationships/checkbox/confidence, merged cells/spans, result fragments chứa relationships khác nhau, expense duplicate types/line pagination; lease/duplicate/stale version, sync/async API version/token; IN_PROGRESS/checkpoint/resume, PARTIAL/FAILED, SNS retry không hạ trạng thái, CSV retry dùng lại raw, overflow children, query/scan pagination, formula protection/UTF-8 BOM, evaluation missing/failed/extra predictions.

### Lưu một lần kiểm chứng có thể truy vết

Tạo tên riêng trước; không tự tạo thư mục đó, `package.py` phải tạo độc quyền:

```powershell
$taskRunDir = "artifacts/runs/$(Get-Date -Format yyyyMMdd-HHmmss)-local-verification-$([guid]::NewGuid().ToString('N').Substring(0,8))"
.venv/Scripts/python.exe tools/package.py --run-dir $taskRunDir --kind local_verification
.venv/Scripts/python.exe tools/verify_package.py --run-dir $taskRunDir
.venv/Scripts/python.exe tools/run_artifacts.py pytest --run-dir $taskRunDir
.venv/Scripts/python.exe tools/bundle_source.py --run-dir $taskRunDir
.venv/Scripts/python.exe tools/run_artifacts.py finish --run-dir $taskRunDir
```

`--new-run` thay cho `--run-dir` cũng tự tạo tên và in đường dẫn; dùng đường dẫn đó cho các bước sau. Với kind `local_verification`, thiếu ZIP/import/SDK/pytest/source bundle thì không đóng PASS được. Cần thêm kết quả/ảnh riêng thì đăng ký trong bước của công cụ trước khi finish; không ghi tay vào run đã đóng.

`verify_package.py --package <ZIP>` kiểm tra đúng ZIP được chọn. Nếu ZIP thuộc run đang mở, kết quả ghi vào manifest; nếu run đã đóng, chỉ đọc và kiểm tra hash/import, không đổi manifest. Verify không tham số kiểm tra ZIP làm việc và không tạo bằng chứng lịch sử. Build nhanh/source bundle nhanh dùng atomic replace nên lỗi không thay file làm việc cũ.

Các test quản lý artifact kiểm tra tạo trùng run, khóa ghi, chống ghi đè, input snapshot, hash sai, run thất bại, deploy không rebuild và build lần hai không thay lần một. Test AWS/deploy dùng boundaries giả; kiểm chứng ZIP/SDK thật phải chạy riêng như trên.

## 3. Bộ dữ liệu

```powershell
.venv/Scripts/python.exe tools/generate_samples.py --output artifacts/datasets/baseline-v1 --count 30
```

Bộ chuẩn được lưu trong `data/samples/baseline-v1/`: 15 hóa đơn và 15 forms tiếng Anh PNG 1275×1650; thêm 1 PDF 2 trang để demo async (ngoài denominator30). Lệnh trên sinh bộ thử vào artifacts, không ghi đè bộ chuẩn. Muốn chạy bộ thử, truyền `--samples artifacts/datasets/baseline-v1` cho smoke và dùng ground truth ở cùng bộ đó khi đánh giá. Ground truth gồm 120 summary/form fields, 30 invoice line items (90 required line fields), 180 table cells. Mẫu invoice khai báo PRICE là thành tiền từng dòng, UNIT_PRICE là đơn giá; kiểm tra Textract có nhận đúng semantic trước khi kết luận lỗi OCR.

Bộ này là baseline layout sạch, thay đổi giá trị/nội dung; không phải tập đa dạng scan thật. Để báo cáo sâu hơn, mở rộng thêm blur/rotation/shadow/crop và layout khác, kèm ground truth tương ứng; không tuyên bố baseline đại diện production.

## 4. AWS smoke tự động (stack mới)

Start Lab + credentials hợp lệ, hoàn tất deployment run theo [hướng dẫn triển khai](deployment.md), xác nhận email subscription. Gán đường dẫn run deploy PASS đã in vào `$deploymentRun` rồi chạy:

```powershell
.venv/Scripts/python.exe tools/smoke_aws.py --stack textract-full --region us-east-1 --learner-lab-active --deployment-run $deploymentRun
```

Script tạo run `aws_smoke` mới, in đường dẫn, snapshot dataset/package/manifest deploy và đối chiếu account/region/stack/hash code Lambda trước upload. Mặc định upload 2 PNG + 1 PDF, chờ terminal status tối đa30 phút, invoke Collector thủ công nếu cần, yêu cầu tất cả COMPLETED, replay đúng revision event để kiểm tra duplicate, invoke Exporter và tải 5 CSV. Chạy thất bại trả exit code khác0, lưu smoke.json và manifest FAILED; chạy xong đóng PASS chỉ cho phạm vi core smoke, các check thủ công ghi NOT_RUN. Không tự tạo lại tài nguyên hay thay role. Trường hợp PARTIAL không được coi smoke pass.

Script kiểm tra prefix notification configuration; **không** gọi đó là bằng chứng không phát sinh invocation khi upload output/. Email receipt và negative invocation test phải kiểm tra thêm thủ công.

## 5. Checklist kiểm thử thủ công

1. Invoice PNG → AnalyzeExpense: summary fields + line items đúng, counts khớp raw/parsed/DDB/CSV.
2. Form PNG → AnalyzeDocument: key/value đúng, hàng/cột/merged/spans đúng; confidence không phải accuracy đo được.
3. PDF 2 trang → SUBMITTED → Collector → COMPLETED; pages=2; parser ghép được fragment, CSV không thiếu trang.
4. Replay cùng event/version → DUPLICATE_OR_IN_PROGRESS, không thêm META/children. Upload lại qua S3 versioned sẽ tạo **revision mới**, không phải duplicate event test.
5. File .txt vào input/forms/ → REJECTED, email lỗi (code mới không xử lý smoke-test.txt như OCR).
6. Output negative: dừng mọi upload khác; ghi timestamp/counter Invocations Processor; upload output/output-smoke-test.csv; đợi logs/metrics cập nhật, Search **all** log streams trong đúng time range. Không có invocation mới, đồng thời cấu hình prefix input/ đúng. Không chỉ đếm số log streams vì một stream có thể chứa nhiều invocations. S3 delivery bất đồng bộ nên ghi cửa sổ quan sát thay vì khẳng định tuyệt đối chỉ từ việc chưa thấy log.
7. Giả lập SNS failure trong unit tests đã có; trên lab nếu muốn fault injection phải có kế hoạch khôi phục, không sửa LabRole/deny policy để thử. Dùng evidence unit test và ghi rõ phạm vi thay vì phá IAM lab.
8. Stop/Start Lab: kiểm tra resource tồn tại; session credentials đổi không yêu cầu tạo lại table/bucket. Theo hướng dẫn chính course; End Lab không tương đương cleanup, tài nguyên lưu trữ/lịch có thể còn phát sinh phí.

Lưu ảnh: S3 input, processor log, async SUBMITTED/collector log, DDB META+children, CSV nội dung, SNS Confirmed/email, trigger prefix, dashboard/alarms. Che thông tin định danh khi chia sẻ công khai; không chụp credentials.

## 6. Chạy ≥30 tài liệu thật và tính accuracy

```powershell
$smokeRun = "artifacts/runs/$(Get-Date -Format yyyyMMdd-HHmmss)-aws-smoke-accuracy-$([guid]::NewGuid().ToString('N').Substring(0,8))"
.venv/Scripts/python.exe tools/smoke_aws.py --stack textract-full --all --no-pdf --learner-lab-active --deployment-run $deploymentRun --run-dir $smokeRun
$evaluationRun = "artifacts/runs/$(Get-Date -Format yyyyMMdd-HHmmss)-evaluation-$([guid]::NewGuid().ToString('N').Substring(0,8))"
.venv/Scripts/python.exe tools/evaluate.py --smoke-run $smokeRun --run-dir $evaluationRun
```

Trước khi chạy lệnh smoke, Start Learner Lab, đặt credentials tạm thời mới của lab trong PowerShell và xác nhận stack deployment còn hoạt động trong đúng account/region. Cờ bắt buộc `--learner-lab-active` là xác nhận rõ ràng của người vận hành; smoke sau đó gọi STS trước khi đọc stack, đối chiếu Account ID với deployment run, và kiểm tra hash Lambda trước khi upload. Script không deploy hoặc dọn tài nguyên. `--all --no-pdf` tải đúng bộ PNG có ground truth (>=30); PDF demo async không thuộc mẫu số accuracy.

Smoke run lưu danh sách upload/version, account/region, trạng thái DynamoDB, phản hồi export, 5 CSV thật và hash của dataset/package/deployment. Evaluator chấm 4 CSV documents/fields/line_items/table_cells; `table_rows.csv` vẫn được lưu làm bằng chứng export. Evaluator chỉ nhận smoke run đã PASS; nó tạo run `evaluation` riêng, snapshot toàn bộ dataset, CSV, smoke.json và smoke manifest, rồi lưu `evaluation.json`. Manifest evaluation ghi hash các đầu vào và source smoke run, nên có thể tái lập scoring mà không gọi AWS lại. PASS chỉ có nghĩa scoring hoàn tất, không có nghĩa accuracy đạt một ngưỡng.

Nếu tài liệu FAILED/PARTIAL, smoke dừng trước export để không giả PASS. Có thể lấy CSV thủ công để chấm cả thất bại; tải vào khu vực làm việc mới, không ghi vào run smoke FAILED đã đóng:

```powershell
$manualExportDir = "artifacts/manual-exports/$(Get-Date -Format yyyyMMdd-HHmmss)-$([guid]::NewGuid().ToString('N').Substring(0,8))"
New-Item -ItemType Directory -Path $manualExportDir | Out-Null
aws lambda invoke --function-name textract-full-exporter --cli-binary-format raw-in-base64-out --payload file://tools/events/export-all.json --region us-east-1 "$manualExportDir/export-response.json"
# Thay BUCKET_NAME bằng Output thật của stack:
aws s3 cp s3://BUCKET_NAME/output/exports/ "$manualExportDir/exports/" --recursive --region us-east-1
.venv/Scripts/python.exe tools/evaluate.py --truth "$smokeRun/inputs/dataset/ground_truth.json" --exports "$manualExportDir/exports"
```

Kiểm tra response không có FunctionError; HTTP StatusCode 200 của Invoke không đủ chứng minh handler thành công. Run evaluation snapshot CSV nhập tay nhưng không chứng minh những CSV này đến từ đúng Lambda: cần giữ response/log và liên kết run smoke FAILED trong báo cáo. Không biến kết quả manual thành smoke PASS.

Evaluator chọn revision mới nhất cho mỗi source key (kể cả revision FAILED mới hơn), không lấy bản cũ thành công để che lỗi. Missing/failed docs vẫn tính ground-truth denominator. PARTIAL có thể đánh giá phần nhận được nếu export include_partial=true; phần thiếu vẫn bị tính sai.

- Field accuracy = số expected fields có tên/page/value khớp / tổng expected fields.
- Field precision = matched fields / tổng predicted fields ở tài liệu trong tập đánh giá; extra predictions làm giảm precision.
- Line-item field accuracy = từng ITEM/QUANTITY/PRICE khớp theo expense/group/line ordinal. Bỏ LINE_ITEM description bổ sung khỏi metric này.
- Line-item accuracy = dòng có toàn bộ required fields đúng / tổng expected dòng.
- Table-cell accuracy = đúng page/table/row/column/value / tổng expected cells; merged overlays không đếm hai lần. Việc sai row/column là lỗi kể cả text đúng.
- Chuẩn hóa NFKC/case/whitespace; chỉ tên numeric định trước mới chuẩn hóa số/currency. Không bỏ leading zeros của invoice ID. Ngày phải đúng chuỗi, chưa quy đổi mọi format ngày.

Lưu evaluation.json có correct/expected/predicted/accuracy/precision và mismatches; đính kèm 30 input + ground truth + real CSV + smoke evidence. PASS của evaluation chỉ xác nhận scoring chạy xong, không ép ngưỡng accuracy. Mục tiêu tham khảo để thảo luận: field accuracy >=90% trên baseline; chỉ ghi đạt sau khi đo, không hard-code threshold thành số đo.

## 7. Demo đề xuất (5–7 phút)

Mở sơ đồ → upload invoice + form → DDB/CSV/mail → PDF2trang và Collector → duplicate/output isolation → báo cáo30docs → CloudWatch/chi phí → cleanup plan. Không xóa tài nguyên trước khi lưu bằng chứng và demo xong.
