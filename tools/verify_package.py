"""Verify a chosen ZIP; update an open owning run or inspect a sealed one read-only."""

import argparse
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

import run_artifacts as runs

ROOT = Path(__file__).resolve().parents[1]


def verify(path, record=lambda name: None):
    with zipfile.ZipFile(path) as archive:
        if archive.testzip():
            raise RuntimeError("ZIP CRC validation failed")
        for item in archive.infolist():
            name = item.orig_filename
            if "\x00" in name or "\\" in name or PureWindowsPath(name).drive or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
                raise RuntimeError("Unsafe ZIP path")
            if name.endswith("WHEEL") and "Root-Is-Purelib: true" not in archive.read(item).decode():
                raise RuntimeError("Non-pure dependency needs a Linux build")
        record("zip_crc")
        with tempfile.TemporaryDirectory(prefix="textract-verify-") as directory:
            archive.extractall(directory)
            common = "import sys; sys.path.insert(0, sys.argv[1]); "
            handlers = common + "from textract_pipeline.handlers import processor, collector, exporter; assert all(callable(m.lambda_handler) for m in (processor, collector, exporter))"
            sdk = common + "import boto3; s=boto3.Session(aws_access_key_id='testing', aws_secret_access_key='testing', region_name='us-east-1'); assert s.client('textract').meta.service_model.operation_model('StartExpenseAnalysis')"
            for name, program in (("handler_imports", handlers), ("textract_sdk_model", sdk)):
                subprocess.run([sys.executable, "-S", "-c", program, directory], check=True, cwd=directory)
                record(name)


def verify_run(run, path=None):
    with run.step("package_verification"):
        record = run.document["packages"].get("lambda")
        if not record:
            raise ValueError("Run has no Lambda package")
        expected = run.resolve(record["path"])
        if path is not None and Path(path).resolve() != expected:
            raise ValueError("Selected package does not belong to this run")
        run.validate_files()
        verify(expected, run.check)
        run.validate_files()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", help="ZIP to verify; defaults to the work ZIP")
    parser.add_argument("--run-dir", help="Record checks in this existing open run")
    args = parser.parse_args()
    path = Path(args.package).resolve() if args.package else None
    run = runs.Run(args.run_dir) if args.run_dir else None
    if run is None and path:
        owner = next((parent for parent in path.parents if (parent / "manifest.json").is_file()), None)
        if owner:
            run = runs.Run(owner)
    if run:
        document = run.read()
        if document["status"] == "RUNNING":
            verify_run(run, path)
        elif args.run_dir:
            raise ValueError("Run is sealed; use --package alone for read-only verification")
        else:
            run.validate_files()
            expected = run.resolve(document["packages"]["lambda"]["path"])
            if path != expected:
                raise ValueError("Selected ZIP is not the run Lambda package")
            verify(path)
    else:
        verify(path or ROOT / "artifacts/packages/textract-pipeline.zip")
    print("PASS: ZIP CRC, handler imports and bundled Textract SDK model")


if __name__ == "__main__":
    main()
