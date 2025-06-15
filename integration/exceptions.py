from pydantic import BaseModel


class Metadata(BaseModel):
    report_in_sentry: bool
    """If True, report the error in Sentry."""
    sentry_fingerprint: str | None
    """
    If provided, all errors with the same fingerprint will be grouped together
    in the same issue in Sentry.
    See https://docs.sentry.io/platforms/python/usage/sdk-fingerprinting
    """
    report_in_kicksaw_integration_app: bool
    """If True, report the error in the Kicksaw Integration App in Salesforce."""

    model_config = {
        "extra": "forbid",
    }


class KicksawIntegrationError(Exception):
    """Base class for all integration errors."""

    def __init__(
        self,
        message,
        *args,
        report_in_sentry: bool = True,
        sentry_fingerprint: str | None = None,
        report_in_kicksaw_integration_app: bool = True,
        **kwargs,
    ):
        super().__init__(message, *args, **kwargs)
        self.metadata: Metadata = Metadata(
            report_in_sentry=report_in_sentry,
            sentry_fingerprint=sentry_fingerprint,
            report_in_kicksaw_integration_app=report_in_kicksaw_integration_app,
        )
