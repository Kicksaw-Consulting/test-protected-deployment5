#!/bin/bash

set -e

# Zip lambda code and assets
echo "Zipping source code and assets for Lambda Function..."
mkdir lambda-code
cp -r handlers/ integration/ lambda-code
cd lambda-code
find handlers/ -type f | egrep -v ".py$" | xargs -r rm
find integration/ -type f | egrep -v ".py$" | xargs -r rm
find . -type d -empty -delete
zip -r9 lambda.zip . > /dev/null
mv lambda.zip ../
cd .. && rm -r lambda-code

# Zip python dependencies
echo "Zipping Python dependencies..."
poetry export -f requirements.txt -o requirements.txt --without-hashes
mkdir lambda-layer && cd lambda-layer
mv ../requirements.txt .
PYTHON_DIR=python/lib/python3.12/site-packages
mkdir -p $PYTHON_DIR
pip install -r requirements.txt -t $PYTHON_DIR > /dev/null
rm requirements.txt
find . -name "__pycache__" -type d -exec rm -r {} +
find . -name "*.pyc" -type f -delete
find . -name "*.pyo" -type f -delete
zip -r9 python.zip . > /dev/null
mv python.zip ../
cd .. && rm -r lambda-layer

# Deploy
echo "Deploying with AWS CDK..."
cdk deploy --all --require-approval never --outputs-file cdk-outputs.json

rm -r lambda.zip python.zip
