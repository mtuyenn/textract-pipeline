"""Runtime settings. No credentials or network operations at import time."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    table_name: str
    bucket_name: str
    topic_arn: str = ""
    region: str = "us-east-1"
    work_index: str = "WorkIndex"
    lease_seconds: int = 240
    poll_seconds: int = 60
    max_attempts: int = 5
    max_jobs: int = 10
    max_async_mb: int = 50
    max_result_mb: int = 32
    max_pages: int = 100
    raw_prefix: str = "raw-results/"
    parsed_prefix: str = "parsed-results/"
    output_prefix: str = "output/"

    @classmethod
    def from_env(cls):
        config = cls(
            table_name=os.environ["RESULTS_TABLE"],
            bucket_name=os.environ["DATA_BUCKET"],
            topic_arn=os.getenv("NOTIFICATION_TOPIC_ARN", ""),
            region=os.getenv("AWS_REGION", "us-east-1"),
            work_index=os.getenv("WORK_INDEX", "WorkIndex"),
            lease_seconds=int(os.getenv("LEASE_SECONDS", "240")),
            poll_seconds=int(os.getenv("POLL_SECONDS", "60")),
            max_attempts=int(os.getenv("MAX_ATTEMPTS", "5")),
            max_jobs=int(os.getenv("MAX_JOBS_PER_TICK", "10")),
            max_async_mb=int(os.getenv("MAX_ASYNC_MB", "50")),
            max_result_mb=int(os.getenv("MAX_RESULT_MB", "32")),
            max_pages=int(os.getenv("MAX_PAGES", "100")),
        )
        if config.region not in {"us-east-1", "us-west-2"}:
            raise ValueError("Learner Lab supports only us-east-1 or us-west-2 in this project")
        if config.lease_seconds < 210 or config.max_jobs < 1:
            raise ValueError("LEASE_SECONDS must exceed the 180-second Lambda timeout; MAX_JOBS >= 1")
        if min(config.poll_seconds, config.max_attempts, config.max_result_mb, config.max_pages, config.max_async_mb) < 1:
            raise ValueError("Polling, attempts, memory, page and size limits must be positive")
        if config.max_async_mb > 50 or config.max_pages > 100 or config.max_result_mb > 32:
            raise ValueError("This lab implementation caps async at 50 MB / 100 pages / 32 MB raw JSON")
        return config
