import os
import pathlib
import warnings

from functools import cache
from typing import Literal, overload

import boto3
import orjson

from cachetools import TTLCache, cached
from dotenv import dotenv_values

ENV_FILES: tuple[pathlib.Path, ...] = (
    # .env file in the same directory as this module
    pathlib.Path(__file__).parent.resolve() / ".env",
    # .env file in the root of the project
    pathlib.Path(__file__).parent.parent.parent.resolve() / ".env",
)


@cache
def get_env_value(key: str) -> str | None:
    """
    Used by properties to mimic pydantic's default behavior when fetching values
    from environment and .env files.

    Parameters
    ----------
    key : str
        The name of the environment variable to fetch.

    Returns
    -------
    str | None
        The value of the environment variable, or None if it doesn't exist.

    """
    # Check environment variables first
    try:
        return os.environ[key]
    except KeyError:
        pass

    # Check .env files
    for env_file in ENV_FILES:
        if not env_file.exists():
            continue
        env_values = dotenv_values(env_file)
        try:
            return env_values[key]
        except KeyError:
            pass

    return None


@overload
def get_secret(
    name: str,
    parse_json: Literal[True] = True,
) -> dict[str, str | None]: ...


@overload
def get_secret(
    name: str,
    parse_json: Literal[False],
) -> str: ...


@cached(cache=TTLCache(maxsize=1024, ttl=60))
def get_secret(
    name: str,
    parse_json: bool = True,
) -> dict[str, str | None] | str:
    """
    Get secret from AWS Secrets Manager.

    Parameters
    ----------
    name : str
        Name of the secret.
    parse_json : bool, optional
        If True, the secret is parsed as JSON, by default True.
        Otherwise, the raw string is returned.

    Returns
    -------
    dict[str, str | None] | str
        Dictionary with key-value pairs as declared in the secret string
        if parse_json is True. Otherwise, the raw string is returned.

    """
    secret_value = str(
        boto3.client("secretsmanager").get_secret_value(SecretId=name)["SecretString"]
    )
    if parse_json:
        secret_dict: dict[str, str | None] = {}
        for key, value in orjson.loads(secret_value).items():
            if value is None:
                secret_dict[key] = None
            else:
                secret_dict[key] = str(value)
                if "changeme" in str(value).lower():
                    warnings.warn(f"'{key}' is not set on the '{name}' secret")
        return secret_dict
    if "changeme" in secret_value.lower():
        warnings.warn(f"Secret '{name}' is not set")
    return secret_value
