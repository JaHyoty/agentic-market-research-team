#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Stopping Local Environment...${NC}"

cd local-dev
docker-compose down

echo -e "${GREEN}Local Environment stopped.${NC}"
