import logging

from typing import Any

import httpx
import sentry_sdk
import sentry_sdk.integrations

from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from integration.exceptions import KicksawIntegrationError

from .project_settings import settings


def before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """
    Preprocess event before it's sent to Sentry.

    Parameters
    ----------
    event : dict[str, Any]
        See https://develop.sentry.dev/sdk/event-payloads/
    hint : dict[str, Any]
        See https://docs.sentry.io/platforms/python/guides/logging/configuration/filtering/hints/

    Returns
    -------
    dict[str, Any]
        Modified event.

    """
    # Propagate non-exception events as-is
    if "exc_info" not in hint:
        return event

    exception = hint["exc_info"][1]
    if isinstance(exception, KicksawIntegrationError):
        if not exception.metadata.report_in_sentry:
            return None
        if exception.metadata.sentry_fingerprint is not None:
            event["fingerprint"] = [exception.metadata.sentry_fingerprint]
    # Group all httpx errors to the same domain together
    elif (
        isinstance(exception, httpx.HTTPError)
        and isinstance(exception.request, httpx.Request)
        and isinstance(exception.request.url, str)
    ):
        base_url = ".".join(exception.request.url.split("/")[2].split(".")[-2:])
        event["fingerprint"] = [
            "-".join(
                [
                    exception.__class__.__name__,
                    base_url,
                ]
            )
        ]

    return event


def configure_sentry() -> None:
    """
    Configure Sentry error logging for the project.

    """
    if settings.SENTRY_DSN is not None and settings.ENVIRONMENT != "testing":
        integrations: list[sentry_sdk.integrations.Integration] = [
            AwsLambdaIntegration(timeout_warning=True),
            LoggingIntegration(level=logging.DEBUG, event_level=logging.ERROR),
        ]
        sentry_sdk.init(
            dsn=str(settings.SENTRY_DSN),
            debug=False,
            environment=settings.ENVIRONMENT,
            send_default_pii=settings.ENVIRONMENT in {"development", "staging"},
            integrations=integrations,
            before_send=before_send,
        )
