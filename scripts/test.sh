#!/bin/bash

export ENVIRONMENT=testing
export AWS_ACCOUNT_ID=123456789012
export AWS_REGION=us-west-2
export XRAY_ENABLED=false

poetry run pytest
