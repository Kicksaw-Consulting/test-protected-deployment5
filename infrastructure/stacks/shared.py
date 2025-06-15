from aws_cdk import CfnOutput, SecretValue, Stack, aws_secretsmanager
from constructs import Construct

from integration.config import settings


class SharedStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        sentry_dsn_secret = aws_secretsmanager.Secret(
            self,
            "Sentry DSN Secret",
            description="Sentry DSN for shared resources",
            secret_name=f"{settings.PROJECT_SLUG}-shared-resources-sentry-dsn",
            secret_object_value={"dsn": SecretValue(None)},
        )
        self.sentry_dsn_secret_output = CfnOutput(
            self,
            "Sentry DSN Secret ARN Output",
            value=sentry_dsn_secret.secret_arn,
            description="Sentry DSN to be used across all environments",
            export_name=f"{settings.PROJECT_SLUG}-shared-resources-sentry-dsn",
        )
