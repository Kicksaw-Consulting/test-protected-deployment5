from typing import Literal

import boto3

from pydantic import HttpUrl, field_validator
from pydantic_core.core_schema import ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict

from .utils import ENV_FILES, get_env_value, get_secret


class Settings(BaseSettings):
    CLIENT_NAME: str = "Kicksaw"
    PROJECT_NAME: str = "Salesforce Integration"
    PROJECT_SLUG: str = "salesforce-integration"
    PROJECT_DESCRIPTION: str = "Salesforce Integration for Kicksaw by Kicksaw"
    PROJECT_VERSION: str = "0.0.1"

    ENVIRONMENT: Literal[
        "testing",  # Used during testing (locally and in CI)
        "development",  # Used during development (in AWS and locally)
        "staging",  # Used during UAT
        "production",  # Used in production
    ]

    # AWS
    AWS_RESOURCE_SUFFIX: str = "<changeme>"
    """Suffix added to AWS resources to avoid name collisions."""
    AWS_ACCOUNT_ID: str = "<changeme>"
    AWS_REGION: str
    XRAY_ENABLED: bool = True
    S3_BUCKET_STORAGE: str = "<changeme>"
    SQS_QUEUE_MESSAGES: str = "<changeme>"

    @field_validator("AWS_RESOURCE_SUFFIX")
    @classmethod
    def construct_aws_resource_suffix(
        cls,
        value: str,
        info: ValidationInfo,
    ) -> str:
        if value != "<changeme>":
            return value
        return info.data["ENVIRONMENT"]

    @field_validator("AWS_ACCOUNT_ID")
    @classmethod
    def validate_account_id(
        cls,
        value: str,
    ) -> str:
        if value != "<changeme>":
            return value
        return boto3.client("sts").get_caller_identity()["Account"]

    @field_validator(
        "S3_BUCKET_STORAGE",
    )
    @classmethod
    def validate_s3_buckets(
        cls,
        value: str,
        info: ValidationInfo,
    ) -> str:
        if value != "<changeme>":
            return value
        assert info.field_name is not None
        return "-".join(
            [
                info.data["PROJECT_SLUG"],
                info.data["AWS_RESOURCE_SUFFIX"],
                info.field_name.replace("S3_BUCKET_", "").lower().replace("_", "-"),
            ]
        )

    @field_validator(
        "SQS_QUEUE_MESSAGES",
    )
    @classmethod
    def validate_sqs_queues(
        cls,
        value: str,
        info: ValidationInfo,
    ) -> str:
        if value != "<changeme>":
            return value
        assert info.field_name is not None
        queue_name = "-".join(
            [
                info.data["PROJECT_SLUG"],
                info.data["AWS_RESOURCE_SUFFIX"],
                info.field_name.replace("SQS_QUEUE_", "").lower().replace("_", "-"),
            ]
        )
        if info.field_name in {}:
            queue_name += ".fifo"
        return queue_name

    @property
    def SENTRY_DSN(self) -> HttpUrl | None:  # noqa: N802
        env_value = get_env_value("SENTRY_DSN")
        if env_value is not None:
            if env_value.strip(" ").lower() in {
                "",
                "null",
                "none",
            }:
                return None
            return HttpUrl(env_value)
        if self.ENVIRONMENT == "testing":
            return None
        secret_name = "-".join(
            [
                self.PROJECT_SLUG,
                "shared-resources",
                "sentry-dsn",
            ]
        )
        sentry_dsn = get_secret(secret_name)["dsn"]
        if sentry_dsn is None or sentry_dsn.strip(" ").lower() in {
            "",
            "null",
            "none",
        }:
            return None
        return HttpUrl(sentry_dsn)

    # Model configuration
    model_config = SettingsConfigDict(
        extra="ignore",
        case_sensitive=True,
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
    )


settings = Settings()  # type: ignore
