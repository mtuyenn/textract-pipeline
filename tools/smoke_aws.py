"""Real AWS acceptance runner. Requires an ACTIVE lab and temporary credentials.

Does not provision resources. Writes synthetic uploads, invokes Collector/Exporter,
downloads real CSV and stores an evidence JSON (including failures).
"""

import argparse
import base64
import json
import time
from pathlib import Path
import shutil

import run_artifacts as runs

import boto3

from textract_pipeline.models import document_id


def invoke(client, name, payload):
    response = client.invoke(FunctionName=name, InvocationType="RequestResponse",
                             Payload=json.dumps(payload).encode())
    result = json.loads(response["Payload"].read())
    if response.get("FunctionError"):
        raise RuntimeError(f"{name}: {result}")
    return result


def run(args, evidence):
    session = boto3.Session(region_name=args.region)
    cf = session.client("cloudformation")
    stack = cf.describe_stacks(StackName=args.stack)["Stacks"][0]
    if {tag["Key"]: tag["Value"] for tag in stack.get("Tags", [])}.get("Project") != "TextractDocumentDigitization":
        raise RuntimeError("Stack is not tagged as this project")
    outputs = {item["OutputKey"]: item["OutputValue"] for item in stack["Outputs"]}
    bucket, table_name = outputs["BucketName"], outputs["TableName"]
    evidence["account"] = session.client("sts").get_caller_identity()["Account"]
    if evidence["account"] != args.expected_account:
        raise RuntimeError("Smoke account differs from the recorded deployment")
    evidence["resources"] = outputs
    s3, functions = session.client("s3"), session.client("lambda")
    for name in ("ProcessorName", "CollectorName", "ExporterName"):
        actual = functions.get_function_configuration(FunctionName=outputs[name])["CodeSha256"]
        if actual != args.expected_code_sha256:
            raise RuntimeError(f"Deployed code drift detected: {outputs[name]}")
    evidence["package_sha256"] = args.package_sha256
    table = session.resource("dynamodb").Table(table_name)
    directory = Path(args.samples)
    manifest = json.loads((directory / "ground_truth.json").read_text(encoding="utf-8"))
    documents = manifest["documents"] if args.all else manifest["documents"][:2]
    uploads = []
    for document in documents:
        key = document["s3_key"]
        response = s3.put_object(Bucket=bucket, Key=key, Body=(directory / key).read_bytes(),
                                 ContentType="image/png", ServerSideEncryption="AES256")
        revision = response.get("VersionId") or response["ETag"].strip('"')
        uploads.append({"key": key, "document_id": document_id(bucket, key, revision),
                        "version_id": response.get("VersionId"), "etag": response["ETag"].strip('"')})
    if not args.no_pdf:
        demo = manifest["async_demo"]
        key = demo["s3_key"]
        response = s3.put_object(Bucket=bucket, Key=key, Body=(directory / demo["local_path"]).read_bytes(),
                                 ContentType="application/pdf", ServerSideEncryption="AES256")
        uploads.append({"key": key, "document_id": document_id(bucket, key, response.get("VersionId") or response["ETag"].strip('"'))})
    evidence["uploads"] = uploads
    deadline = time.monotonic() + args.timeout
    states = {}
    while time.monotonic() < deadline:
        for upload in uploads:
            item = table.get_item(Key={"PK": f"DOC#{upload['document_id']}", "SK": "META"}, ConsistentRead=True).get("Item", {})
            states[upload["document_id"]] = item.get("status", "NOT_SEEN")
        if all(status in {"COMPLETED", "PARTIAL", "FAILED", "REJECTED"} for status in states.values()):
            break
        # Also works with PollingState=DISABLED. Leases prevent collision with scheduled polls.
        invoke(functions, outputs["CollectorName"], {})
        print(json.dumps(states))
        time.sleep(10)
    evidence["states"] = states
    if any(status != "COMPLETED" for status in states.values()):
        raise RuntimeError("Not every uploaded document reached COMPLETED; see states and CloudWatch")
    first = uploads[0]
    event_object = {"key": first["key"], "eTag": first["etag"]}
    if first.get("version_id"):
        event_object["versionId"] = first["version_id"]
    duplicate = invoke(functions, outputs["ProcessorName"], {"Records": [{"eventSource": "aws:s3",
        "eventName": "ObjectCreated:Put", "s3": {"bucket": {"name": bucket}, "object": event_object}}]})
    evidence["duplicate"] = duplicate
    if duplicate["results"][0]["status"] != "DUPLICATE_OR_IN_PROGRESS":
        raise RuntimeError("Duplicate event was not suppressed")
    exported = invoke(functions, outputs["ExporterName"], {"dataset": "all"})
    evidence["export"] = exported
    export_dir = Path(args.run_dir) / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    for name in exported["exports"]:
        s3.download_file(bucket, f"output/exports/{name}.csv", str(export_dir / f"{name}.csv"))
    configuration = s3.get_bucket_notification_configuration(Bucket=bucket)
    target = next(item for item in configuration.get("LambdaFunctionConfigurations", [])
                  if item["LambdaFunctionArn"].endswith(":" + outputs["ProcessorName"]))
    filters = target.get("Filter", {}).get("Key", {}).get("FilterRules", [])
    if not any(item["Name"].lower() == "prefix" and item["Value"] == "input/" for item in filters):
        raise RuntimeError("S3 event prefix must be input/ to exclude output/")
    evidence["output_filter_configuration"] = target
    evidence["email_receipt"] = "MANUAL_CHECK_REQUIRED"
    evidence["output_negative_invocation_test"] = "MANUAL_CHECK_REQUIRED; configuration verified only"


def smoke_run(args):
    artifact_run = runs.Run.create(args.run_dir, "aws_smoke")
    print(f"Run: {artifact_run.path}")
    evidence = {"started_at": runs.now(), "region": args.region, "result": "FAILED"}
    with artifact_run.step("core_smoke"):
        try:
            deployment = runs.Run(args.deployment_run)
            document = deployment.read()
            if document["kind"] != "aws_deployment" or document["status"] != "PASS":
                raise ValueError("Use a completed aws_deployment run")
            if document["environment"]["stack"] != args.stack or document["environment"]["region"] != args.region:
                raise ValueError("Smoke target differs from the recorded deployment")
            deployment.require_package()
            artifact_run.capture("deployment_manifest", deployment.manifest, "inputs/deployment-manifest.json")
            for name, record in document["packages"].items():
                target = artifact_run.output(record["path"])
                shutil.copyfile(deployment.resolve(record["path"]), target)
                copied = artifact_run.register(name, record["path"], "packages")
                if copied["sha256"] != record["sha256"]:
                    raise ValueError("Deployment package changed during snapshot")
            dataset = artifact_run.capture("dataset", args.samples, "inputs/dataset", dataset=True)
            args.samples = str(dataset)
            args.run_dir = str(artifact_run.path)
            args.package_sha256 = artifact_run.document["packages"]["lambda"]["sha256"]
            args.expected_account = document["environment"]["account"]
            args.expected_code_sha256 = base64.b64encode(bytes.fromhex(args.package_sha256)).decode()
            artifact_run.update_environment(region=args.region, stack=args.stack)
            run(args, evidence)
            artifact_run.register("exports", "exports")
            artifact_run.check("core_smoke")
            artifact_run.check("email_receipt", "NOT_RUN", reason="Manual observation required")
            artifact_run.check("output_negative_invocation", "NOT_RUN", reason="Manual observation required")
            evidence["result"] = "PASSED_CORE_SMOKE"
        except BaseException as exc:
            evidence["error"] = str(exc)
            raise
        finally:
            output = artifact_run.output("smoke.json")
            output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            artifact_run.register("smoke", "smoke.json")
    artifact_run.finish()
    return artifact_run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stack", default="textract-full")
    parser.add_argument("--region", choices=["us-east-1", "us-west-2"], default="us-east-1")
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--samples", default=str(root / "data/samples/baseline-v1"))
    parser.add_argument("--run-dir", help="New run directory; timestamp ID generated by default")
    parser.add_argument("--deployment-run", required=True, help="Completed deployment run whose code hashes must match AWS")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--all", action="store_true", help="Upload all >=30 ground-truth documents")
    parser.add_argument("--no-pdf", action="store_true")
    args = parser.parse_args()
    artifact_run = smoke_run(args)
    print(f"Core smoke run sealed: {artifact_run.path}; email/output isolation still need manual checks")


if __name__ == "__main__":
    main()
