"""In-memory AWS boundaries only. Production state transitions/parsers run unchanged."""

import copy
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

from textract_pipeline.config import Config
from textract_pipeline.aws.storage import DynamoStore


def client_error(code="ThrottlingException"):
    return ClientError({"Error": {"Code": code, "Message": "synthetic error"}}, "SyntheticOperation")


class MemoryTable:
    def __init__(self):
        self.data = {}

    def get_item(self, Key, **kwargs):
        value = self.data.get((Key["PK"], Key["SK"]))
        return {"Item": copy.deepcopy(value)} if value else {}

    def put_item(self, Item, **kwargs):
        identity = (Item["PK"], Item["SK"])
        if kwargs.get("ConditionExpression") and identity in self.data:
            raise client_error("ConditionalCheckFailedException")
        self.data[identity] = copy.deepcopy(Item)

    def update_item(self, Key, UpdateExpression, ConditionExpression, ExpressionAttributeValues,
                    ExpressionAttributeNames=None, **kwargs):
        item = self.data[(Key["PK"], Key["SK"])]
        values, names = ExpressionAttributeValues, ExpressionAttributeNames or {}
        if ConditionExpression == "lease_owner=:owner":
            accepted = item["lease_owner"] == values[":owner"]
        else:
            accepted = item["status"] == values[":status"] and item.get("lease_until", 0) <= values[":now"]
        if not accepted:
            raise client_error("ConditionalCheckFailedException")
        assignments, _, removed = UpdateExpression.removeprefix("SET ").partition(" REMOVE ")
        for assignment in assignments.split(", "):
            key, value = assignment.split("=")
            item[names.get(key, key)] = copy.deepcopy(values[value])
        for key in removed.split(", ") if removed else []:
            item.pop(names.get(key, key), None)
        return {"Attributes": copy.deepcopy(item)}

    def batch_writer(self, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeServices:
    def __init__(self, config):
        self.config = config
        self.jsons, self.csvs = {}, {}
        self.calls, self.notifications = [], []
        self.analyze_response = {"DocumentMetadata": {"Pages": 1}, "Blocks": []}
        self.responses = []
        self.notify_error = None
        self.csv_error = None
        self.analysis_error = None

    def inspect(self, bucket, key, obj):
        from textract_pipeline.models import document_id, route
        revision = obj.get("versionId") or obj.get("eTag", "etag")
        return {"document_id": document_id(bucket, key, revision), "bucket": bucket, "s3_key": key,
                "document_type": route(key), "size_bytes": 100, "processing_mode": "auto"}

    def analyze(self, metadata):
        self.calls.append("analyze")
        if self.analysis_error:
            raise self.analysis_error
        return copy.deepcopy(self.analyze_response)

    def start(self, metadata):
        self.calls.append("start")
        return "job-synthetic"

    def get_result(self, metadata):
        self.calls.append(("get", metadata.get("result_next_token")))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def save_json(self, key, data):
        from textract_pipeline.models import json_bytes
        self.jsons[key] = copy.deepcopy(data)
        return len(json_bytes(data))

    def load_json(self, key):
        return copy.deepcopy(self.jsons[key])

    def put_csv(self, key, data):
        if self.csv_error:
            error, self.csv_error = self.csv_error, None
            raise error
        self.csvs[key] = data

    def notify(self, metadata):
        if self.notify_error:
            raise self.notify_error
        self.notifications.append(copy.deepcopy(metadata))


@pytest.fixture
def setup():
    config = Config("test-table", "test-bucket", "arn:aws:sns:us-east-1:123456789012:test")
    clock = [1000]
    table = MemoryTable()
    store = DynamoStore(table, config, clock=lambda: clock[0])
    # Query filtering itself is tested separately with the SDK stub; this boundary supplies due candidates.
    store.due = lambda: [copy.deepcopy(item) for item in table.data.values()
                        if item.get("work_pk") == "WORK" and item["due_at"] <= clock[0]]
    store.items = lambda document_id=None: (copy.deepcopy(item) for item in list(table.data.values())
                        if not document_id or item["document_id"] == document_id)
    context = SimpleNamespace(aws_request_id="owner-1", get_remaining_time_in_millis=lambda: 180000)
    return SimpleNamespace(config=config, clock=clock, table=table, store=store, services=FakeServices(config), context=context)


@pytest.fixture
def form_response():
    return {"DocumentMetadata": {"Pages": 1}, "Blocks": [
        {"Id": "k", "BlockType": "KEY_VALUE_SET", "EntityTypes": ["KEY"], "Confidence": 99,
         "Relationships": [{"Type": "CHILD", "Ids": ["kw"]}, {"Type": "VALUE", "Ids": ["v"]}]},
        {"Id": "kw", "BlockType": "WORD", "Text": "NAME:"},
        {"Id": "v", "BlockType": "KEY_VALUE_SET", "EntityTypes": ["VALUE"], "Confidence": 97,
         "Relationships": [{"Type": "CHILD", "Ids": ["vw", "sel"]}]},
        {"Id": "vw", "BlockType": "WORD", "Text": "SYNTHETIC"},
        {"Id": "sel", "BlockType": "SELECTION_ELEMENT", "SelectionStatus": "SELECTED"},
        {"Id": "table", "BlockType": "TABLE", "Page": 1,
         "Relationships": [{"Type": "CHILD", "Ids": ["cell"]}, {"Type": "MERGED_CELL", "Ids": ["merge"]}]},
        {"Id": "cell", "BlockType": "CELL", "RowIndex": 1, "ColumnIndex": 1,
         "Relationships": [{"Type": "CHILD", "Ids": ["vw"]}]},
        {"Id": "merge", "BlockType": "MERGED_CELL", "RowIndex": 1, "ColumnIndex": 1, "ColumnSpan": 2,
         "Relationships": [{"Type": "CHILD", "Ids": ["cell"]}]},
    ]}
