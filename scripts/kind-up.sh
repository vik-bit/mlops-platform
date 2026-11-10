#!/usr/bin/env bash
# Bring the whole platform up on a local Kind cluster.
#
#   scripts/kind-up.sh            # create cluster (if missing), build + load images, apply, wait
#   SKIP_BUILD=1 scripts/kind-up.sh   # reuse images already loaded into the cluster
#
# Needs: docker, kind, kubectl. Writes k8s/kind/secrets.env with random values the first time
# (gitignored). Host ports: gateway 18000, deployment 18003, frontend 13000, prometheus 19090.
set -euo pipefail
cd "$(dirname "$0")/.."

CLUSTER=${CLUSTER:-mlops}
DOCKER=${DOCKER:-docker}
KIND=${KIND:-kind}
SERVICES=(api-gateway dataset-service training-service deployment-service monitoring-service ai-service)

if [ ! -f k8s/kind/secrets.env ]; then
  rand() { python -c "import secrets; print(secrets.token_urlsafe(24))"; }
  {
    echo "POSTGRES_USER=mlops"
    echo "POSTGRES_PASSWORD=$(rand)"
    echo "JWT_SECRET_KEY=$(rand)"
    echo "ADMIN_PASSWORD=$(rand)"
  } > k8s/kind/secrets.env
  echo "wrote k8s/kind/secrets.env (random values; gitignored)"
fi

if ! "$KIND" get clusters | grep -qx "$CLUSTER"; then
  "$KIND" create cluster --name "$CLUSTER" --config k8s/kind/kind-config.yaml
fi
kubectl config use-context "kind-$CLUSTER" >/dev/null

if [ -z "${SKIP_BUILD:-}" ]; then
  for svc in "${SERVICES[@]}"; do
    dockerfile=backend/$svc/Dockerfile
    [ -f "$dockerfile" ] || dockerfile=backend/$svc/dockerfile
    "$DOCKER" build -q -t "mlops/$svc:dev" -f "$dockerfile" .
  done
  "$DOCKER" build -q -t mlops/frontend:dev \
    --build-arg NEXT_PUBLIC_API_BASE_URL=http://localhost:18000 frontend/vertex-ai-frontend
  for img in "${SERVICES[@]}" frontend; do
    "$KIND" load docker-image "mlops/$img:dev" --name "$CLUSTER"
  done
fi

kubectl apply -f k8s/kind/metrics-server.yaml
kubectl apply -k k8s/kind
# Pick up rebuilt :dev images (same tag) on re-runs.
kubectl -n mlops rollout restart deployment "${SERVICES[@]}" frontend >/dev/null
kubectl -n mlops rollout status statefulset/postgres --timeout=300s
for d in "${SERVICES[@]}" frontend redis mlflow prometheus; do
  kubectl -n mlops rollout status "deployment/$d" --timeout=600s
done
kubectl -n kube-system rollout status deployment/metrics-server --timeout=300s
kubectl -n mlops get pods -o wide
