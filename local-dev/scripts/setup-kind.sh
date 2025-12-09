#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

KUBECONFIG_FILE="$(dirname "$0")/../kubeconfig/kubeconfig.yaml"
export KUBECONFIG="$KUBECONFIG_FILE"

echo -e "${BLUE}Setting up Kind Cluster...${NC}"

# Wait for cluster readiness (basic check)
echo "Waiting for nodes to be ready..."
kubectl wait --for=condition=Ready nodes --all --timeout=60s

# Install KEDA
echo "Installing KEDA..."
kubectl apply --server-side --force-conflicts -f https://github.com/kedacore/keda/releases/download/v2.12.0/keda-2.12.0.yaml

# Wait for KEDA operator
echo "Waiting for KEDA operator..."
kubectl wait --for=condition=Available deployment/keda-operator -n keda --timeout=300s

# Patch KEDA with LocalStack credentials (as was done in start-k3s.sh)
echo "Patching KEDA operator with LocalStack credentials..."
kubectl set env deployment/keda-operator -n keda \
    AWS_ACCESS_KEY_ID=test \
    AWS_SECRET_ACCESS_KEY=test \
    AWS_REGION=us-east-1

# Install Karpenter CRDs
echo "Installing Karpenter CRDs..."
kubectl apply --server-side --force-conflicts -f https://raw.githubusercontent.com/aws/karpenter-provider-aws/v0.32.1/pkg/apis/crds/karpenter.sh_nodepools.yaml
kubectl apply --server-side --force-conflicts -f https://raw.githubusercontent.com/aws/karpenter-provider-aws/v0.32.1/pkg/apis/crds/karpenter.k8s.aws_ec2nodeclasses.yaml
kubectl apply --server-side --force-conflicts -f https://raw.githubusercontent.com/aws/karpenter-provider-aws/v0.32.1/pkg/apis/crds/karpenter.sh_nodeclaims.yaml

echo -e "${GREEN}Cluster Setup Complete!${NC}"
