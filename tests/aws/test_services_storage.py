from types import SimpleNamespace

import boto3
import pytest
from botocore.stub import Stubber

from textract_pipeline.config import Config
from textract_pipeline.models import document_id
from textract_pipeline.aws.services import AwsServices
from textract_pipeline.aws.storage import DynamoStore


@pytest.fixture
def services():
    # Synthetic credentials + Stubber: no network request or real credentials required.
    session = boto3.Session(aws_access_key_id="testing", aws_secret_access_key="testing", region_name="us-east-1")
    return AwsServices(Config("test-table", "test-bucket"), session=session)


def source(kind="form"):
    return {"document_id": "a" * 64, "document_type": kind, "bucket": "test-bucket", "s3_key": "input/forms/a.pdf", "version_id": "v1"}


def test_head_uses_event_version_and_real_size(services):
    with Stubber(services.s3) as stub:
        stub.add_response("head_object", {"ETag": '"etag"', "VersionId": "v1", "ContentLength": 123,
            "Metadata": {"processing-mode": "sync"}}, {"Bucket": "test-bucket", "Key": "input/forms/a.pdf", "VersionId": "v1"})
        value = services.inspect("test-bucket", "input/forms/a.pdf", {"versionId": "v1"})
        assert value["document_id"] == document_id("test-bucket", "input/forms/a.pdf", "v1")
        assert value["size_bytes"] == 123 and value["processing_mode"] == "sync"
        stub.assert_no_pending_responses()


def test_stale_unversioned_event_skipped(services):
    with Stubber(services.s3) as stub:
        stub.add_response("head_object", {"ETag": '"new"', "ContentLength": 123}, {"Bucket": "test-bucket", "Key": "input/forms/a.pdf"})
        assert services.inspect("test-bucket", "input/forms/a.pdf", {"eTag": "old"}) is None


@pytest.mark.parametrize("kind,method", [("form", "start_document_analysis"), ("invoice", "start_expense_analysis")])
def test_start_version_idempotent_token_no_notification_role(services, kind, method):
    metadata = source(kind)
    expected = {"DocumentLocation": {"S3Object": {"Bucket": "test-bucket", "Name": "input/forms/a.pdf", "Version": "v1"}}, "ClientRequestToken": "a" * 64}
    if kind == "form":
        expected["FeatureTypes"] = ["FORMS", "TABLES"]
    with Stubber(services.textract) as stub:
        stub.add_response(method, {"JobId": "job"}, expected)
        assert services.start(metadata) == "job"
        stub.assert_no_pending_responses()


@pytest.mark.parametrize("kind,method", [("form", "analyze_document"), ("invoice", "analyze_expense")])
def test_sync_selects_correct_api(services, kind, method):
    expected = {"Document": {"S3Object": {"Bucket": "test-bucket", "Name": "input/forms/a.pdf", "Version": "v1"}}}
    if kind == "form":
        expected["FeatureTypes"] = ["FORMS", "TABLES"]
    with Stubber(services.textract) as stub:
        stub.add_response(method, {"DocumentMetadata": {"Pages": 1}}, expected)
        assert services.analyze(source(kind))["DocumentMetadata"]["Pages"] == 1


@pytest.mark.parametrize("kind,method", [("form", "get_document_analysis"), ("invoice", "get_expense_analysis")])
def test_async_passes_pagination_token(services, kind, method):
    with Stubber(services.textract) as stub:
        stub.add_response(method, {"JobStatus": "SUCCEEDED"}, {"JobId": "job", "MaxResults": 1000, "NextToken": "next"})
        assert services.get_result({**source(kind), "job_id": "job", "result_next_token": "next"})["JobStatus"] == "SUCCEEDED"


def test_storage_real_sdk_update_owner_condition(services):
    store = DynamoStore(services.table, services.config)
    with Stubber(services.table.meta.client) as stub:
        from botocore.stub import ANY
        stub.add_response("update_item", {"Attributes": {"PK": {"S": "DOC#id"}, "SK": {"S": "META"}, "status": {"S": "SUBMITTED"}}}, {
            "TableName": "test-table", "Key": {"PK": "DOC#id", "SK": "META"}, "UpdateExpression": "SET #n0=:v0, #n1=:v1",
            "ConditionExpression": "lease_owner=:owner", "ExpressionAttributeNames": {"#n0": "status", "#n1": "updated_at"},
            "ExpressionAttributeValues": {":v0": "SUBMITTED", ":v1": ANY, ":owner": "owner"}, "ReturnValues": "ALL_NEW"})
        assert store.update({"document_id": "id"}, "owner", {"status": "SUBMITTED"})["status"] == "SUBMITTED"


def test_scan_and_document_query_paginate():
    class Pages:
        def __init__(self):
            self.calls = []
        def scan(self, **kwargs):
            self.calls.append(kwargs.copy())
            return {"Items": [{"SK": "first"}], "LastEvaluatedKey": {"PK": "a", "SK": "first"}} if len(self.calls) == 1 else {"Items": [{"SK": "second"}]}
        query = scan
    for identity in (None, "docid"):
        table = Pages()
        store = DynamoStore(table, Config("t", "b"))
        assert [item["SK"] for item in store.items(identity)] == ["first", "second"]
        assert table.calls[1]["ExclusiveStartKey"] == {"PK": "a", "SK": "first"}
        assert all(call["ConsistentRead"] for call in table.calls)
        assert ("KeyConditionExpression" in table.calls[0]) == bool(identity)


def test_config_rejects_disallowed_region_and_limits(monkeypatch):
    monkeypatch.setenv("RESULTS_TABLE", "t")
    monkeypatch.setenv("DATA_BUCKET", "b")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    with pytest.raises(ValueError):
        Config.from_env()
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("MAX_PAGES", "101")
    with pytest.raises(ValueError):
        Config.from_env()
