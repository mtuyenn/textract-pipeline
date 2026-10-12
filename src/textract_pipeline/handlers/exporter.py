"""Lambda entry point for exporter."""

from ..aws.services import runtime
from ..processing.exporting import export


def lambda_handler(event, context):
    services, store, _ = runtime()
    return {"exports": export(services, store, event)}
