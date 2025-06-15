import boto3

from botocore.config import Config

from integration.config import settings


class Boto3Clients:
    def __init__(self) -> None:
        self._s3_client = None
        self._sqs_client = None
        self._dynamodb_client = None
        self._cloudwatch_client = None

        self.config = Config(
            region_name=settings.AWS_REGION,
            retries={
                "max_attempts": 10,
                "mode": "standard",
            },
        )

    def reset(self) -> None:
        self._s3_client = None
        self._sqs_client = None
        self._dynamodb_client = None
        self._cloudwatch_client = None

    @property
    def s3_client(self):
        if not self._s3_client:
            self._s3_client = boto3.client(
                "s3",
                config=self.config,
            )
        return self._s3_client

    @property
    def sqs_client(self):
        if not self._sqs_client:
            self._sqs_client = boto3.client(
                "sqs",
                config=self.config,
            )
        return self._sqs_client

    @property
    def dynamodb_client(self):
        if not self._dynamodb_client:
            self._dynamodb_client = boto3.client(
                "dynamodb",
                config=self.config,
            )
        return self._dynamodb_client

    @property
    def cloudwatch_client(self):
        if not self._cloudwatch_client:
            self._cloudwatch_client = boto3.client(
                "cloudwatch",
                config=self.config,
            )
        return self._cloudwatch_client


BOTO3_CLIENTS = Boto3Clients()
