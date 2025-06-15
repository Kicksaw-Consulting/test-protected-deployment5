from aws_cdk import Duration, aws_sqs
from constructs import Construct


class QueueWithDLQ(Construct):
    dead_letter_queue: aws_sqs.Queue | None
    queue: aws_sqs.Queue

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        name: str,
        create_dlq: bool,
        max_receive_count: int = 3,
        is_fifo: bool = False,
        content_based_deduplication: bool = False,
        visibility_timeout: int = 900,
    ) -> None:
        """
        Creates an SQS queue and, optionally, a dead letter queue for it.

        Parameters
        ----------
        name : str
            Queue name, e.g. "kicksaw-production-api-requests".
        create_dlq : bool
            Whether to create a dead letter queue for this queue.
        max_receive_count : int
            Maximum number of times a message can be received before being sent
            to the dead letter queue.
        is_fifo : bool
            Whether this queue is FIFO.
        content_based_deduplication : bool
            Whether to enable content-based deduplication for this queue.
        visibility_timeout : int
            Visibility timeout for this queue.

        """
        super().__init__(scope, id)

        assert not name.endswith(
            ".fifo"
        ), "Queue name must not end with .fifo, use the is_fifo argument instead"

        # AWS is bugged and doesn't allow passing fifo=False
        fifo_params = {}
        if is_fifo:
            fifo_params["fifo"] = True
            fifo_params["content_based_deduplication"] = content_based_deduplication

        self.dead_letter_queue = None
        if create_dlq:
            self.dead_letter_queue = aws_sqs.Queue(
                self,
                f"{id} DLQ",
                queue_name=f"{name}-dlq.fifo" if is_fifo else f"{name}-dlq",
                retention_period=Duration.days(14),
                visibility_timeout=Duration.seconds(visibility_timeout),
                **fifo_params,
            )
        self.queue = aws_sqs.Queue(
            self,
            id,
            dead_letter_queue=aws_sqs.DeadLetterQueue(
                max_receive_count=max_receive_count,
                queue=self.dead_letter_queue,
            )
            if self.dead_letter_queue is not None
            else None,
            queue_name=f"{name}.fifo" if is_fifo else name,
            retention_period=Duration.days(14),
            visibility_timeout=Duration.seconds(visibility_timeout),
            **fifo_params,
        )
