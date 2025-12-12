#!/bin/bash
set -e

# Directory where reports will be synced
LOCAL_DIR="local-dev/reports"

# Ensure the directory exists
mkdir -p "$LOCAL_DIR"

echo "Syncing S3 bucket 'market-research-reports' to '$LOCAL_DIR'..."

# Run s3 sync command inside the LocalStack container to avoid needing aws-cli on host
# We use 'cp' from container to host if we wanted to copy OUT, but 'awslocal s3 sync' syncs from bucket to local FS *inside* the container.
# Wait, 'awslocal' is usually an alias for 'aws --endpoint-url ...'.
# If we run it on the HOST, we need 'aws' installed.
# If we run it in the CONTAINER, we need to mount the volume to get files OUT.

# Better approach for "no deps on host":
# 1. Use docker exec to stream files? No, sync is hard with streams.
# 2. Simplest: Require 'aws' or 'awslocal' on host.
# 3. Docker approach: Run a transient container with aws-cli that mounts the local volume.

# Let's try to use the 'localstack/localstack' container itself if it has 'aws' installed?
# LocalStack container usually has 'awslocal' installed.

# If we run 'awslocal s3 sync s3://bucket /tmp/reports' INSIDE container, the files stay in container.
# UNLESS we mounted a volume. We didn't mount a generic volume for reports.

# So, to make this work without modifying docker-compose (restarting services), we should rely on the HOST having 'aws' or 'awslocal'.
# OR, use a one-off docker run command.

# Let's check if 'aws' is installed on the host.
if ! command -v aws &> /dev/null; then
    echo "Error: 'aws' CLI is not installed on the host."
    echo "Attempting to use docker to sync..."
    
    # Run a container that has AWS CLI, connect to localstack network, mount local dir
    docker run --rm \
        --network local-dev_default \
        -v "$(pwd)/$LOCAL_DIR:/downloads" \
        -e AWS_ACCESS_KEY_ID=test \
        -e AWS_SECRET_ACCESS_KEY=test \
        -e AWS_REGION=us-east-1 \
        amazon/aws-cli \
        --endpoint-url http://localstack:4566 \
        s3 sync s3://market-research-reports /downloads
        
else
    # AWS CLI exists on host
    export AWS_ACCESS_KEY_ID=test
    export AWS_SECRET_ACCESS_KEY=test
    export AWS_REGION=us-east-1
    
    aws --endpoint-url http://localhost:4566 s3 sync s3://market-research-reports "$LOCAL_DIR"
fi

echo "Sync complete."
ls -R "$LOCAL_DIR"
