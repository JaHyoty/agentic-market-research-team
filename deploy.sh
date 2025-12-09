#!/bin/bash
set -e

ENVIRONMENT=$1
SCRIPT_DIR=$(dirname "$0")

if [ -z "$ENVIRONMENT" ]; then
    echo "Usage: ./deploy.sh [local|cloud]"
    exit 1
fi

echo "Deploying to $ENVIRONMENT..."

if [ "$ENVIRONMENT" == "local" ]; then
    # Ensure snap bin is in path for local kubectl
    export PATH=$PATH:/snap/bin
    
    # Point to the local kubeconfig
    export KUBECONFIG=local-dev/kubeconfig/kubeconfig.yaml
    
    REGISTRY="localhost:5000"
    IMAGE_NAME="market-research-backend"
    TAG="local"
    FULL_IMAGE="$REGISTRY/$IMAGE_NAME:$TAG"
    
    echo "Building image for local environment..."
    docker build -f local-dev/Dockerfile.api -t "$FULL_IMAGE" .
    
    echo "Pushing image to local registry..."
    docker push "$FULL_IMAGE"
    
    
    echo "Configuring LocalStack DNS workaround..."
    LOCALSTACK_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' local-dev-localstack-1 || true)
    if [ -n "$LOCALSTACK_IP" ]; then
        echo "Found LocalStack IP: $LOCALSTACK_IP"
        # Create Service and Endpoints for localstack resolution
        cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: localstack
  namespace: default
spec:
  ports:
  - port: 4566
    targetPort: 4566
---
apiVersion: v1
kind: Endpoints
metadata:
  name: localstack
  namespace: default
subsets:
- addresses:
  - ip: $LOCALSTACK_IP
  ports:
  - port: 4566
EOF
    else
        echo "Warning: Could not find LocalStack container IP. DNS resolution for 'localstack' might fail."
    fi

    # Load secrets from .env if present
    if [ -f local-dev/.env ]; then
        echo "Loading secrets from local-dev/.env..."
        export $(grep -v '^#' local-dev/.env | xargs)
    else
        echo "Warning: local-dev/.env not found using default mock keys except for OpenRouter which might fail."
    fi

    echo "Seeding Secrets in LocalStack..."
    docker exec local-dev-localstack-1 awslocal secretsmanager delete-secret --secret-id market-research-keys --force-delete-without-recovery || true
    docker exec local-dev-localstack-1 awslocal secretsmanager create-secret \
        --name market-research-keys \
        --secret-string "{\"OPENAI_API_KEY\":\"${OPENAI_API_KEY:-mock-openai-key}\",\"TAVILY_API_KEY\":\"${TAVILY_API_KEY:-mock-tavily-key}\",\"OPENROUTER_API_KEY\":\"${OPENROUTER_API_KEY:-mock-openrouter-key}\"}" \
        --region us-east-1 || true

    echo "Configuring DynamoDB DNS workaround..."
    DYNAMODB_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' local-dev-dynamodb-local-1 || true)
    if [ -n "$DYNAMODB_IP" ]; then
        echo "Found DynamoDB IP: $DYNAMODB_IP"
        # Create Service and Endpoints for dynamodb resolution
        cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: dynamodb-local
  namespace: default
spec:
  ports:
  - port: 8000
    targetPort: 8000
---
apiVersion: v1
kind: Endpoints
metadata:
  name: dynamodb-local
  namespace: default
subsets:
- addresses:
  - ip: $DYNAMODB_IP
  ports:
  - port: 8000
EOF
    else
        echo "Warning: Could not find DynamoDB container IP. DNS resolution for 'dynamodb-local' might fail."
    fi

    echo "Applying manifests..."
    kubectl apply -k k8s/overlays/local
    
    echo "Restarting worker deployment to pick up new image..."
    kubectl rollout restart deployment/market-research-worker

elif [ "$ENVIRONMENT" == "cloud" ]; then
    if [ -z "$ECR_REGISTRY" ]; then
        echo "Error: ECR_REGISTRY environment variable is not set."
        echo "Example: export ECR_REGISTRY=123456789012.dkr.ecr.us-east-1.amazonaws.com"
        exit 1
    fi
    
    # Ensure AWS login
    aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin "$ECR_REGISTRY"
    
    IMAGE_NAME="market-research-backend"
    TAG="latest" # You can change this to $(git rev-parse --short HEAD) for versioning
    FULL_IMAGE="$ECR_REGISTRY/$IMAGE_NAME:$TAG"
    
    echo "Building image for cloud environment..."
    docker build --platform linux/amd64 -f local-dev/Dockerfile.api -t "$FULL_IMAGE" .
    
    echo "Pushing image to ECR..."
    docker push "$FULL_IMAGE"
    
    # Update kustomization.yaml or use kustomize edit to set the image
    echo "Updating kustomize image..."
    cd k8s/overlays/prod
    kustomize edit set image market-research-backend:latest="$FULL_IMAGE"
    cd -
    
    echo "Applying manifests..."
    kubectl apply -k k8s/overlays/prod
    
else
    echo "Invalid environment: $ENVIRONMENT"
    echo "Usage: ./deploy.sh [local|cloud]"
    exit 1
fi

echo "Deployment complete!"
