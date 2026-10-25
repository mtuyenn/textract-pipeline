"""Cleanup only a tagged project stack; default retains S3/DynamoDB.

Backup all S3 object versions and all DynamoDB items BEFORE deletion. This is a
small-lab utility, not a transactional backup service. Stop all uploads first.
"""

import argparse
import json
import time
import run_artifacts as runs

import boto3

from textract_pipeline.models import json_bytes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stack", default="textract-full")
    parser.add_argument("--region", choices=["us-east-1", "us-west-2"], default="us-east-1")
    parser.add_argument("--purge-data", action="store_true")
    parser.add_argument("--run-dir", help="New run directory for backup and evidence")
    args = parser.parse_args()
    artifact_run = runs.Run.create(args.run_dir, "cleanup")
    print(f"Run: {artifact_run.path}")
    with artifact_run.step("cleanup"):
        artifact_run.update_environment(region=args.region, stack=args.stack)
        cleanup(args, artifact_run)
    artifact_run.finish()
    print(f"Cleanup run sealed: {artifact_run.path}")


def cleanup(args, artifact_run):
    session = boto3.Session(region_name=args.region)
    cf, s3 = session.client("cloudformation"), session.client("s3")
    stack = cf.describe_stacks(StackName=args.stack)["Stacks"][0]
    tags = {tag["Key"]: tag["Value"] for tag in stack.get("Tags", [])}
    if tags.get("Project") != "TextractDocumentDigitization":
        raise SystemExit("Refusing cleanup: wrong project tag")
    outputs = {value["OutputKey"]: value["OutputValue"] for value in stack["Outputs"]}
    bucket, table_name = outputs["BucketName"], outputs["TableName"]
    account = session.client("sts").get_caller_identity()["Account"]
    print(f"Account={account} region={args.region} stack={args.stack}\nBucket={bucket}\nTable={table_name}")
    print("Stop uploads and other writers. All object versions/items will be backed up locally.")
    confirmation = input(f"Type exact bucket name {bucket} to continue (anything else cancels): ")
    if confirmation != bucket:
        raise SystemExit("Cancelled")
    resources = cf.list_stack_resources(StackName=args.stack)["StackResourceSummaries"]
    identities = {item.get("PhysicalResourceId") for item in resources}
    if bucket not in identities or table_name not in identities:
        raise SystemExit("Refusing cleanup: output resources do not belong to this stack")
    bucket_tags = s3.get_bucket_tagging(Bucket=bucket)["TagSet"]
    if {tag["Key"]: tag["Value"] for tag in bucket_tags}.get("Project") != tags["Project"]:
        raise SystemExit("Refusing cleanup: wrong bucket tag")
    session.client("events").disable_rule(Name=outputs["PollerName"])
    s3.put_bucket_notification_configuration(Bucket=bucket, NotificationConfiguration={})
    print("Triggers disabled. Waiting 240 seconds for existing Lambda invocations to finish...")
    time.sleep(240)
    backup = artifact_run.output("backup")
    backup.mkdir(parents=True, exist_ok=False)
    (backup / "resources.json").write_bytes(json_bytes({"account": account, "region": args.region, "outputs": outputs}))
    versions, objects_to_delete = [], []
    for page in s3.get_paginator("list_object_versions").paginate(Bucket=bucket):
        for item in page.get("Versions", []):
            # Local filenames are numbered; untrusted S3 keys never become filesystem paths.
            filename = f"s3-version-{len(versions):08d}.bin"
            s3.download_file(bucket, item["Key"], str(backup / filename), ExtraArgs={"VersionId": item["VersionId"]})
            head = s3.head_object(Bucket=bucket, Key=item["Key"], VersionId=item["VersionId"])
            versions.append({"key": item["Key"], "version_id": item["VersionId"], "file": filename,
                             "content_type": head.get("ContentType"), "metadata": head.get("Metadata", {})})
            objects_to_delete.append({"Key": item["Key"], "VersionId": item["VersionId"]})
        for item in page.get("DeleteMarkers", []):
            versions.append({"key": item["Key"], "version_id": item["VersionId"], "delete_marker": True})
            objects_to_delete.append({"Key": item["Key"], "VersionId": item["VersionId"]})
    (backup / "s3-versions.json").write_bytes(json_bytes(versions))
    table = session.resource("dynamodb").Table(table_name)
    items, kwargs = [], {"ConsistentRead": True}
    while True:
        page = table.scan(**kwargs)
        items.extend(page.get("Items", []))
        if not page.get("LastEvaluatedKey"):
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    (backup / "dynamodb-items.json").write_bytes(json_bytes(items))
    artifact_run.register("backup", "backup")
    artifact_run.check("backup")
    artifact_run.validate_files()
    print(f"Backup saved: {backup}. Deleting stack compute/notifications; S3/table retained by template.")
    cf.delete_stack(StackName=args.stack)
    cf.get_waiter("stack_delete_complete").wait(StackName=args.stack)
    if args.purge_data:
        for index in range(0, len(objects_to_delete), 1000):
            response = s3.delete_objects(Bucket=bucket, Delete={"Objects": objects_to_delete[index:index + 1000], "Quiet": True})
            if response.get("Errors"):
                raise RuntimeError(f"S3 version deletion failed: {response['Errors']}")
        s3.delete_bucket(Bucket=bucket)
        table.delete()
        print("Deleted retained bucket versions and table. Recoverable only from local backup; version IDs cannot be preserved on restore.")
    else:
        print("Bucket and table RETAINED (storage charges can continue). Artifact package bucket was not deleted.")

    artifact_run.check("cleanup", purge_data=args.purge_data)


if __name__ == "__main__":
    main()
