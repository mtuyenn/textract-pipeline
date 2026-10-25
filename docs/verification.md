# Kiểm chứng quản lý artifact — 11/10/2026

Run hiện hành: [`20261011-212257-local-verification-4ffe5e6a`](../artifacts/runs/20261011-212257-local-verification-4ffe5e6a/manifest.json), kind `local_verification`. Chỉ kiểm chứng tại máy; AWS deployment, OCR thật, accuracy và cleanup đều NOT_RUN.

## Kết quả

| Kiểm tra | Kết quả | Bằng chứng/phạm vi |
|---|---|---|
| pytest | 88 passed, 0 failed/errors/skipped | `test-results/pytest.xml`, kết quả được runner đọc lại vào manifest |
| Build Lambda trong run | PASS, 16,661,135 bytes | `packages/textract-pipeline.zip`, build trực tiếp từ source/requirements snapshot |
| Verify đúng ZIP của run | PASS | CRC, giải nén, Python `-S` import 3 handler và load bundled Textract `StartExpenseAnalysis` SDK model; không gọi OCR |
| Source ZIP | PASS | `packages/textract-project-source.zip`; source/requirements khớp đầu vào Lambda, CRC hợp lệ |
| Code Lambda không đổi | PASS, 16 file | So byte source với ZIP Lambda của đợt trước; tools/tests không có trong ZIP Lambda mới |
| compileall | PASS | `src`, `tools`, `tests` |
| cfn-lint | PASS, exit 0 | `infra/template.yaml`; chưa deploy |
| PowerShell AST | PASS | `tools/deploy.ps1`, `tools/cleanup.ps1`; chỉ parse, không thực thi |
| CLI help | PASS, 9 scripts | package/verify/bundle/run/deploy/smoke/evaluate/generator/cleanup; không liên hệ AWS |
| Di chuyển file tuần 1 | PASS, 2 file giữ nguyên SHA256 | `inputs/week1-relocation.json`, hai file smoke test được lưu tại `docs/week1/evidence/` |

SHA256 ZIP Lambda: `ad64c63e50e09345ef6979b73fbb9accac70f0bd750e07f328fa5aced43855aa`.

Manifest ghi hash ZIP source, ZIP Lambda, JUnit, snapshot source/requirements và bằng chứng bổ sung. Lệnh/kết quả kiểm tra bổ sung nằm trong `evidence/local-checks.json`. Các đường dẫn file được quản lý đều tương đối với run; `inputs.*.source` chỉ ghi nguồn gốc, tách khỏi snapshot. Run được đóng PASS sau khi đủ gate và kiểm tra lại toàn bộ hash.

## Hành vi đã được bảo vệ bằng tests

- Tạo trùng run hoặc ghi lại file trong run bị từ chối; run PASS/FAILED không nhận bước ghi mới, hai writer không cùng giữ khóa.
- Build lần hai và ghi đè ZIP làm việc không đổi manifest/package của run lần một; build lỗi giữ ZIP làm việc cũ và ghi manifest FAILED cho run bị lỗi.
- Snapshot đầu vào độc lập với dữ liệu nguồn; chuyển cả thư mục run vẫn kiểm tra hash được.
- Chọn ZIP tùy ý khi verify; phát hiện ZIP bị thay trước import; từ chối đường dẫn ZIP không an toàn, gồm backslash gốc trên Windows.
- Source bundle phát hiện sửa hoặc thêm source sau build; finish phát hiện artifact bị thay và ghi FAILED.
- Deploy nhận đúng package đã verify, upload đường dẫn/hash đó và không rebuild; hash sai dừng trước AWS boundary.
- Smoke đối chiếu hash Lambda trước upload; snapshot package/dataset riêng, lưu thành công hoặc thất bại mà không sửa deployment run.
- Evaluator snapshot CSV/truth, không ghi đè run cũ; 29 tài liệu có dữ liệu và 1 FAILED vẫn dùng denominator 30.
- Cleanup ghi hash backup trước delete; lỗi đọc backup dừng trước delete.

Tests AWS/deploy/cleanup dùng boundaries giả, không chứng minh IAM, deployment, OCR hoặc xóa tài nguyên thực tế. Verify ZIP dùng interpreter/SDK thật nhưng không gửi API tới AWS. PASS của evaluation chỉ nghĩa scoring hoàn tất, không phải đạt ngưỡng accuracy.

## Quy ước hiện hành

Xem [cây thư mục và vòng đời run](structure.md), [lệnh kiểm chứng](guides/testing.md) và [hướng dẫn triển khai](guides/deployment.md). `artifacts/` bị Git bỏ qua; chỉ giữ run cần đối chiếu hoặc bàn giao. File trong `docs/week1/evidence/` là đầu vào smoke test, không tự chứng minh lần chạy AWS thành công.

AWS còn NOT_RUN: quyền session/LabRole, tạo/cập nhật tài nguyên, upload → OCR sync/async → DynamoDB → CSV → email, accuracy 30 tài liệu, billing và cleanup. Code/runtime và IaC không đổi trong đợt quản lý artifact này.
