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
    echo "Building and starting local Docker Compose environment..."
    cd local-dev
    docker compose up -d --build
    cd ..
    
    echo ""
    echo "Local deployment complete!"
    echo ""
    echo "Services running:"
    echo "  - LocalStack (S3, SQS, Secrets): http://localhost:4566"
    echo "  - DynamoDB Local: http://localhost:8000"
    echo "  - API Gateway: http://localhost:8080"
    echo "  - Worker: Running in Docker"
    echo ""
    echo "To view worker logs:"
    echo "  docker compose -f local-dev/docker-compose.yml logs -f worker"
    echo ""
    echo "To start the frontend:"
    echo "  cd frontend && npm run dev"

elif [ "$ENVIRONMENT" == "cloud" ]; then
    # Validate required environment variables
    if [ -z "$AWS_ACCOUNT_ID" ]; then
        export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
        echo "Using AWS Account ID: $AWS_ACCOUNT_ID"
    fi

    ECR_REGISTRY="$AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com"
    IMAGE_NAME="market-research-backend"
    TAG="latest"
    FULL_IMAGE="$ECR_REGISTRY/$IMAGE_NAME:$TAG"

    # Login to ECR
    echo "Logging in to ECR..."
    aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin "$ECR_REGISTRY"

    # Build and push backend image
    echo "Building backend image..."
    docker build --platform linux/amd64 -f local-dev/Dockerfile.api -t "$FULL_IMAGE" .

    echo "Pushing image to ECR..."
    docker push "$FULL_IMAGE"

    # Update ECS service to deploy new image
    echo "Updating ECS service..."
    aws ecs update-service \
        --cluster market-research \
        --service worker \
        --force-new-deployment \
        --region us-east-1

    echo ""
    echo "Backend deployment complete!"
    echo ""
    
    # Frontend deployment
    echo "Building frontend..."
    cd frontend
    npm run build
    
    # Get the frontend bucket from Terraform output
    cd ../infrastructure
    FRONTEND_BUCKET=$(terraform output -raw frontend_bucket 2>/dev/null || echo "")
    CLOUDFRONT_DIST_ID=$(terraform output -raw cloudfront_distribution_id 2>/dev/null || echo "")
    cd ..
    
    if [ -n "$FRONTEND_BUCKET" ]; then
        echo "Deploying frontend to S3: $FRONTEND_BUCKET"
        aws s3 sync frontend/out/ "s3://$FRONTEND_BUCKET/" --delete
        
        if [ -n "$CLOUDFRONT_DIST_ID" ]; then
            echo "Invalidating CloudFront cache..."
            aws cloudfront create-invalidation \
                --distribution-id "$CLOUDFRONT_DIST_ID" \
                --paths "/*"
        fi
        
        CLOUDFRONT_URL=$(cd infrastructure && terraform output -raw cloudfront_url 2>/dev/null || echo "")
        echo ""
        echo "Frontend deployment complete!"
        echo "Application URL: $CLOUDFRONT_URL"
    else
        echo "Warning: Could not find frontend_bucket in Terraform outputs."
        echo "Run 'terraform apply' in infrastructure/ first, then re-run this script."
    fi

else
    echo "Invalid environment: $ENVIRONMENT"
    echo "Usage: ./deploy.sh [local|cloud]"
    exit 1
fi

echo ""
echo "Deployment complete!"
