"""Lambda entry point for processor."""

from ..aws.services import runtime
from ..processing.process_document import handle


def lambda_handler(event, context):
    services, store, _ = runtime()
    return handle(event, context, services, store)
