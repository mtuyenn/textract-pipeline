"""Bundle explicit source/data roots, with a snapshot in an open run when requested."""

import argparse
import zipfile
from pathlib import Path

import run_artifacts as runs

ROOT = Path(__file__).resolve().parents[1]


def build(output):
    files = [ROOT / name for name in ("README.md", "pyproject.toml",
        "requirements-lambda.txt", ".gitignore", "AGENTS.md")]
    for directory in ("src/textract_pipeline", "tools", "tests", "infra", "docs", "data"):
        files.extend(file for file in (ROOT / directory).rglob("*") if file.is_file()
                     and "__pycache__" not in file.parts and file.suffix != ".pyc")
    with runs.atomic_output(output) as temporary:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(set(files)):
                if file.is_file():
                    archive.write(file, "textract-pipeline/" + file.relative_to(ROOT).as_posix())
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip():
                raise RuntimeError("Source archive CRC error")


def bundle_run(run):
    with run.step("source_bundle"):
        output = run.output("packages/textract-project-source.zip")
        build(output)
        # The handoff source must contain the exact code and requirements used by the Lambda build.
        with zipfile.ZipFile(output) as archive:
            source = run.resolve(run.document["inputs"]["lambda_source"]["path"])
            prefix = "textract-pipeline/src/textract_pipeline/"
            expected = {file.relative_to(source).as_posix(): file.read_bytes()
                for file in source.rglob("*") if file.is_file()
                and "__pycache__" not in file.parts and file.suffix != ".pyc"}
            actual = {name[len(prefix):]: archive.read(name) for name in archive.namelist()
                if name.startswith(prefix) and not name.endswith("/")}
            if actual != expected:
                raise ValueError("Source bundle differs from the Lambda build inputs")
            requirements = run.resolve(run.document["inputs"]["lambda_requirements"]["path"])
            if archive.read("textract-pipeline/requirements-lambda.txt") != requirements.read_bytes():
                raise ValueError("Source bundle requirements differ from build inputs")
        run.register("source", "packages/textract-project-source.zip", "packages")
        run.check("source_bundle")
        run.check("source_zip_crc")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--run-dir", help="Attach source ZIP to an existing open run")
    group.add_argument("--output", help="Quick work ZIP output")
    args = parser.parse_args()
    if args.run_dir:
        output = bundle_run(runs.Run(args.run_dir))
    else:
        output = runs.workspace_output(args.output or ROOT / "artifacts/packages/textract-project-source.zip")
        build(output)
    print(f"Source archive: {output}\nSHA256: {runs.sha256(output)}")


if __name__ == "__main__":
    main()
