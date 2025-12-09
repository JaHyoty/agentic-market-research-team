#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting Local Environment...${NC}"

# 1. Start Docker Services
echo -e "${GREEN}Starting Docker Compose services (LocalStack, DynamoDB, API Gateway)...${NC}"
cd local-dev
docker compose up -d
cd ..

# 2. Start Kind Cluster
./local-dev/scripts/start-kind.sh

# 3. Setup Kind Cluster (KEDA, etc.)
./local-dev/scripts/setup-kind.sh

echo -e "${BLUE}Local Environment is UP and READY!${NC}"
echo -e "S3 Buckets: market-research-artifacts, market-research-reports"
echo -e "SQS Queue: market-research-tasks"
echo -e "DynamoDB Table: market-research-tasks"
echo -e "Local API Gateway: http://localhost:8080"
echo -e "Kubernetes (Kind): Running"
echo -e "Kubeconfig: $(pwd)/local-dev/kubeconfig/kubeconfig.yaml"
echo -e "  export KUBECONFIG=$(pwd)/local-dev/kubeconfig/kubeconfig.yaml"
echo -e "  kubectl get pods"

echo -e "\nTo start the worker:
  export PYTHONPATH=$PYTHONPATH:$(pwd)
  python3 backend/app/worker.py"
echo -e "\nTo start the frontend:"
echo -e "  cd frontend && npm run dev"
