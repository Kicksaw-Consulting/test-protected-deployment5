import asyncio
import json
import logging
import traceback

from typing import Any, TypedDict

from aws_xray_sdk.core import xray_recorder

from integration.config import settings
from integration.salesforce import KicksawIntegrationAppExecution, get_salesforce_client
from integration.utils import get_httpx_client

logger = logging.getLogger(__name__)


class Event(TypedDict): ...


def handler(event: Event, context: Any) -> None:
    asyncio.run(async_handler(event, context))


async def async_handler(event: Event, context: Any) -> None:
    """Do something."""
    async with get_httpx_client() as httpx_client:
        salesforce = get_salesforce_client(httpx_client)
        execution = KicksawIntegrationAppExecution(
            salesforce_client=salesforce,
            integration_name=(
                f"{settings.PROJECT_SLUG} {settings.ENVIRONMENT} Do something"
            ),
            execution_payload=dict(event),
        )
        execution_soft_errors: list[str] = []
        try:
            with xray_recorder.in_subsegment("Doing something") as subsegment:
                logger.info("Doing something with event: %s", json.dumps(event))

            # Finish execution
            if len(execution_soft_errors) > 0:
                logger.warning("Encountered %d soft errors", len(execution_soft_errors))
                for error in execution_soft_errors:
                    execution.logger.warning(error)
                execution.error_message = (
                    f"Encountered {len(execution_soft_errors):,d} errors, "
                    f"see execution logs for details"
                )
                execution.success = False
            else:
                execution.response_payload = {"success": True}
                execution.success = True

        except* Exception as eg:
            match len(eg.exceptions):
                case 1:
                    execution.error_message = "\n".join(
                        traceback.format_exception_only(eg.exceptions[0])
                    )
                case _:
                    for exception in eg.exceptions:
                        execution.logger.error(
                            "\n".join(traceback.format_exception_only(exception))
                        )
                    execution.error_message = (
                        f"Execution failed with {len(eg.exceptions):,d} errors, "
                        f"see ERROR logs for details"
                    )
            raise eg

        finally:
            async with xray_recorder.in_subsegment_async(
                "Creating Kicksaw Integration App execution record"
            ) as subsegment:
                task = asyncio.create_task(execution.create_all())
                await asyncio.shield(task)
                subsegment.put_annotation(
                    "integration_name",
                    execution.integration_name,
                )
                subsegment.put_annotation("integration_id", execution.integration_id)
                subsegment.put_annotation("execution_id", execution.execution_id)
                subsegment.put_annotation("success", execution.success)
