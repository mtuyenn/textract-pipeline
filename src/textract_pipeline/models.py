import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import Decimal


TERMINAL = {"COMPLETED", "PARTIAL", "FAILED", "REJECTED"}
TRANSIENT_CODES = {
    "ThrottlingException", "ProvisionedThroughputExceededException", "LimitExceededException",
    "InternalServerError", "InternalServerErrorException", "ServiceUnavailable",
    "RequestTimeout", "SlowDown", "RequestTimeoutException",
}


class InvalidDocument(ValueError):
    pass


class LostLease(RuntimeError):
    pass


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, default=lambda v: float(v) if isinstance(v, Decimal) else str(v), separators=(",", ":")).encode("utf-8")


def dynamo_value(value):
    # boto3's DynamoDB serializer rejects native float, including nested values.
    return json.loads(json_bytes(value), parse_float=Decimal)


def iso_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def document_id(bucket, key, revision):
    return hashlib.sha256(json_bytes([bucket, key, revision])).hexdigest()


def field_name(text):
    return re.sub(r"\s+", " ", text.strip().rstrip(":")).strip()


def route(key):
    if key.startswith("input/invoices/"):
        return "invoice"
    if key.startswith("input/forms/"):
        return "form"
    raise InvalidDocument("Use input/invoices/ or input/forms/")


def retryable(exc):
    response = getattr(exc, "response", {})
    code = response.get("Error", {}).get("Code", "")
    return code in TRANSIENT_CODES or isinstance(exc, (TimeoutError, ConnectionError)) or type(exc).__name__ in {
        "EndpointConnectionError", "ConnectTimeoutError", "ReadTimeoutError", "ConnectionClosedError",
    }


def safe_error(exc):
    # Do not persist SDK error messages that could contain document values.
    return getattr(exc, "response", {}).get("Error", {}).get("Code", type(exc).__name__)
