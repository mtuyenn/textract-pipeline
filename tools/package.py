"""Build a quick work ZIP or create a new managed run with its own package."""

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import run_artifacts as runs

ROOT = Path(__file__).resolve().parents[1]


def install_dependencies(stage, requirements):
    subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
        "--only-binary=:all:", "--no-compile", "--target", str(stage),
        "-r", str(requirements)], check=True)


def build(output, source=None, requirements=None):
    source = Path(source) if source else ROOT / "src/textract_pipeline"
    requirements = Path(requirements) if requirements else ROOT / "requirements-lambda.txt"
    with tempfile.TemporaryDirectory(prefix="textract-package-") as directory:
        stage = Path(directory)
        install_dependencies(stage, requirements)
        shutil.copytree(source, stage / "textract_pipeline",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        with runs.atomic_output(output) as temporary:
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
                for file in sorted(stage.rglob("*")):
                    if file.is_file() and "__pycache__" not in file.parts and file.suffix != ".pyc":
                        archive.write(file, file.relative_to(stage).as_posix())
            with zipfile.ZipFile(temporary) as archive:
                if archive.testzip():
                    raise RuntimeError("Package CRC validation failed")


def build_run(directory=None, kind="package"):
    run = runs.Run.create(directory, kind)
    print(f"Run: {run.path}")
    with run.step("lambda_build"):
        # Snapshot build inputs before installing dependencies or producing any ZIP.
        source = run.capture("lambda_source", ROOT / "src/textract_pipeline", "inputs/lambda-source")
        requirements = run.capture("lambda_requirements", ROOT / "requirements-lambda.txt", "inputs/requirements-lambda.txt")
        output = run.output("packages/textract-pipeline.zip")
        build(output, source, requirements)
        run.validate_files()
        # Detect a source edit during build, including dirty/untracked files.
        if runs.file_record(ROOT / "src/textract_pipeline") != runs.file_record(source):
            raise ValueError("Source changed during build")
        if runs.file_record(ROOT / "requirements-lambda.txt") != runs.file_record(requirements):
            raise ValueError("Requirements changed during build")
        run.register("lambda", "packages/textract-pipeline.zip", "packages")
        run.check("lambda_build")
    return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--run-dir", help="Create a new run; an existing directory is refused")
    group.add_argument("--new-run", action="store_true", help="Create a run with a timestamp and random suffix")
    group.add_argument("--output", help="Quick build output; cannot point inside a run")
    parser.add_argument("--kind", choices=["package", "local_verification", "aws_deployment"], default="package")
    args = parser.parse_args()
    if args.run_dir or args.new_run:
        run = build_run(args.run_dir, args.kind)
        output = run.resolve("packages/textract-pipeline.zip")
    else:
        output = runs.workspace_output(args.output or ROOT / "artifacts/packages/textract-pipeline.zip")
        build(output)
    print(f"ZIP: {output}\nBytes: {output.stat().st_size}\nSHA256: {runs.sha256(output)}")


if __name__ == "__main__":
    main()
