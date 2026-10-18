"""Deploy the verified package of an open aws_deployment run. Never rebuild it."""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

import run_artifacts as runs

ROOT = Path(__file__).resolve().parents[1]


def aws(arguments, region, json_output=False):
    command = ["aws", *arguments, "--region", region, "--no-cli-pager"]
    if json_output:
        command += ["--output", "json"]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"AWS {arguments[0]} {arguments[1]} failed: {result.stderr.strip() or result.stdout.strip()}")
    return json.loads(result.stdout) if json_output else result.stdout.strip()


def deploy(run, args):
    with run.step("deployment"):
        if run.document["kind"] != "aws_deployment":
            raise ValueError("Deployment requires a run created with --kind aws_deployment")
        package = run.require_package()
        if run.document["checks"].get("source_bundle", {}).get("status") != "PASS":
            raise ValueError("Bundle source into this run before deployment")
        if not shutil.which("aws"):
            raise RuntimeError("Install AWS CLI v2 and configure temporary Learner Lab credentials")
        run.update_environment(region=args.region, stack=args.prefix)
        identity = aws(["sts", "get-caller-identity"], args.region, True)
        account = identity["Account"]
        if account != args.expected_account:
            raise ValueError(f"Wrong account: expected {args.expected_account}, got {account}")
        run.update_environment(account=account)
        role = f"arn:aws:iam::{account}:role/LabRole"
        print(f"Target: account={account} region={args.region} stack={args.prefix} existing role={role}")
        aws(["s3api", "head-bucket", "--bucket", args.artifact_bucket], args.region)
        location = aws(["s3api", "get-bucket-location", "--bucket", args.artifact_bucket], args.region, True)
        if (location.get("LocationConstraint") or "us-east-1") != args.region:
            raise ValueError("Artifact bucket and Lambda code must use the same region")
        stacks = aws(["cloudformation", "describe-stacks"], args.region, True)
        existing = next((s for s in stacks["Stacks"] if s["StackName"] == args.prefix), None)
        if existing and {t["Key"]: t["Value"] for t in existing.get("Tags", [])}.get("Project") != "TextractDocumentDigitization":
            raise ValueError("Refusing to update an unrelated stack")
        template = run.capture("deployment_template", ROOT / "infra/template.yaml", "inputs/template.yaml")
        source = run.resolve(run.document["packages"]["source"]["path"])
        with zipfile.ZipFile(source) as archive:
            if archive.read("textract-pipeline/infra/template.yaml") != template.read_bytes():
                raise ValueError("Template changed since source was bundled")
        aws(["cloudformation", "validate-template", "--template-body", f"file://{template}"], args.region)
        digest = run.document["packages"]["lambda"]["sha256"]
        key = f"artifacts/{args.prefix}/{digest}.zip"
        # Hash before and after upload binds the deployment to the recorded snapshot.
        run.validate_files()
        aws(["s3", "cp", str(package), f"s3://{args.artifact_bucket}/{key}", "--sse", "AES256"], args.region)
        run.validate_files()
        parameters = [f"Prefix={args.prefix}", f"Owner={args.owner}", f"LabRoleArn={role}",
            f"ArtifactBucket={args.artifact_bucket}", f"ArtifactKey={key}",
            f"NotificationEmail={args.email}", f"PollingState={args.polling_state}"]
        aws(["cloudformation", "deploy", "--template-file", str(template), "--stack-name", args.prefix,
            "--parameter-overrides", *parameters, "--tags", "Project=TextractDocumentDigitization",
            f"Owner={args.owner}", "--no-fail-on-empty-changeset"], args.region)
        stack = aws(["cloudformation", "describe-stacks", "--stack-name", args.prefix], args.region, True)["Stacks"][0]
        if stack["StackStatus"] not in {"CREATE_COMPLETE", "UPDATE_COMPLETE"}:
            raise RuntimeError(f"Stack is not complete: {stack['StackStatus']}")
        evidence = {"account": account, "region": args.region, "stack": args.prefix,
            "package_sha256": digest, "artifact_bucket": args.artifact_bucket, "artifact_key": key,
            "stack_status": stack["StackStatus"], "outputs": stack["Outputs"]}
        output = run.output("evidence/deployment.json")
        output.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        run.register("deployment", "evidence/deployment.json")
        run.check("deployment")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--artifact-bucket", required=True)
    parser.add_argument("--region", choices=["us-east-1", "us-west-2"], default="us-east-1")
    parser.add_argument("--prefix", default="textract-full")
    parser.add_argument("--expected-account", default="535709085695")
    parser.add_argument("--owner", default="24110372-24110381")
    parser.add_argument("--email", default="")
    parser.add_argument("--polling-state", choices=["ENABLED", "DISABLED"], default="ENABLED")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,25}", args.prefix) or not re.fullmatch(r"\d{12}", args.expected_account):
        parser.error("Invalid stack prefix or account ID")
    artifact_run = runs.Run(args.run_dir)
    deploy(artifact_run, args)
    artifact_run.finish()
    print(f"Deployment run sealed: {artifact_run.path}")


if __name__ == "__main__":
    main()
