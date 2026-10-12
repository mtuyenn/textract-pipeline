"""AWS adapter. Clients are constructed on first invocation, never at import."""

import gzip
import json
import logging

import boto3
from botocore.config import Config as BotoConfig

from ..config import Config
from ..models import InvalidDocument, document_id, json_bytes, route
from .storage import DynamoStore

LOG = logging.getLogger(__name__)


class AwsServices:
    def __init__(self, config, session=None):
        self.config = config
        session = session or boto3.Session(region_name=config.region)
        sdk_config = BotoConfig(retries={"mode": "standard", "max_attempts": 4}, connect_timeout=5, read_timeout=60)
        self.s3 = session.client("s3", config=sdk_config)
        self.textract = session.client("textract", config=sdk_config)
        self.sns = session.client("sns", config=sdk_config)
        self.table = session.resource("dynamodb", config=sdk_config).Table(config.table_name)

    def inspect(self, bucket, key, event_object):
        if bucket != self.config.bucket_name:
            raise InvalidDocument("Unexpected source bucket")
        kind = route(key)
        version = event_object.get("versionId")
        kwargs = {"Bucket": bucket, "Key": key}
        if version:
            kwargs["VersionId"] = version
        head = self.s3.head_object(**kwargs)
        etag = head.get("ETag", "").strip('"')
        expected = event_object.get("eTag", "").strip('"')
        if not version and expected and expected != etag:
            return None  # Late notification for an object that has already been overwritten.
        version = head.get("VersionId") or version
        return {"document_id": document_id(bucket, key, version or etag), "bucket": bucket,
                "s3_key": key, "version_id": version, "source_etag": etag, "document_type": kind,
                "size_bytes": int(head["ContentLength"]), "processing_mode": head.get("Metadata", {}).get("processing-mode", "auto")}

    @staticmethod
    def location(metadata):
        location = {"Bucket": metadata["bucket"], "Name": metadata["s3_key"]}
        if metadata.get("version_id"):
            location["Version"] = metadata["version_id"]
        return location

    def analyze(self, metadata):
        document = {"S3Object": self.location(metadata)}
        if metadata["document_type"] == "invoice":
            return self.textract.analyze_expense(Document=document)
        return self.textract.analyze_document(Document=document, FeatureTypes=["FORMS", "TABLES"])

    def start(self, metadata):
        kwargs = {"DocumentLocation": {"S3Object": self.location(metadata)},
                  "ClientRequestToken": metadata["document_id"]}
        if metadata["document_type"] == "invoice":
            return self.textract.start_expense_analysis(**kwargs)["JobId"]
        return self.textract.start_document_analysis(**kwargs, FeatureTypes=["FORMS", "TABLES"])["JobId"]

    def get_result(self, metadata):
        kwargs = {"JobId": metadata["job_id"], "MaxResults": 1000}
        if metadata.get("result_next_token"):
            kwargs["NextToken"] = metadata["result_next_token"]
        method = self.textract.get_expense_analysis if metadata["document_type"] == "invoice" else self.textract.get_document_analysis
        return method(**kwargs)

    def save_json(self, key, value):
        data = json_bytes(value)
        self.s3.put_object(Bucket=self.config.bucket_name, Key=key, Body=gzip.compress(data),
            ContentType="application/json", ContentEncoding="gzip", ServerSideEncryption="AES256")
        return len(data)

    def load_json(self, key):
        response = self.s3.get_object(Bucket=self.config.bucket_name, Key=key)
        body = response["Body"].read()
        return json.loads(gzip.decompress(body))

    def put_csv(self, key, data):
        self.s3.put_object(Bucket=self.config.bucket_name, Key=key, Body=data,
            ContentType="text/csv; charset=utf-8", ServerSideEncryption="AES256")

    def notify(self, metadata):
        payload = {name: metadata.get(name) for name in
                   ("document_id", "s3_key", "status", "counts", "csv_prefix", "error_code")}
        self.sns.publish(TopicArn=self.config.topic_arn,
            Subject=f"Textract {metadata['status']} {metadata['document_id'][:12]}",
            Message=json_bytes(payload).decode("utf-8"))


_runtime = None


def runtime():
    global _runtime
    if _runtime is None:
        config = Config.from_env()
        services = AwsServices(config)
        _runtime = (services, DynamoStore(services.table, config), config)
        logging.getLogger().setLevel(logging.INFO)
    return _runtime
