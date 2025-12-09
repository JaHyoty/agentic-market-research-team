#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CLUSTER_NAME="agentic-cluster"
KIND_CONFIG="$(dirname "$0")/../kind-config.yaml"
KUBECONFIG_DIR="$(dirname "$0")/../kubeconfig"
KUBECONFIG_FILE="$KUBECONFIG_DIR/kubeconfig.yaml"

echo -e "${BLUE}Starting Kind Cluster: $CLUSTER_NAME...${NC}"

# Ensure kubeconfig directory exists
mkdir -p "$KUBECONFIG_DIR"

# Check if cluster exists
if ! kind get clusters | grep -q "^$CLUSTER_NAME$"; then
    echo "Creating cluster..."
    kind create cluster --name "$CLUSTER_NAME" --config "$KIND_CONFIG"
    echo -e "${GREEN}Cluster created.${NC}"
else
    echo -e "${GREEN}Cluster $CLUSTER_NAME already exists.${NC}"
fi

# Connect Kind nodes to local-dev network
echo "Connecting Kind nodes to local-dev_default network..."
NODES=$(kind get nodes --name "$CLUSTER_NAME")
for node in $NODES; do
    if ! docker network inspect local-dev_default | grep -q "$node"; then
        docker network connect local-dev_default "$node" || true 
        echo "Connected $node to local-dev_default"
    else
         echo "$node is already connected to local-dev_default"
    fi
done

# Export Kubeconfig
echo "Exporting Kubeconfig..."
rm -f "$KUBECONFIG_FILE"
kind get kubeconfig --name "$CLUSTER_NAME" > "$KUBECONFIG_FILE"
chmod 600 "$KUBECONFIG_FILE"

echo -e "${GREEN}Kind Cluster is Ready!${NC}"
echo "Kubeconfig saved to: $KUBECONFIG_FILE"
