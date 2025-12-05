#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Stopping Local Environment...${NC}"

cd local-dev
docker-compose down

# Stop Local API Gateway
# No need to kill manually, docker-compose down handles it.
rm -f local-dev/api_gateway.pid

echo -e "${GREEN}Local Environment stopped.${NC}"
