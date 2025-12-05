#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting Local Environment...${NC}"

# 1. Start Docker Services
echo -e "${GREEN}Starting Docker Compose services (LocalStack, DynamoDB)...${NC}"
cd local-dev
docker-compose up -d
cd ..

# 2. Wait for services to be ready
echo -e "${GREEN}Waiting for services to be ready...${NC}"
echo "Waiting for LocalStack..."
count=0
until curl -s http://localhost:4566/_localstack/health | grep "\"s3\": \"running\"" > /dev/null; do
    sleep 2
    echo -n "."
    count=$((count + 1))
    if [ $count -gt 30 ]; then
        echo -e "\nLocalStack S3 is failing to start."
        exit 1
    fi
done
echo -e "\nLocalStack S3 is ready."
echo "Waiting for init scripts to complete..."
sleep 5

echo "Waiting for DynamoDB Local..."
# Simple check if port is open
count=0
while ! nc -z localhost 8000; do   
  sleep 1
  echo -n "."
  count=$((count + 1))
  if [ $count -gt 30 ]; then
    echo -e "\nDynamoDB Local is failing to start."
    exit 1
  fi
done
echo -e "\nDynamoDB Local is ready."

# 3. Initialize Resources
echo -e "${GREEN}Initializing Resources...${NC}"

# LocalStack init script runs automatically on container start, but we can verify or run extra steps here if needed.
# The 01-setup.sh in init-scripts/ is mounted and run by LocalStack itself.

# Create DynamoDB Table
echo "Creating DynamoDB tables..."
export PYTHONPATH=$PYTHONPATH:$(pwd)
if [ -d "venv" ]; then
    source venv/bin/activate
fi
python3 local-dev/create_table.py

# 4. Verify Environment
echo -e "${GREEN}Verifying Environment...${NC}"
python3 local-dev/verify_env.py

echo -e "${BLUE}Local Environment is UP and READY!${NC}"
echo -e "S3 Buckets: market-research-artifacts, market-research-reports"
echo -e "SQS Queue: market-research-tasks"
echo -e "DynamoDB Table: market-research-tasks"
echo -e "\nTo start the backend:"
echo -e "  uvicorn backend.app.api:app --reload --port 8080"
echo -e "  python3 backend/app/worker.py"
echo -e "\nTo start the frontend:"
echo -e "  cd frontend && npm run dev"
