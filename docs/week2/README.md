# Tuần 2 — Triển khai và kiểm thử

Báo cáo và bằng chứng cho lượt triển khai pipeline Textract trên AWS Learner Lab, account `535709085695`, Region `us-east-1`.

- Báo cáo tuần 2: `BaoCaoTuan2.docx`
- Worklog nhóm: `../../WORKLOG.md`
- Deployment: `evidence/deployment-manifest.json`, `evidence/deployment.json`
- Smoke test: `evidence/smoke-manifest.json`, `evidence/smoke.json`
- Các CSV Exporter tạo: `evidence/exports/`

Mã xử lý Lambda nằm trong `src/textract_pipeline/`; template hạ tầng là `infra/template.yaml`. Các script đóng gói, kiểm tra ZIP, triển khai và smoke test nằm trong `tools/`.
