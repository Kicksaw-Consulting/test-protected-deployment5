import aws_cdk

from infrastructure.stacks import MainStack, SharedStack
from integration.config import settings

app = aws_cdk.App()
shared_stack = SharedStack(
    app,
    "SharedStack",
    description="Resources shared across all environments",
    env=aws_cdk.Environment(
        account=settings.AWS_ACCOUNT_ID,
        region=settings.AWS_REGION,
    ),
    stack_name=f"{settings.PROJECT_SLUG}-shared-resources",
    tags={
        "project": settings.PROJECT_SLUG,
    },
)
main_stack = MainStack(
    app,
    "MainStack",
    description=f"Contains project resources for {settings.ENVIRONMENT} environment",
    sentry_dsn_secret_arn=shared_stack.sentry_dsn_secret_output.import_value,
    env=aws_cdk.Environment(
        account=settings.AWS_ACCOUNT_ID,
        region=settings.AWS_REGION,
    ),
    stack_name=f"{settings.PROJECT_SLUG}-{settings.AWS_RESOURCE_SUFFIX}-main",
    tags={
        "project": settings.PROJECT_SLUG,
        "environment": settings.ENVIRONMENT,
    },
)
main_stack.add_dependency(shared_stack)

app.synth()
