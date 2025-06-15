#!/usr/bin/env python3
# ruff: noqa: T201, PLR0911

##############################################################################################
# NOTE: This script is used to create a GitHub OIDC role and policy for the project.
# It is never intended to be run locally.  Instead it is used to create the role and policy
# in the AWS account that is used for the project via the Cloud Shell.
##############################################################################################

import json
import time

import boto3  # type: ignore

from botocore.exceptions import ClientError  # type: ignore

# Constants
ROLE_NAME = "salesforce-integration-deployment-role"
POLICY_NAME = "salesforce-integration-cdk-deployment-policy"


def wait_for_role(iam_client, role_name, max_attempts=10, delay=2):
    """Wait for the IAM role to be available."""
    waiter = iam_client.get_waiter("role_exists")
    try:
        waiter.wait(
            RoleName=role_name,
            WaiterConfig={"Delay": delay, "MaxAttempts": max_attempts},
        )
        return True
    except ClientError as e:
        print(f"Error waiting for role: {e}")
        return False


def wait_for_policy(iam_client, policy_arn, max_attempts=10, delay=2):
    """Wait for the IAM policy to be available."""
    for attempt in range(max_attempts):
        try:
            iam_client.get_policy(PolicyArn=policy_arn)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                time.sleep(delay)
                continue
            raise
    return False


def main():
    # Initialize AWS clients
    iam_client = boto3.client("iam")
    sts_client = boto3.client("sts")

    # Get AWS account ID
    try:
        account_id = sts_client.get_caller_identity()["Account"]
    except ClientError as e:
        print(f"Error getting account ID: {e}")
        return

    # Create role trust policy
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Federated": f"arn:aws:iam::{account_id}:oidc-provider/token.actions.githubusercontent.com"
                },
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
                    },
                    "StringLike": {
                        "token.actions.githubusercontent.com:sub": "repo:Kicksaw-Consulting/*"
                    },
                },
            }
        ],
    }

    # Create IAM role
    try:
        response = iam_client.create_role(
            RoleName=ROLE_NAME, AssumeRolePolicyDocument=json.dumps(trust_policy)
        )
        print(f"✅ Role created: {ROLE_NAME}")

        # Wait for role to be available
        if not wait_for_role(iam_client, ROLE_NAME):
            print("❌ Failed to confirm role creation")
            return
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"Role {ROLE_NAME} already exists")
        else:
            print(f"Error creating role: {e}")
            return

    # Create IAM policy
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Action": ["*"], "Resource": ["*"]}],
    }

    try:
        response = iam_client.create_policy(
            PolicyName=POLICY_NAME, PolicyDocument=json.dumps(policy_document)
        )
        policy_arn = response["Policy"]["Arn"]
        print(f"✅ Policy created: {POLICY_NAME}")

        # Wait for policy to be available
        if not wait_for_policy(iam_client, policy_arn):
            print("❌ Failed to confirm policy creation")
            return
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            # Get the existing policy ARN
            try:
                response = iam_client.get_policy(
                    PolicyArn=f"arn:aws:iam::{account_id}:policy/{POLICY_NAME}"
                )
                policy_arn = response["Policy"]["Arn"]
                print(f"Policy {POLICY_NAME} already exists")
            except ClientError as e:
                print(f"Error getting existing policy: {e}")
                return
        else:
            print(f"Error creating policy: {e}")
            return

    # Attach policy to role
    try:
        iam_client.attach_role_policy(RoleName=ROLE_NAME, PolicyArn=policy_arn)
        print("✅ Policy attached to role")

        # Verify policy attachment
        response = iam_client.list_attached_role_policies(RoleName=ROLE_NAME)
        attached_policies = response["AttachedPolicies"]
        if any(policy["PolicyName"] == POLICY_NAME for policy in attached_policies):
            print("✅ Verified policy attachment")
        else:
            print("❌ Policy attachment verification failed")
    except ClientError as e:
        print(f"Error attaching policy to role: {e}")
        return

    print("🎉 All operations completed successfully!")


if __name__ == "__main__":
    main()
