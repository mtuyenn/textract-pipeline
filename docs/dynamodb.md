# Thiết kế DynamoDB

## 1. Key và loại item

Table mới: `textract-full-results`; table tuần 1: `textract-pipeline-results`. Billing PAY_PER_REQUEST, PK/SK đều String. Không dùng invoice number làm PK vì số hóa đơn có thể trùng giữa nhà cung cấp/revisions.

| PK | SK | item_type | Nội dung |
|---|---|---|---|
| DOC#<sha256> | META | META | nguồn, trạng thái, JobId, lease, outbox, số lượng, đường dẫn kết quả |
| DOC#<sha256> | FIELD#000001 | FIELD | field_name, label, value, confidence, page, expense_index nếu invoice |
| DOC#<sha256> | LINE#000001 | LINE_ITEM | expense_index, group_index, line_number, page, fields (list, không flatten mất duplicate) |
| DOC#<sha256> | CELL#00000001 | TABLE_CELL | table_number, page, row/column, spans, merged, value, confidence, title/footer |

Mọi item có document_id, s3_key, document_type. Khi một child quá lớn: giữ item_type + PK/SK + source identity + overflow_key, tải chi tiết từ S3 lúc export. Raw Textract response không nhét nguyên vào một DynamoDB item.

## 2. META ví dụ

```json
{
  "PK": "DOC#<sha256>", "SK": "META", "item_type": "META",
  "document_id": "<sha256>", "document_type": "invoice",
  "bucket": "textract-full-535709085695-us-east-1",
  "s3_key": "input/invoices/invoice-001.png",
  "version_id": "<S3 version>", "source_etag": "<etag>",
  "size_bytes": 35000, "processing_mode": "auto",
  "status": "COMPLETED", "created_at": "<UTC ISO8601>",
  "updated_at": "<UTC ISO8601>", "completed_at": "<UTC ISO8601>",
  "lease_owner": "<Lambda request id>", "lease_until": 0,
  "pages": 1, "counts": {"fields": 8, "line_items": 2, "table_cells": 0},
  "parsed_key": "parsed-results/<sha256>.json.gz",
  "csv_prefix": "output/<sha256>/", "notification_status": "DELIVERED"
}
```

Job đang xử lý thêm work_pk=WORK, due_at (epoch seconds Number), job_id, submitted_at_epoch, raw_chunk_count, raw_bytes, result_next_token, results_ready, partial_result. Terminal đã gửi mail xóa work_pk/due_at để không tiếp tục xuất hiện trong index. Không bật TTL cho due_at: đó là lịch làm việc, không phải thời điểm xóa dữ liệu.

## 3. WorkIndex

GSI `WorkIndex`: partition `work_pk` String, sort `due_at` Number, projection ALL. Đây là sparse index, chỉ item đang cần xử lý hoặc có mail pending nằm trong index. Collector Query `work_pk = WORK AND due_at <= now`, Limit=10. GSI eventually consistent: nhìn thấy job chậm hơn một tick là bình thường. CAS trên bảng chính ngăn hai Collector cùng giành lease.

Với table tuần 1 phải thêm index này trước khi chạy Collector. Chỉ khai báo 4 attributes PK/SK/work_pk/due_at ở schema vì các attribute còn lại là schemaless.

## 4. Truy vấn và consistency

```python
from boto3.dynamodb.conditions import Key

response = table.query(
    KeyConditionExpression=Key("PK").eq("DOC#" + document_id),
    ConsistentRead=True,
)
# Tiếp tục với ExclusiveStartKey nếu response có LastEvaluatedKey.
```

- Một tài liệu: Query partition, đọc META và children; có thể thêm begins_with(SK,"FIELD#") để chỉ lấy fields.
- Một hóa đơn theo source key: ở quy mô lab, lấy metadata qua Scan hoặc dùng ID được trả trong smoke evidence/SNS. Không có GSI invoice_number/vendor/date trong bản này; do đó không hứa Query hiệu quả theo các thuộc tính đó.
- Liệt kê/export nhiều tài liệu: Scan phân trang, chỉ lấy child khi META COMPLETED (hoặc opt-in PARTIAL). Có thể có nhiều revisions cùng source key; CSV giữ document_id để phân biệt. Evaluator chọn revision mới nhất theo created_at.
- Nếu mở rộng tìm theo vendor/date/status: thiết kế access pattern trước rồi bổ sung GSI riêng, không dùng FilterExpression để giả làm index.
- Dùng Decimal khi lưu float confidence vào DDB; JSON/CSV chuyển lại giá trị serializable. ID tiền tố không chứa PII.

## 5. Điều kiện ghi

New META: `attribute_not_exists(PK)`. Claim lease: status vẫn khớp + lease_until hết hạn; update kết quả: `lease_owner=:owner`. Nếu owner đổi, LostLease dừng việc ghi metadata cũ. lease_seconds phải lớn hơn timeout của cả Processor/Collector; mặc định 240 so với 180.

Lifecycle: PROCESSING → SUBMITTED (async) → COMPLETED/PARTIAL/FAILED; lỗi transient → RETRYABLE hoặc giữ SUBMITTED; input không hợp lệ → REJECTED. Notification status độc lập: PENDING → DELIVERED hoặc FAILED, không đổi extraction COMPLETED thành FAILED chỉ vì mail lỗi.
