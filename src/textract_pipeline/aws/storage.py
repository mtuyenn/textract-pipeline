"""DynamoDB metadata leases + deterministic child records + notification outbox."""

import time

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from ..models import LostLease, TERMINAL, dynamo_value, iso_now


class DynamoStore:
    def __init__(self, table, config, clock=time.time):
        self.table, self.config, self.clock = table, config, clock

    @staticmethod
    def key(document_id):
        return {"PK": f"DOC#{document_id}", "SK": "META"}

    def get(self, document_id):
        return self.table.get_item(Key=self.key(document_id), ConsistentRead=True).get("Item")

    def claim_source(self, source, owner):
        now = int(self.clock())
        existing = self.get(source["document_id"])
        if existing:
            if existing["status"] in TERMINAL or existing.get("job_id"):
                return None
            return self.claim(existing, owner)
        metadata = {**source, **self.key(source["document_id"]), "item_type": "META",
            "status": "PROCESSING", "created_at": iso_now(), "updated_at": iso_now(),
            "lease_owner": owner, "lease_until": now + self.config.lease_seconds,
            "work_pk": "WORK", "due_at": now + self.config.lease_seconds, "error_attempts": 0}
        try:
            self.table.put_item(Item=dynamo_value(metadata), ConditionExpression="attribute_not_exists(PK)")
            return metadata
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return None
            raise

    def claim(self, metadata, owner):
        now = int(self.clock())
        if int(metadata.get("lease_until", 0)) > now:
            return None
        if metadata["status"] in TERMINAL and metadata.get("notification_status") != "PENDING":
            return None
        try:
            response = self.table.update_item(
                Key=self.key(metadata["document_id"]),
                UpdateExpression="SET lease_owner=:owner, lease_until=:lease, due_at=:lease",
                ConditionExpression="#status=:status AND (attribute_not_exists(lease_until) OR lease_until<=:now)",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":owner": owner, ":lease": now + self.config.lease_seconds,
                                           ":status": metadata["status"], ":now": now},
                ReturnValues="ALL_NEW")
            return response["Attributes"]
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return None
            raise

    def update(self, metadata, owner, values, remove=()):
        values = {**values, "updated_at": iso_now()}
        names = {f"#n{i}": name for i, name in enumerate(values)}
        attributes = {f":v{i}": dynamo_value(value) for i, value in enumerate(values.values())}
        attributes[":owner"] = owner
        expression = "SET " + ", ".join(f"#n{i}=:v{i}" for i in range(len(values)))
        if remove:
            for i, name in enumerate(remove):
                names[f"#r{i}"] = name
            expression += " REMOVE " + ", ".join(f"#r{i}" for i in range(len(remove)))
        try:
            return self.table.update_item(Key=self.key(metadata["document_id"]),
                UpdateExpression=expression, ConditionExpression="lease_owner=:owner",
                ExpressionAttributeNames=names, ExpressionAttributeValues=attributes,
                ReturnValues="ALL_NEW")["Attributes"]
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise LostLease(metadata["document_id"]) from exc
            raise

    def defer(self, metadata, owner, values=None, delay=None):
        return self.update(metadata, owner, {**(values or {}), "work_pk": "WORK", "lease_until": 0,
            "due_at": int(self.clock()) + (self.config.poll_seconds if delay is None else delay)})

    def finish(self, metadata, owner, status, values=None):
        notifications = bool(self.config.topic_arn)
        updates = {**(values or {}), "status": status, "completed_at": iso_now(),
                   "notification_status": "PENDING" if notifications else "DISABLED"}
        if notifications:
            # Keep the active lease until immediate delivery or collector recovery.
            updates.update(work_pk="WORK", due_at=int(self.clock()) + self.config.lease_seconds)
        else:
            updates["lease_until"] = 0
        return self.update(metadata, owner, updates, remove=() if notifications else ("work_pk", "due_at"))

    def notified(self, metadata, owner):
        return self.update(metadata, owner, {"notification_status": "DELIVERED", "lease_until": 0},
                           remove=("work_pk", "due_at"))

    def due(self):
        response = self.table.query(IndexName=self.config.work_index,
            KeyConditionExpression=Key("work_pk").eq("WORK") & Key("due_at").lte(int(self.clock())),
            Limit=self.config.max_jobs)
        # One bounded batch per tick. Remaining jobs are picked up next tick.
        return response.get("Items", [])

    def put_children(self, items):
        with self.table.batch_writer(overwrite_by_pkeys=["PK", "SK"]) as batch:
            for item in items:
                batch.put_item(Item=dynamo_value(item))

    def items(self, document_id=None):
        kwargs = {"ConsistentRead": True}
        method = self.table.scan
        if document_id:
            method = self.table.query
            kwargs["KeyConditionExpression"] = Key("PK").eq(f"DOC#{document_id}")
        while True:
            response = method(**kwargs)
            yield from response.get("Items", [])
            if not response.get("LastEvaluatedKey"):
                break
            kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
