import pathlib

from typing import Generator

import moto
import pytest

from integration.config import settings
from integration.utils import BOTO3_CLIENTS

HERE = pathlib.Path(__file__).parent.resolve()


@pytest.fixture(scope="function")
def data_folder() -> pathlib.Path:
    """Path to test data folder."""
    return HERE / "data"


@pytest.fixture(scope="function", autouse=True)
def mock_aws_resources() -> Generator[None, None, None]:
    with moto.mock_aws():
        BOTO3_CLIENTS.reset()
        BOTO3_CLIENTS.s3_client.create_bucket(
            Bucket=settings.S3_BUCKET_STORAGE,
            CreateBucketConfiguration={"LocationConstraint": settings.AWS_REGION},
        )
        BOTO3_CLIENTS.sqs_client.create_queue(
            QueueName=settings.SQS_QUEUE_MESSAGES,
            Attributes={
                "VisibilityTimeout": "900",
                "FifoQueue": str(settings.SQS_QUEUE_MESSAGES.endswith(".fifo")).lower(),
            },
        )
        yield None
        BOTO3_CLIENTS.reset()
