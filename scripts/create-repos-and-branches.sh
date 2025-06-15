#!/bin/bash -e

scripts/github/create_repos_and_branches.py \
    create-repo-with-branches \
    --repo-name kicksaw-salesforce-integration \
    --aws-region us-west-2 \
    --aws-account-id 123456789012