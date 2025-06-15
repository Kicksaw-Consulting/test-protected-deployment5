import contextlib

from unittest.mock import MagicMock

import httpx

from aws_xray_sdk.core import patch, xray_recorder
from aws_xray_sdk.core.exceptions.exceptions import AlreadyEndedException
from aws_xray_sdk.core.models import http
from aws_xray_sdk.ext.httpx.patch import AsyncInstrumentedTransport
from aws_xray_sdk.ext.util import get_hostname, inject_trace_header

from .project_settings import settings


def configure_xray():
    """Configure AWS X-Ray SDK."""
    if not settings.XRAY_ENABLED:

        @contextlib.contextmanager
        def in_subsegment(*args, **kwargs):
            yield MagicMock()

        @contextlib.asynccontextmanager
        async def in_subsegment_async(*args, **kwargs):
            yield MagicMock()

        setattr(xray_recorder, "in_subsegment", in_subsegment)
        setattr(xray_recorder, "in_subsegment_async", in_subsegment_async)
        return

    xray_recorder.configure(
        context_missing="IGNORE_ERROR",
        service="-".join(
            [
                settings.PROJECT_SLUG,
                settings.ENVIRONMENT,
            ]
        ),
    )

    # Patch x-ray's httpx patcher because it's bugged for asyncio
    async def handle_async_request(
        self: AsyncInstrumentedTransport,
        request: httpx.Request,
    ) -> httpx.Response:
        subsegment_context = xray_recorder.in_subsegment_async(
            get_hostname(str(request.url)), namespace="remote"
        )
        subsegment = await subsegment_context.__aenter__()
        try:
            if subsegment is not None:
                try:
                    subsegment.put_http_meta(http.METHOD, request.method)
                    subsegment.put_http_meta(
                        http.URL,
                        str(
                            request.url.copy_with(
                                password=None, query=None, fragment=None
                            )
                        ),
                    )
                    inject_trace_header(request.headers, subsegment)
                except AlreadyEndedException:
                    # https://github.com/aws/aws-xray-sdk-python/issues/164
                    pass
            response = await self._wrapped_transport.handle_async_request(request)
            if subsegment is not None:
                try:
                    subsegment.put_http_meta(http.STATUS, response.status_code)
                except AlreadyEndedException:
                    # https://github.com/aws/aws-xray-sdk-python/issues/164
                    pass
            return response
        except Exception as exc:
            try:
                await subsegment_context.__aexit__(type(exc), exc, exc.__traceback__)
            except AlreadyEndedException:
                # https://github.com/aws/aws-xray-sdk-python/issues/164
                pass
            raise

    AsyncInstrumentedTransport.handle_async_request = handle_async_request

    # Patch libraries
    patch(
        [
            "aioboto3",
            "aiobotocore",
            "boto3",
            "botocore",
            "httpx",
            "pynamodb",
        ],
        raise_errors=False,
    )
