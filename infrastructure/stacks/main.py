from typing import List, Protocol

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_cloudwatch,
    aws_dynamodb,
    aws_iam,
    aws_lambda,
    aws_logs,
    aws_s3,
    aws_s3_notifications,
    aws_sqs,
)
from constructs import Construct

from infrastructure.constructs import QueueWithDLQ
from integration.config import S3ToSQSConnector, config, settings


class HasSecretArn(Protocol):
    @property
    def secret_arn(self) -> str: ...


class Secrets(Construct):
    secrets: dict[str, HasSecretArn]

    def __init__(
        self,
        scope: Construct,
        id: str,
    ) -> None:
        super().__init__(scope, id)

        self.secrets = {}


class Queues(Construct):
    queues: dict[str, QueueWithDLQ]

    def __init__(
        self,
        scope: Construct,
        id: str,
    ) -> None:
        super().__init__(scope, id)

        self.queues = {}
        self.queues["messages"] = QueueWithDLQ(
            self,
            "messages SQS Queue",
            name="-".join(
                [
                    settings.PROJECT_SLUG,
                    settings.AWS_RESOURCE_SUFFIX,
                    "messages",
                ]
            ),
            create_dlq=True,
            max_receive_count=3,
            is_fifo=False,
            content_based_deduplication=False,
            visibility_timeout=900,
        )


class Buckets(Construct):
    buckets: dict[str, aws_s3.Bucket]

    def __init__(
        self,
        scope: Construct,
        id: str,
    ) -> None:
        super().__init__(scope, id)

        self.buckets = {}
        # storage bucket
        self.buckets["storage"] = aws_s3.Bucket(
            self,
            "storage S3 Bucket",
            block_public_access=aws_s3.BlockPublicAccess.BLOCK_ALL,
            bucket_name=settings.S3_BUCKET_STORAGE,
            encryption=aws_s3.BucketEncryption.S3_MANAGED,
        )


class S3ToSQSConnections(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        buckets: Construct,
        queues: Construct,
        connectors: List[S3ToSQSConnector],
    ) -> None:
        super().__init__(scope, id)

        for connector in connectors:
            bucket_id = connector.bucket_name.lower().replace(" ", "-")
            queue_id = connector.queue_name.lower().replace(" ", "-")
            prefix = connector.prefix

            bucket: aws_s3.Bucket = buckets.buckets[bucket_id]
            queue: aws_sqs.Queue = queues.queues[queue_id].queue  # Get actual SQS queue

            # Allow S3 to send messages to SQS
            queue.add_to_resource_policy(
                aws_iam.PolicyStatement(
                    effect=aws_iam.Effect.ALLOW,
                    actions=["sqs:SendMessage"],
                    principals=[aws_iam.ServicePrincipal("s3.amazonaws.com")],
                    resources=[queue.queue_arn],
                    conditions={"ArnLike": {"aws:SourceArn": bucket.bucket_arn}},
                )
            )

            event_arguments = []
            if prefix is not None:
                event_arguments.append(aws_s3.NotificationKeyFilter(prefix=prefix))
            # Configure S3 to send events to SQS
            bucket.add_event_notification(
                aws_s3.EventType.OBJECT_CREATED,
                aws_s3_notifications.SqsDestination(queue),
                *event_arguments,
            )


class MainStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        sentry_dsn_secret_arn: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        self.secrets = Secrets(self, "Secrets")
        self.queues = Queues(self, "Queues")
        self.buckets = Buckets(self, "Buckets")
        if config.s3_to_sqs_connectors:
            S3ToSQSConnections(
                self,
                "S3ToSQSConnections",
                buckets=self.buckets,
                queues=self.queues,
                connectors=config.s3_to_sqs_connectors,
            )
        # DynamoDB tables
        self.dynamodb_tables: dict[str, aws_dynamodb.Table] = {}

        self.lambda_functions: dict[str, aws_lambda.Function] = {}

        # Lambda permissions
        statements: list[aws_iam.PolicyStatement] = [
            aws_iam.PolicyStatement(
                actions=["cloudwatch:PutMetricData"],
                conditions={
                    "StringEquals": {"cloudwatch:namespace": settings.PROJECT_SLUG}
                },
                resources=["*"],
            ),
        ]
        if sentry_dsn_secret_arn is not None or len(self.secrets.secrets) > 0:
            statements.append(
                aws_iam.PolicyStatement(
                    actions=["secretsmanager:GetSecretValue"],
                    resources=[
                        sentry_dsn_secret_arn,
                        *[
                            secret.secret_arn
                            for secret in self.secrets.secrets.values()
                        ],
                    ],
                )
            )
        if len(self.queues.queues) > 0:
            statements.append(
                aws_iam.PolicyStatement(
                    actions=[
                        "sqs:GetQUeueUrl",
                        "sqs:GetQueueAttributes",
                        "sqs:ListDeadLetterSourceQueues",
                        "sqs:SendMessage",
                        "sqs:ReceiveMessage",
                        "sqs:DeleteMessage",
                        "sqs:ChangeMessageVisibility",
                    ],
                    resources=[
                        *[
                            queue.queue.queue_arn
                            for queue in self.queues.queues.values()
                        ],
                        *[
                            queue.dead_letter_queue.queue_arn
                            for queue in self.queues.queues.values()
                            if queue.dead_letter_queue is not None
                        ],
                    ],
                )
            )
        if len(self.buckets.buckets) > 0:
            statements.extend(
                [
                    aws_iam.PolicyStatement(
                        actions=["s3:ListBucket"],
                        resources=[
                            *[
                                bucket.bucket_arn
                                for bucket in self.buckets.buckets.values()
                            ],
                        ],
                    ),
                    aws_iam.PolicyStatement(
                        actions=[
                            "s3:GetObject*",
                            "s3:PutObject*",
                            "s3:DeleteObject",
                        ],
                        resources=[
                            *[
                                bucket.bucket_arn + "/*"
                                for bucket in self.buckets.buckets.values()
                            ],
                        ],
                    ),
                ]
            )
        if len(self.dynamodb_tables) > 0:
            statements.append(
                aws_iam.PolicyStatement(
                    actions=[
                        "dynamodb:BatchGetItem",
                        "dynamodb:BatchWriteItem",
                        "dynamodb:DeleteItem",
                        "dynamodb:GetItem",
                        "dynamodb:PutItem",
                        "dynamodb:Query",
                        "dynamodb:Scan",
                        "dynamodb:UpdateItem",
                    ],
                    resources=[
                        table.table_arn for table in self.dynamodb_tables.values()
                    ],
                )
            )
        self.lambda_policy = aws_iam.ManagedPolicy(
            self,
            "Lambda Policy",
            description="Assumed by lambda functions during execution",
            managed_policy_name="-".join(
                [
                    settings.PROJECT_SLUG,
                    settings.AWS_RESOURCE_SUFFIX,
                    "lambda-policy",
                ]
            ),
            statements=statements,
        )
        self.lambda_role = aws_iam.Role(
            self,
            "Lambda Role",
            assumed_by=aws_iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                aws_iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
                aws_iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaVPCAccessExecutionRole"
                ),
                aws_iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSXRayDaemonWriteAccess"
                ),
                self.lambda_policy,
            ],
            permissions_boundary=aws_iam.ManagedPolicy.from_managed_policy_name(
                self,
                "Lambda Role Permissions Boundary",
                managed_policy_name=(
                    f"{settings.PROJECT_SLUG}-cdk-bootstrap-boundary-policy"
                ),
            ),
            role_name="-".join(
                [
                    settings.PROJECT_SLUG,
                    settings.AWS_RESOURCE_SUFFIX,
                    "lambda-role",
                ]
            ),
        )

        # Python dependencies lambda layer
        lambda_layer = aws_lambda.LayerVersion(
            self,
            "Python Dependencies",
            code=aws_lambda.Code.from_asset("python.zip"),
            compatible_runtimes=[aws_lambda.Runtime.PYTHON_3_12],
            description="Python packages for lambda functions",
            layer_version_name="-".join(
                [
                    settings.PROJECT_SLUG,
                    settings.AWS_RESOURCE_SUFFIX,
                    "python-deps",
                ]
            ),
        )

        # "Do something" lambda function
        self.lambda_functions["do-something"] = aws_lambda.Function(
            self,
            "Do Something Lambda Function",
            code=aws_lambda.Code.from_asset("lambda.zip"),
            handler="handlers.do_something.handler",
            runtime=aws_lambda.Runtime.PYTHON_3_12,
            architecture=aws_lambda.Architecture.X86_64,
            description="Does something",
            environment={
                "ENVIRONMENT": settings.ENVIRONMENT,
                "AWS_RESOURCE_SUFFIX": settings.AWS_RESOURCE_SUFFIX,
            },
            function_name="-".join(
                [
                    settings.PROJECT_SLUG,
                    settings.AWS_RESOURCE_SUFFIX,
                    "do-something",
                ]
            ),
            layers=[lambda_layer],
            memory_size=1024,
            role=self.lambda_role,
            timeout=Duration.minutes(15),
            tracing=aws_lambda.Tracing.ACTIVE,
        )

        # Create log groups for lambda functions
        for name, lambda_function in self.lambda_functions.items():
            aws_logs.LogGroup(
                self,
                f"Log Group for {name} Lambda Function",
                log_group_name=f"/aws/lambda/{lambda_function.function_name}",
                retention=aws_logs.RetentionDays.THREE_MONTHS,
                removal_policy=RemovalPolicy.DESTROY,
            )

        # Create integration dashboard
        self.integration_dashboard = aws_cloudwatch.Dashboard(
            self,
            "Integration Dashboard",
            dashboard_name="-".join(
                [
                    settings.PROJECT_SLUG,
                    settings.AWS_RESOURCE_SUFFIX,
                    "integration-dashboard",
                ]
            ),
            default_interval=Duration.days(7),
            period_override=aws_cloudwatch.PeriodOverride.INHERIT,
        )
        for name, lambda_function in self.lambda_functions.items():
            self.integration_dashboard.add_widgets(
                aws_cloudwatch.GraphWidget(
                    title=f"Lambda Function - {name} - Invocations - Hourly",
                    left=[
                        lambda_function.metric_invocations(
                            label="Invocations",
                            period=Duration.hours(1),
                            statistic="Sum",
                        ),
                    ],
                    right=[
                        lambda_function.metric_errors(
                            label="Errors",
                            period=Duration.hours(1),
                            statistic="Sum",
                        ),
                        lambda_function.metric_throttles(
                            label="Throttles",
                            period=Duration.hours(1),
                            statistic="Sum",
                        ),
                    ],
                    width=12,
                ),
                aws_cloudwatch.GraphWidget(
                    title=f"Lambda Function - {name} - Duration - Hourly",
                    left=[
                        lambda_function.metric_duration(
                            label="Duration minimum",
                            period=Duration.hours(1),
                            statistic="Minimum",
                        ),
                        lambda_function.metric_duration(
                            label="Duration average",
                            period=Duration.hours(1),
                            statistic="Average",
                        ),
                        lambda_function.metric_duration(
                            label="Duration maximum",
                            period=Duration.hours(1),
                            statistic="Maximum",
                        ),
                    ],
                    width=12,
                ),
            )
        for name, queue in self.queues.queues.items():
            _queue_widgets = []
            _queue_widgets.append(
                aws_cloudwatch.GraphWidget(
                    title=f"Queue - {name} - Hourly",
                    left=[
                        queue.queue.metric_approximate_number_of_messages_visible(
                            label="Visible",
                            period=Duration.hours(1),
                        ),
                    ],
                    right=[
                        queue.queue.metric_approximate_number_of_messages_not_visible(
                            label="In Flight",
                            period=Duration.hours(1),
                        ),
                    ],
                    width=12,
                )
            )
            if queue.dead_letter_queue is not None:
                _queue_widgets.append(
                    aws_cloudwatch.GraphWidget(
                        title=f"Queue DLQ - {name} - Hourly",
                        left=[
                            (
                                queue.dead_letter_queue.metric_approximate_number_of_messages_visible(
                                    label="Visible",
                                    period=Duration.hours(1),
                                )
                            ),
                        ],
                        right=[
                            (
                                queue.dead_letter_queue.metric_approximate_number_of_messages_not_visible(
                                    label="In Flight",
                                    period=Duration.hours(1),
                                )
                            ),
                        ],
                        width=12,
                    )
                )
            self.integration_dashboard.add_widgets(*_queue_widgets)
