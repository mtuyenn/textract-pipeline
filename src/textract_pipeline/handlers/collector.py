"""Lambda entry point for collector."""

from ..aws.services import runtime
from ..processing.collect_result import handle


def lambda_handler(event, context):
    services, store, _ = runtime()
    return handle(context, services, store)
