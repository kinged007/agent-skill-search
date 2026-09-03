---
name: deploy-k8s
description: "Deploy applications to Kubernetes: manifests, Helm charts, health checks, resource limits, rolling updates, and rollback procedures."
metadata:
  hermes:
    category: devops
---

# Kubernetes Deployment

## When to Use
When deploying, scaling, or troubleshooting applications on Kubernetes.

## Procedure
1. Create Deployment manifest with proper labels
2. Configure liveness and readiness probes
3. Set resource requests and limits
4. Use Helm charts for templated deployments
5. Implement rolling update strategy
6. Verify with `kubectl get pods` and `kubectl logs`
