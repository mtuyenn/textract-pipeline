"""Artifact behavior tests. AWS/install/import subprocesses are boundaries where stubbed."""

import base64
import csv
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

import run_artifacts as runs
from tools import bundle_source, cleanup_aws, deploy, evaluate, generate_samples, package, smoke_aws, verify_package


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / "project"
    source = root / "src/textract_pipeline"
    source.mkdir(parents=True)
    (source / "__init__.py").write_bytes(b"VALUE = 1\n")
    (root / "requirements-lambda.txt").write_text("")
    (root / "infra").mkdir()
    (root / "infra/template.yaml").write_text("Resources: {}\n")
    for module in (runs, package, bundle_source, deploy):
        monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(runs, "git_state", lambda: {"commit": None, "dirty": True})
    def install(stage, requirements):
        (stage / "dependency.txt").write_text("fixture dependency")
    monkeypatch.setattr(package, "install_dependencies", install)
    return root


def directory(project, name="unit", sequence=0):
    return project / "artifacts/runs" / f"20261011-1430{sequence:02d}-{name}"


def prepared_run(project, kind="package", name="prepared"):
    run = package.build_run(directory(project, name), kind)
    # Downstream unit tests assume the import checks succeeded in a previous stage.
    # The real SDK/import route is verified separately on the actual built ZIP.
    with run.step("package_verification"):
        for check in ("zip_crc", "handler_imports", "textract_sdk_model"):
            run.check(check)
    return run


def test_create_refuses_existing_directory_without_modifying_it(project):
    run = runs.Run.create(directory(project))
    before = run.manifest.read_bytes()
    with pytest.raises(FileExistsError):
        runs.Run.create(run.path)
    assert run.manifest.read_bytes() == before


def test_generated_ids_are_sortable_and_collision_resistant(project):
    first, second = runs.Run.create(), runs.Run.create()
    assert first.path != second.path
    assert first.path.name[:8] == second.path.name[:8]
    assert first.read()["started_at"].endswith("+07:00")


@pytest.mark.parametrize("path", ["../escape", "/absolute", "C:/escape", "C:relative", "a\\b", "manifest.json"])
def test_paths_cannot_escape_or_replace_manifest(project, path):
    run = runs.Run.create(directory(project))
    with pytest.raises(ValueError):
        run.resolve(path)


def test_package_is_inside_run_and_hash_matches_real_zip(project):
    run = package.build_run(directory(project))
    record = run.read()["packages"]["lambda"]
    assert record["path"] == "packages/textract-pipeline.zip"
    path = run.resolve(record["path"])
    assert record["sha256"] == runs.sha256(path)
    with zipfile.ZipFile(path) as archive:
        assert archive.read("textract_pipeline/__init__.py") == b"VALUE = 1\n"
    assert not (project / "artifacts/packages/textract-pipeline.zip").exists()


def test_later_build_and_workspace_overwrite_do_not_change_first_run(project):
    first = package.build_run(directory(project, "first"))
    manifest = first.manifest.read_bytes()
    original = first.resolve("packages/textract-pipeline.zip").read_bytes()
    (project / "src/textract_pipeline/__init__.py").write_text("VALUE = 2\n")
    second = package.build_run(directory(project, "second"))
    workspace = project / "artifacts/packages/textract-pipeline.zip"
    package.build(workspace)
    assert second.resolve("packages/textract-pipeline.zip").read_bytes() != original
    assert workspace.read_bytes() != original
    assert first.manifest.read_bytes() == manifest
    assert first.resolve("packages/textract-pipeline.zip").read_bytes() == original
    first.read()
    first.validate_files()


def test_failed_build_records_failure_and_preserves_previous_work_zip(project, monkeypatch):
    workspace = project / "artifacts/packages/textract-pipeline.zip"
    package.build(workspace)
    before = workspace.read_bytes()
    def fail(*args):
        raise RuntimeError("dependency install failed")
    monkeypatch.setattr(package, "install_dependencies", fail)
    with pytest.raises(RuntimeError):
        package.build(workspace)
    assert workspace.read_bytes() == before
    target = directory(project, "failed")
    with pytest.raises(RuntimeError):
        package.build_run(target)
    document = runs.Run(target).read()
    assert document["status"] == "FAILED"
    assert document["steps"]["lambda_build"]["status"] == "FAILED"
    assert document["packages"] == {}


def test_workspace_output_cannot_bypass_run_ownership(project):
    with pytest.raises(ValueError):
        runs.workspace_output(directory(project) / "packages/a.zip")


def test_finish_requires_real_stage_results_and_seals_run(project):
    run = package.build_run(directory(project))
    with pytest.raises(ValueError, match="Required checks"):
        run.finish()
    assert run.read()["status"] == "RUNNING"
    with run.step("package_verification"):
        for check in ("zip_crc", "handler_imports", "textract_sdk_model"):
            run.check(check)
    run.finish()
    before = run.manifest.read_bytes()
    with pytest.raises(ValueError, match="sealed"):
        with run.step("another"):
            pass
    with pytest.raises(ValueError, match="sealed"):
        run.finish("FAILED")
    assert run.manifest.read_bytes() == before


def test_duplicate_artifact_fails_instead_of_overwriting(project):
    run = runs.Run.create(directory(project))
    with pytest.raises(FileExistsError):
        with run.step("write"):
            run.output("evidence/result.txt").write_text("first")
            run.output("evidence/result.txt")
    assert run.resolve("evidence/result.txt").read_text() == "first"
    assert run.read()["status"] == "FAILED"


def test_lock_refuses_second_writer(project):
    run = runs.Run.create(directory(project))
    with run.step("first"):
        with pytest.raises(FileExistsError):
            with runs.Run(run.path).step("second"):
                pass
        assert (run.path / ".writer.lock").exists()
    assert not (run.path / ".writer.lock").exists()


def test_input_provenance_is_separate_from_portable_output_paths(project):
    source = project / "dataset"
    source.mkdir()
    (source / "truth.json").write_text('{"value":1}')
    run = runs.Run.create(directory(project))
    with run.step("input"):
        snapshot = run.capture("dataset", source, "inputs/dataset", dataset=True)
    (source / "truth.json").write_text('{"value":2}')
    assert (snapshot / "truth.json").read_text() == '{"value":1}'
    doc = run.read()
    assert doc["dataset"]["path"] == "inputs/dataset"
    assert doc["dataset"]["source"] == {"scope": "repository", "path": "dataset"}
    run.validate_files()
    moved = project / "moved-run"
    run.path.rename(moved)
    portable = runs.Run(moved)
    portable.read()
    portable.validate_files()


def test_verify_selected_package_and_persist_checks(project, monkeypatch):
    run = package.build_run(directory(project))
    selected = run.resolve("packages/textract-pipeline.zip")
    seen = []
    def imports(command, **kwargs):
        seen.append(command)
    monkeypatch.setattr(verify_package.subprocess, "run", imports)
    monkeypatch.setattr("sys.argv", ["verify_package.py", "--package", str(selected)])
    verify_package.main()
    assert len(seen) == 2
    assert run.read()["checks"]["handler_imports"]["status"] == "PASS"
    run.finish()
    before = run.manifest.read_bytes()
    verify_package.main()
    assert run.manifest.read_bytes() == before


def test_tampered_package_fails_before_importing_and_is_recorded(project, monkeypatch):
    run = package.build_run(directory(project))
    run.resolve("packages/textract-pipeline.zip").write_bytes(b"different ZIP")
    monkeypatch.setattr(verify_package, "verify", lambda *args: pytest.fail("must check hash first"))
    with pytest.raises(ValueError, match="mismatch"):
        verify_package.verify_run(run)
    assert run.read()["status"] == "FAILED"
    assert "handler_imports" not in run.document["checks"]


@pytest.mark.parametrize("entry", ["../escape.py", "/escape.py", "C:/escape.py", "a\\escape.py"])
def test_verifier_rejects_zip_traversal_before_import(project, entry):
    path = project / "unsafe.zip"
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("placeholder")
        info.filename = entry  # Keep raw backslashes; ZipInfo's Windows constructor normalizes them.
        archive.writestr(info, "unsafe")
    with pytest.raises(RuntimeError, match="Unsafe ZIP"):
        verify_package.verify(path)


@pytest.mark.parametrize("change", ["edit", "add"])
def test_source_bundle_matches_build_and_detects_later_source_edits(project, change):
    run = prepared_run(project)
    output = bundle_source.bundle_run(run)
    with zipfile.ZipFile(output) as archive:
        assert archive.read("textract-pipeline/src/textract_pipeline/__init__.py") == b"VALUE = 1\n"
    other = package.build_run(directory(project, "changed"))
    changed = "__init__.py" if change == "edit" else "extra.py"
    (project / "src/textract_pipeline" / changed).write_text("VALUE = 2\n")
    with pytest.raises(ValueError, match="differs"):
        bundle_source.bundle_run(other)
    assert other.read()["status"] == "FAILED"


def test_finish_detects_changed_artifact_and_records_failure(project):
    run = prepared_run(project)
    run.resolve("packages/textract-pipeline.zip").write_bytes(b"changed")
    with pytest.raises(ValueError, match="mismatch"):
        run.finish()
    assert run.read()["status"] == "FAILED"


def test_generator_cannot_write_into_a_run(project):
    run = runs.Run.create(directory(project))
    with pytest.raises(ValueError, match="workspace output"):
        generate_samples.generate(run.path / "inputs/dataset")
    assert not (run.path / "inputs/dataset").exists()


@pytest.mark.parametrize("backup_fails", [False, True])
def test_cleanup_records_backup_before_delete_and_stops_on_failure(project, monkeypatch, backup_fails):
    run = runs.Run.create(directory(project, "cleanup"), "cleanup")
    calls = []
    def delete_stack(**kwargs):
        # Read the persisted manifest at the actual delete boundary.
        document = json.loads(run.manifest.read_text())
        assert document["checks"]["backup"]["status"] == "PASS"
        assert document["artifacts"]["backup"]["sha256"] == runs.file_record(run.path / "backup")["sha256"]
        calls.append("delete")
    def scan(**kwargs):
        if backup_fails:
            raise RuntimeError("backup read failed")
        return {"Items": [{"PK": "DOC#1", "SK": "META"}]}
    outputs = {"BucketName": "bucket", "TableName": "table", "PollerName": "poller"}
    clients = {
        "cloudformation": SimpleNamespace(
            describe_stacks=lambda **k: {"Stacks": [{"Tags": [{"Key": "Project", "Value": "TextractDocumentDigitization"}], "Outputs": [{"OutputKey": k, "OutputValue": v} for k, v in outputs.items()]}]},
            list_stack_resources=lambda **k: {"StackResourceSummaries": [{"PhysicalResourceId": "bucket"}, {"PhysicalResourceId": "table"}]},
            delete_stack=delete_stack, get_waiter=lambda name: SimpleNamespace(wait=lambda **k: None)),
        "s3": SimpleNamespace(get_bucket_tagging=lambda **k: {"TagSet": [{"Key": "Project", "Value": "TextractDocumentDigitization"}]},
            put_bucket_notification_configuration=lambda **k: None,
            get_paginator=lambda name: SimpleNamespace(paginate=lambda **k: [])),
        "sts": SimpleNamespace(get_caller_identity=lambda: {"Account": "account"}),
        "events": SimpleNamespace(disable_rule=lambda **k: None),
    }
    session = SimpleNamespace(client=lambda name: clients[name], resource=lambda name: SimpleNamespace(Table=lambda name: SimpleNamespace(scan=scan)))
    monkeypatch.setattr(cleanup_aws.boto3, "Session", lambda **k: session)
    monkeypatch.setattr(cleanup_aws.time, "sleep", lambda seconds: None)
    monkeypatch.setattr("builtins.input", lambda prompt: "bucket")
    args = SimpleNamespace(region="us-east-1", stack="stack", purge_data=False)
    if backup_fails:
        with pytest.raises(RuntimeError, match="backup read"):
            with run.step("cleanup"):
                cleanup_aws.cleanup(args, run)
        assert run.read()["status"] == "FAILED"
        assert not calls
    else:
        with run.step("cleanup"):
            cleanup_aws.cleanup(args, run)
        run.finish()
        assert calls == ["delete"]
        assert run.read()["status"] == "PASS"


def deployment_args():
    return SimpleNamespace(region="us-east-1", prefix="textract-full", artifact_bucket="artifact-bucket",
        expected_account="535709085695", owner="team", email="", polling_state="ENABLED")


def test_deploy_uploads_verified_snapshot_and_never_rebuilds(project, monkeypatch):
    run = prepared_run(project, "aws_deployment")
    bundle_source.bundle_run(run)
    expected = run.resolve("packages/textract-pipeline.zip")
    digest = runs.sha256(expected)
    calls = []
    def aws(arguments, region, json_output=False):
        calls.append(arguments)
        if arguments[:2] == ["sts", "get-caller-identity"]:
            return {"Account": "535709085695"}
        if arguments[:2] == ["s3api", "get-bucket-location"]:
            return {"LocationConstraint": None}
        if arguments[:2] == ["cloudformation", "describe-stacks"]:
            return {"Stacks": [] if "--stack-name" not in arguments else [{"StackStatus": "CREATE_COMPLETE", "Outputs": []}]}
        if arguments[:2] == ["s3", "cp"]:
            assert Path(arguments[2]) == expected
            assert runs.sha256(arguments[2]) == digest
            assert digest in arguments[3]
        return ""
    monkeypatch.setattr(deploy, "aws", aws)
    monkeypatch.setattr(deploy.shutil, "which", lambda name: "aws-fixture")
    monkeypatch.setattr(package, "build", lambda *a, **k: pytest.fail("deployment must not rebuild"))
    deploy.deploy(run, deployment_args())
    run.finish()
    assert any(c[:2] == ["s3", "cp"] for c in calls)
    evidence = json.loads(run.resolve("evidence/deployment.json").read_text())
    assert evidence["package_sha256"] == digest


def test_deploy_refuses_changed_package_without_contacting_aws(project, monkeypatch):
    run = prepared_run(project, "aws_deployment")
    bundle_source.bundle_run(run)
    run.resolve("packages/textract-pipeline.zip").write_bytes(b"changed")
    monkeypatch.setattr(deploy, "aws", lambda *a, **k: pytest.fail("must reject before AWS"))
    with pytest.raises(ValueError, match="mismatch"):
        deploy.deploy(run, deployment_args())
    assert run.read()["status"] == "FAILED"


def write_evaluation_inputs(project):
    truth = project / "truth.json"
    truth.write_text(json.dumps({"documents": [{"s3_key": str(i), "fields": [{"field_name": "NAME", "value": "X"}]} for i in range(30)]}))
    exports = project / "exports"
    exports.mkdir()
    datasets = {
        "documents": (["document_id", "s3_key", "status"], [{"document_id": str(i), "s3_key": str(i), "status": "COMPLETED" if i < 29 else "FAILED"} for i in range(30)]),
        "fields": (["document_id", "field_name", "value"], [{"document_id": str(i), "field_name": "NAME", "value": "X"} for i in range(29)]),
        "line_items": (["document_id", "fields"], []), "table_cells": (["document_id", "value"], []),
    }
    for name, (headers, rows) in datasets.items():
        with (exports / f"{name}.csv").open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
    return truth, exports


def test_evaluation_snapshots_inputs_and_seals_without_hiding_failed_docs(project):
    truth, exports = write_evaluation_inputs(project)
    path = directory(project, "evaluation")
    run, report = evaluate.evaluation_run(truth, exports, path)
    assert report["metrics"]["fields"]["correct"] == 29
    assert report["metrics"]["fields"]["expected"] == 30
    assert run.read()["status"] == "PASS"
    before = run.manifest.read_bytes()
    with pytest.raises(FileExistsError):
        evaluate.evaluation_run(truth, exports, path)
    assert run.manifest.read_bytes() == before
    (exports / "fields.csv").write_text("changed")
    run.validate_files()


def test_evaluation_failure_has_a_failed_manifest(project):
    target = directory(project, "bad-evaluation")
    with pytest.raises(FileNotFoundError):
        evaluate.evaluation_run(project / "missing.json", project / "missing-exports", target)
    assert runs.Run(target).read()["status"] == "FAILED"


def test_smoke_rejects_deployed_code_drift_before_upload(project, monkeypatch):
    class Session:
        def client(self, name):
            if name == "cloudformation":
                return SimpleNamespace(describe_stacks=lambda **k: {"Stacks": [{"Tags": [{"Key": "Project", "Value": "TextractDocumentDigitization"}],
                    "Outputs": [{"OutputKey": k, "OutputValue": v} for k, v in {"BucketName": "b", "TableName": "t", "ProcessorName": "p", "CollectorName": "c", "ExporterName": "e"}.items()]}]})
            if name == "sts":
                return SimpleNamespace(get_caller_identity=lambda: {"Account": "account"})
            if name == "lambda":
                return SimpleNamespace(get_function_configuration=lambda **k: {"CodeSha256": base64.b64encode(b"different").decode()})
            return SimpleNamespace(put_object=lambda **k: pytest.fail("no upload before code check"))
    monkeypatch.setattr(smoke_aws.boto3, "Session", lambda **k: Session())
    args = SimpleNamespace(region="us-east-1", stack="s", expected_account="account", expected_code_sha256="expected", package_sha256="digest")
    with pytest.raises(RuntimeError, match="drift"):
        smoke_aws.run(args, {})


@pytest.mark.parametrize("smoke_fails", [False, True])
def test_smoke_owns_snapshot_and_seals_success_or_failure(project, monkeypatch, smoke_fails):
    deployment = prepared_run(project, "aws_deployment")
    bundle_source.bundle_run(deployment)
    with deployment.step("deployment"):
        deployment.update_environment(region="us-east-1", stack="stack", account="account")
        deployment.check("deployment")
    deployment.finish()
    before = deployment.manifest.read_bytes()
    dataset = project / "dataset"
    dataset.mkdir()
    (dataset / "ground_truth.json").write_text('{"documents":[]}')
    def smoke(args, evidence):
        assert args.expected_account == "account"
        assert args.package_sha256 == deployment.document["packages"]["lambda"]["sha256"]
        assert Path(args.samples).is_relative_to(Path(args.run_dir))
        if smoke_fails:
            raise RuntimeError("AWS boundary failed")
        output = Path(args.run_dir) / "exports"
        output.mkdir()
        (output / "documents.csv").write_text("fixture CSV")
    monkeypatch.setattr(smoke_aws, "run", smoke)
    target = directory(project, "smoke")
    args = SimpleNamespace(run_dir=target, deployment_run=deployment.path, samples=dataset,
        region="us-east-1", stack="stack")
    if smoke_fails:
        with pytest.raises(RuntimeError, match="AWS boundary"):
            smoke_aws.smoke_run(args)
    else:
        smoke_aws.smoke_run(args)
    run = runs.Run(target)
    document = run.read()
    assert document["status"] == ("FAILED" if smoke_fails else "PASS")
    evidence = json.loads(run.resolve("smoke.json").read_text())
    assert evidence["result"] == ("FAILED" if smoke_fails else "PASSED_CORE_SMOKE")
    assert deployment.manifest.read_bytes() == before
    assert run.resolve(document["packages"]["lambda"]["path"]).read_bytes() == deployment.resolve("packages/textract-pipeline.zip").read_bytes()
    (dataset / "ground_truth.json").write_text("changed")
    run.validate_files()
