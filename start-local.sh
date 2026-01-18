#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting Local Environment...${NC}"

# 1. Start Docker Services (includes worker)
echo -e "${GREEN}Starting Docker Compose services...${NC}"
cd local-dev
docker compose up -d --build
cd ..

echo -e "${BLUE}Local Environment is UP and READY!${NC}"
echo ""
echo -e "Services running:"
echo -e "  - LocalStack (S3, SQS, Secrets): http://localhost:4566"
echo -e "  - DynamoDB Local: http://localhost:8000"
echo -e "  - API Gateway: http://localhost:8080"
echo -e "  - Worker: Running in Docker (simulates ECS Fargate)"
echo ""
echo -e "To view worker logs:"
echo -e "  docker compose -f local-dev/docker-compose.yml logs -f worker"
echo ""
echo -e "To start the frontend:"
echo -e "  cd frontend && npm run dev"
