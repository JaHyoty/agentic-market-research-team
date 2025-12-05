#!/bin/bash
echo "Initializing LocalStack resources..."

awslocal s3 mb s3://market-research-artifacts
awslocal s3 mb s3://market-research-reports

awslocal sqs create-queue --queue-name market-research-tasks

echo "LocalStack resources initialized."
