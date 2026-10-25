# Kế hoạch triển khai hoàn chỉnh

## Yêu cầu môn học

- Dùng `us-east-1`; chỉ dùng `LabRole`/`LabInstanceProfile` được cấp, không tạo IAM user hoặc role. Nếu dùng EC2: loại nano đến large, tối đa 9 instance và 32 vCPU chạy đồng thời mỗi Region; EBS tối đa 100 GB, loại gp2/gp3.
- Gắn `Project` và `Owner` cho tài nguyên dự án. Dừng hoặc xóa tài nguyên sau mỗi buổi lab và ghi chi phí sử dụng cuối kỳ.
- Bàn giao mã nguồn/template trên Git, báo cáo kèm sơ đồ kiến trúc, ảnh Console/CLI có Account ID, Region và thời gian, cùng video demo tối đa 10 phút.

## 1. Cấu trúc, kiến trúc và nền tảng

- [x] Tổ chức code và dữ liệu theo [structure.md](structure.md).
- [x] Thiết kế sync/async, schema DynamoDB, retry/idempotency; sơ đồ Mermaid và SVG.
- [x] Viết CloudFormation: tham chiếu LabRole có sẵn, tags, S3 private/versioning/SSE-S3, DynamoDB On-demand, SNS, Lambda, EventBridge, CloudWatch; stack `textract-full` triển khai thành công ngày 17/10/2026.
- [x] Hướng dẫn nâng cấp tài nguyên tuần 1 hoặc tạo stack tên riêng.

Nghiệm thu: có sơ đồ, schema, IAM/routing constraints và cấu hình có thể kiểm tra; không tự nhận ownership tài nguyên thủ công.

## 2. Chức năng lõi và kiểm thử thành phần

- [x] Parser Forms KVP/checkbox; tables/cells/merged cells/spans.
- [x] Parser Expense SummaryFields/LineItemGroups, bảo toàn duplicate types, merge pagination.
- [x] Processor: S3 decode/version/ETag, validate size/route, Analyze sync, Start async với token idempotent.
- [x] Collector: polling, pagination/checkpoint, timeout budget, retry/throttling.
- [x] DynamoDB metadata/children, giới hạn item size, raw/parsed JSON S3.
- [x] SNS outbox: kết quả COMPLETED vẫn được giữ khi gửi mail lỗi, retry at-least-once.
- [x] Export CSV UTF-8 BOM, query/scan pagination, chống formula injection.
- [x] 30 synthetic documents + ground truth + PDF2trang; code field/line-item/table-cell evaluation.

Nghiệm thu: tests thực thi logic với botocore stubs/fake storage; tests cục bộ không thay thế accuracy trên Textract thật.

## 3. Tích hợp, bảo mật, giám sát, IaC

- [x] ZIP packaging; deploy/cleanup scripts; region/account/role validation trong script. Deploy thực tế đã PASS ngày 17/10/2026; chưa ghi nhận thực thi cleanup.
- [x] Cấu hình CloudWatch logs/retention, dashboard/alarms; tags trên resource có hỗ trợ trong IaC.
- [x] Console/CLI runbook, checklist quyền LabRole và nâng cấp tài nguyên tuần 1.
- [x] Kiểm chứng local trước và sau tổ chức lại; xem [verification.md](verification.md).
- [x] Run snapshot riêng, manifest/hash dùng chung; deploy đúng ZIP đã verify, smoke/evaluation/cleanup lưu run độc lập.
- [x] Xác minh session triển khai và runtime trên AWS qua deployment/smoke PASS; Console tuần 3 xác nhận ba Lambda dùng LabRole. Phiên `voclabs` có hạn chế đọc `iam:GetPolicy`, được ghi riêng trong báo cáo.

Nghiệm thu: source/package/test chạy được; không lưu credential trong source/log/config.

## 4. E2E, accuracy, chi phí, báo cáo/demo

- [x] AWS smoke invoice/form PNG, PDF hai trang và duplicate PASS ngày 17/10/2026; ảnh email bổ sung cho SNS.
- [x] Chạy 30 tài liệu qua Textract ngày 24/10/2026: 30 COMPLETED, xuất năm CSV, so ground truth và lưu evaluation run riêng.
- [x] Demo lại ngày 24/10/2026 lúc 01:48: 30 ảnh + PDF hai trang, 31/31 COMPLETED; smoke và evaluation mới đều PASS, hash bằng chứng khớp manifest.
- [x] Xác nhận notification prefix `input/` trên stack chính và ghi nhận các CSV đã được xuất vào `output/`.
- [ ] Phép thử độc lập upload output và đối chiếu invocation trước/sau: NOT_RUN trên stack chính; không gộp với trạng thái chức năng xuất CSV đã được chứng minh.
- [x] Viết hướng dẫn chi phí/demo và cleanup có backup/xác nhận.
- [ ] Ghi chi phí thực tế, thực hiện demo và cleanup sau nghiệm thu.

Nghiệm thu AWS: CSV khớp DDB/S3, async hoàn tất, nhận email, ghi metric accuracy thật. Các bước cần AWS session được để NOT_RUN cho đến khi thực thi; không tự tạo số accuracy.

## Bàn giao tại máy — ghi nhận lịch sử ngày 11/10/2026

Ngày 11/10/2026 đã tổ chức lại theo [structure.md](structure.md): handlers/processing/aws, công cụ trong tools, dữ liệu trong data, đầu ra trong artifacts và tài liệu phân nhóm. Giữ 53 tests của đợt tổ chức code, thêm 35 ca về snapshot/hash/vòng đời run và các công cụ, tổng 88 tests đạt. Kết quả chi tiết và giới hạn ở [verification.md](verification.md).

Tại thời điểm 11/10/2026, source, kiến trúc, IaC, scripts và unit/component tests đã hoàn thành cục bộ; AWS deployment/E2E/accuracy30docs khi đó còn NOT_RUN. Đó là ghi nhận lịch sử của lượt kiểm chứng local, không phải trạng thái hiện tại.

## Cập nhật ngày 24/10/2026

Deployment và smoke ngày 17/10 đã PASS; batch ngày 24/10 đã xử lý 30 tài liệu và có CSV/ground truth/evaluation thật. Demo mới `20261024-014837-week3-product-demo-3988825a` chạy từ 01:48:38 đến 01:50:51 với 31/31 COMPLETED, bao gồm PDF hai trang. Evaluation `20261024-015102-evaluation-b21f4135` chấm 30 ảnh, hoàn tất lúc 01:51:03 và tái lập cùng các chỉ số: fields 87,5%, line item fields 100%, table cells 100%; precision tương ứng 68,18%, 60%, 60%. Báo cáo hiện tại ở [week3/README.md](week3/README.md). Hash của các file trong deployment, smoke tuần 2, các smoke/evaluation tuần 3 đã đối chiếu đều khớp manifest.

Yêu cầu chức năng sản phẩm có bằng chứng thực thi trên AWS. Preflight của trợ lý trước đó thiếu credentials, sau đó sinh viên đã demo lại thành công trong terminal có credentials; hai sự kiện được phân biệt trong báo cáo. Worklog tuần 3 đã được tổng hợp từ bằng chứng, giờ thực tế mỗi người chưa có nguồn xác nhận; chi phí cuối kỳ, video demo và cleanup còn cần hoàn thiện theo kế hoạch. Không tự End Lab hoặc xóa tài nguyên.
