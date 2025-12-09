#!/bin/bash
set -e

SCRIPT_DIR=$(dirname "$0")
PROJECT_ROOT="$SCRIPT_DIR/../.."

# 1. Deploy latest worker code
echo "Deploying latest worker..."
cd "$PROJECT_ROOT"
./deploy.sh local

# 2. Trigger a task
echo "Triggering a new task..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi
export AWS_ENDPOINT_URL=http://localhost:4566
export SQS_QUEUE_URL=http://localhost:4566/000000000000/market-research-tasks
python3 local-dev/trigger_task.py

# 3. Monitor scaling
echo "Monitoring worker pods (KEDA should scale up)..."
echo "Press Ctrl+C to stop watching."

# Ensure we use local kubeconfig
export KUBECONFIG=local-dev/kubeconfig/kubeconfig.yaml

# Watch pods
kubectl get pods -l app=market-research-worker -w
