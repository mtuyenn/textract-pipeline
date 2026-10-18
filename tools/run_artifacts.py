"""Shared artifact lifecycle. Run outputs are relative, hashed, and sealed on finish.

Tools are executable scripts in this directory; pytest adds tools to pythonpath.
Locks serialize writers. A killed process leaves RUNNING and/or a lock, never PASS.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys
import tempfile
from uuid import uuid4
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LOCAL_TIME = timezone(timedelta(hours=7))
REQUIRED = {
    "package": {"lambda_build", "zip_crc", "handler_imports", "textract_sdk_model"},
    "local_verification": {"lambda_build", "zip_crc", "handler_imports", "textract_sdk_model", "source_bundle", "source_zip_crc", "pytest"},
    "aws_deployment": {"lambda_build", "zip_crc", "handler_imports", "textract_sdk_model", "source_bundle", "source_zip_crc", "deployment"},
    "aws_smoke": {"core_smoke"},
    "evaluation": {"evaluation"},
    "cleanup": {"backup", "cleanup"},
}


def now():
    return datetime.now(LOCAL_TIME).isoformat(timespec="seconds")


def run_id(kind):
    purpose = kind.replace("_", "-")
    return datetime.now(LOCAL_TIME).strftime("%Y%m%d-%H%M%S-") + purpose + "-" + uuid4().hex[:8]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path):
    path = Path(path)
    if path.is_file():
        return {"kind": "file", "bytes": path.stat().st_size, "sha256": sha256(path)}
    if not path.is_dir():
        raise FileNotFoundError(path)
    entries = []
    size = 0
    for child in sorted(path.rglob("*")):
        if "__pycache__" in child.relative_to(path).parts or child.suffix == ".pyc":
            continue
        if child.is_symlink():
            raise ValueError(f"Dataset symlinks are not supported: {child}")
        if child.is_file():
            record = file_record(child)
            entries.append([child.relative_to(path).as_posix(), record["bytes"], record["sha256"]])
            size += record["bytes"]
    encoded = json.dumps(entries, separators=(",", ":")).encode()
    return {"kind": "directory", "bytes": size, "files": len(entries), "sha256": hashlib.sha256(encoded).hexdigest()}


def provenance(path):
    path = Path(path).resolve()
    if path.is_relative_to(ROOT):
        return {"scope": "repository", "path": path.relative_to(ROOT).as_posix()}
    return {"scope": "external", "path": str(path)}


def git_state():
    def git(*args):
        try:
            result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
            return result.stdout.strip() if result.returncode == 0 else None
        except OSError:
            return None
    commit = git("rev-parse", "HEAD")
    dirty = git("status", "--porcelain")
    return {"commit": commit, "dirty": None if dirty is None else bool(dirty)}


def workspace_output(path):
    """Quick builds may overwrite work files, never files inside a managed run."""
    path = Path(path).resolve()
    if path.is_relative_to(ROOT / "artifacts/runs") or any((p / "manifest.json").is_file() for p in path.parents):
        raise ValueError("Use --run-dir to write run artifacts; workspace output cannot target a run")
    return path


@contextmanager
def atomic_output(path):
    """Publish only a finished file; a failed quick build preserves the previous file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".building-", suffix=path.suffix, dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        yield temporary
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Run:
    def __init__(self, directory):
        self.path = Path(directory).resolve()
        self.manifest = self.path / "manifest.json"
        self.document = None
        self.writing = False

    @classmethod
    def create(cls, directory=None, kind="package"):
        if kind not in REQUIRED:
            raise ValueError(f"Unknown run kind: {kind}")
        directory = Path(directory) if directory else ROOT / "artifacts/runs" / run_id(kind)
        if not re.fullmatch(r"\d{8}-\d{6}-[a-z0-9]+(?:-[a-z0-9]+)*", directory.name):
            raise ValueError("Run-id must be YYYYMMDD-HHMMSS-purpose[-suffix]")
        run = cls(directory)
        run.path.mkdir(parents=True, exist_ok=False)
        run.document = {"schema_version": 1, "run_id": run.path.name, "kind": kind,
            "started_at": now(), "finished_at": None, "status": "RUNNING", "git": git_state(),
            "environment": {"python": sys.version.split()[0], "region": None, "stack": None},
            "dataset": None, "inputs": {}, "packages": {}, "artifacts": {}, "checks": {}, "steps": {}}
        run._save()
        return run

    def read(self):
        self.document = json.loads(self.manifest.read_text(encoding="utf-8"))
        if self.document.get("schema_version") != 1 or self.document.get("kind") not in REQUIRED:
            raise ValueError("Unsupported manifest; historical runs are read-only and must not be relabeled")
        return self.document

    def _save(self):
        with atomic_output(self.manifest) as temporary:
            temporary.write_text(json.dumps(self.document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @contextmanager
    def _lock(self):
        lock = self.path / ".writer.lock"
        with lock.open("x", encoding="utf-8") as stream:
            stream.write(str(os.getpid()))
        try:
            self.read()
            if self.document["status"] != "RUNNING":
                raise ValueError("Run is sealed; create a new run")
            self.writing = True
            yield
        finally:
            self.writing = False
            lock.unlink()

    def _assert_writing(self):
        if not self.writing:
            raise RuntimeError("Artifact writes require an active run step")

    def update_environment(self, **values):
        """Record AWS target details while a run step owns the manifest lock."""
        self._assert_writing()
        allowed = {"region", "stack", "account"}
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"Unsupported environment fields: {sorted(unknown)}")
        self.document["environment"].update(values)
        self._save()

    @contextmanager
    def step(self, name):
        with self._lock():
            if name in self.document["steps"]:
                raise ValueError(f"Step already exists: {name}; create a new run to retry")
            self.document["steps"][name] = {"status": "RUNNING", "started_at": now()}
            self._save()
            try:
                yield self
                self.document["steps"][name].update(status="PASS", finished_at=now())
                self._save()
            except BaseException as exc:
                self.document["steps"][name].update(status="FAILED", finished_at=now(), error=str(exc))
                self.document.update(status="FAILED", finished_at=now())
                self._save()
                raise

    def resolve(self, relative):
        relative = str(relative)
        if not relative or "\\" in relative or PureWindowsPath(relative).drive:
            raise ValueError("Artifact path must be a relative POSIX path")
        path = Path(relative)
        target = (self.path / path).resolve()
        if path.is_absolute() or ".." in path.parts or target == self.path or not target.is_relative_to(self.path):
            raise ValueError("Artifact path escapes its run")
        if path.parts[0] in {"manifest.json", ".writer.lock"}:
            raise ValueError("Reserved run path")
        return target

    def output(self, relative):
        self._assert_writing()
        path = self.resolve(relative)
        if path.exists():
            raise FileExistsError(f"Run artifacts cannot be overwritten: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def register(self, name, relative, section="artifacts"):
        self._assert_writing()
        if section not in {"packages", "artifacts"}:
            raise ValueError(section)
        if name in self.document[section]:
            raise ValueError(f"Artifact already registered: {name}")
        record = {"path": self.resolve(relative).relative_to(self.path).as_posix(), **file_record(self.resolve(relative))}
        self.document[section][name] = record
        self._save()
        return record

    def capture(self, name, source, relative, dataset=False):
        self._assert_writing()
        if name in self.document["inputs"]:
            raise ValueError(f"Input already captured: {name}")
        source = Path(source).resolve()
        before = file_record(source)
        target = self.output(relative)
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copyfile(source, target)
        if file_record(source) != before or file_record(target) != before:
            raise ValueError("Input changed during snapshot")
        record = {"path": target.relative_to(self.path).as_posix(), **before, "source": provenance(source)}
        self.document["inputs"][name] = record
        if dataset:
            self.document["dataset"] = {"name": source.name, **record}
        self._save()
        return target

    def check(self, name, status="PASS", **details):
        self._assert_writing()
        if status not in {"PASS", "FAILED", "NOT_RUN"}:
            raise ValueError(status)
        value = {"status": status, **details}
        if name in self.document["checks"] and self.document["checks"][name] != value:
            raise ValueError(f"Cannot replace check result: {name}")
        self.document["checks"][name] = value
        self._save()

    def validate_files(self):
        for section in ("packages", "artifacts", "inputs"):
            for name, record in self.document[section].items():
                actual = file_record(self.resolve(record["path"]))
                if any(record.get(key) != value for key, value in actual.items()):
                    raise ValueError(f"Artifact hash/size mismatch: {section}.{name}")

    def finish(self, status="PASS", reason=None):
        with self._lock():
            if status not in {"PASS", "FAILED"}:
                raise ValueError(status)
            if status == "PASS":
                missing = [name for name in REQUIRED[self.document["kind"]]
                    if self.document["checks"].get(name, {}).get("status") != "PASS"]
                if missing:
                    raise ValueError(f"Required checks have not passed: {sorted(missing)}")
                if any(step["status"] != "PASS" for step in self.document["steps"].values()):
                    raise ValueError("Run has unfinished/failed steps")
                if any(check["status"] == "FAILED" for check in self.document["checks"].values()):
                    raise ValueError("Run has failed checks")
                try:
                    self.validate_files()
                except (ValueError, OSError) as exc:
                    self.document.update(status="FAILED", finished_at=now(), error=str(exc))
                    self._save()
                    raise
            self.document.update(status=status, finished_at=now())
            if reason:
                self.document["error"] = reason
            self._save()

    def require_package(self):
        for name in ("lambda_build", "zip_crc", "handler_imports", "textract_sdk_model"):
            if self.document["checks"].get(name, {}).get("status") != "PASS":
                raise ValueError(f"Package has not passed {name}")
        self.validate_files()
        return self.resolve(self.document["packages"]["lambda"]["path"])


def pytest_run(run):
    with run.step("pytest"):
        path = run.output("test-results/pytest.xml")
        result = subprocess.run([sys.executable, "-m", "pytest", "-ra", f"--junitxml={path}"], cwd=ROOT, check=False)
        if not path.exists():
            raise RuntimeError(f"pytest exited {result.returncode} without JUnit results")
        run.register("pytest", "test-results/pytest.xml")
        suites = ET.parse(path).getroot()
        suites = [suites] if suites.tag == "testsuite" else list(suites.findall("testsuite"))
        totals = {key: sum(int(s.attrib.get(key, 0)) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
        passed = totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"]
        success = result.returncode == 0 and passed > 0 and totals["failures"] + totals["errors"] == 0
        run.check("pytest", "PASS" if success else "FAILED", passed=passed, failed=totals["failures"], errors=totals["errors"], skipped=totals["skipped"])
        if not success:
            raise RuntimeError(f"pytest failed: {totals}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["pytest", "finish", "status"])
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--status", choices=["PASS", "FAILED"], default="PASS")
    parser.add_argument("--reason")
    args = parser.parse_args()
    run = Run(args.run_dir)
    if args.action == "pytest":
        pytest_run(run)
    elif args.action == "finish":
        run.finish(args.status, args.reason)
    print(json.dumps(run.read(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
