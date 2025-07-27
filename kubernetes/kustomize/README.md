# Kustomize Templates for DORA Metrics

This directory contains Kustomize templates for deploying DORA metrics collection and visualization platform in Kubernetes.

## Directory Structure

```
kustomize/
├── base/                    # Base configurations
│   ├── configs/             # Metric configuration files
│   ├── kustomization.yaml   # Base kustomization
│   ├── namespace.yaml       # Namespace definition
│   ├── rbac.yaml           # RBAC configurations
│   ├── deployment.yaml     # Base deployments
│   ├── service.yaml        # Service definitions
│   └── ...
├── overlays/
│   ├── development/         # Development environment
│   ├── staging/            # Staging environment
│   └── production/         # Production environment
└── components/              # Reusable components
    ├── monitoring/         # Monitoring integrations
    ├── security/           # Security policies
    └── backup/             # Backup configurations
```

## Quick Start

### Development Deployment

```bash
# Preview the generated manifests
kubectl kustomize overlays/development

# Apply to cluster
kubectl apply -k overlays/development

# Watch the deployment
kubectl -n dora-dev get pods -w
```

### Production Deployment

```bash
# Preview with production settings
kubectl kustomize overlays/production

# Apply with dry-run first
kubectl apply -k overlays/production --dry-run=client

# Deploy to production
kubectl apply -k overlays/production
```

## Environment-Specific Configurations

### Development
- Single replica deployments
- Debug logging enabled
- Relaxed security policies
- NodePort services for easy access
- In-memory storage for testing

### Production
- High availability with 3+ replicas
- Anti-affinity rules for pod distribution
- Strict security policies and network policies
- LoadBalancer services with SSL
- Persistent storage with PostgreSQL
- Automated backups
- Prometheus monitoring integration

## Customization Guide

### Adding a New Environment

1. Create a new overlay directory:
```bash
mkdir -p overlays/custom-env
```

2. Create kustomization.yaml:
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

bases:
  - ../../base

namePrefix: custom-
namespace: dora-custom

patches:
  - deployment-patch.yaml
```

### Modifying Resource Limits

Edit the overlay's kustomization.yaml:
```yaml
patches:
  - target:
      kind: Deployment
      name: dora-operator
    patch: |-
      - op: replace
        path: /spec/template/spec/containers/0/resources
        value:
          limits:
            cpu: 4000m
            memory: 4Gi
          requests:
            cpu: 1000m
            memory: 2Gi
```

### Adding Custom Metrics

1. Create a new config file in base/configs/
2. Update base/kustomization.yaml to include it
3. Configure the metric collection in your overlay

## Integration with CI/CD

### GitOps with ArgoCD

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: dora-metrics-prod
  namespace: argocd
spec:
  source:
    repoURL: https://github.com/jefrnc/devops-playbook
    targetRevision: main
    path: kubernetes/kustomize/overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: dora-production
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### GitHub Actions Deployment

```yaml
- name: Deploy with Kustomize
  run: |
    kubectl kustomize overlays/${{ env.ENVIRONMENT }} | \
    kubectl apply -f -
```

## Managing Secrets

### Using Sealed Secrets

```bash
# Create a secret
echo -n 'your-token' | \
kubeseal --raw --scope cluster-wide --controller-name sealed-secrets | \
tee overlays/production/secrets/github-token.encrypted
```

### Using External Secrets Operator

```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault-backend
spec:
  provider:
    vault:
      server: "https://vault.example.com"
      path: "secret"
      version: "v2"
```

## Validation and Testing

### Validate Kustomization

```bash
# Validate base
kustomize build base | kubectl apply --dry-run=client -f -

# Validate overlays
for env in development staging production; do
  echo "Validating $env..."
  kustomize build overlays/$env | kubectl apply --dry-run=client -f -
done
```

### Test with Kind

```bash
# Create a test cluster
kind create cluster --name dora-test

# Deploy development overlay
kubectl apply -k overlays/development

# Port forward for testing
kubectl port-forward -n dora-dev svc/dev-dora-operator 8080:8080
```

## Troubleshooting

### Common Issues

1. **Image not found**: Update image tags in overlay kustomization.yaml
2. **Permission denied**: Check RBAC configuration
3. **Service unreachable**: Verify network policies
4. **High memory usage**: Adjust resource limits

### Debug Commands

```bash
# View generated manifests
kubectl kustomize overlays/production > debug-output.yaml

# Check kustomize version
kustomize version

# List all resources
kubectl api-resources --verbs=list --namespaced -o name | \
  xargs -n 1 kubectl get --show-kind --ignore-not-found -n dora-production
```

## Best Practices

1. **Never edit base files directly** - Use overlays for environment-specific changes
2. **Use components** for reusable features across environments
3. **Version your images** explicitly in production
4. **Test in development** before applying to production
5. **Use GitOps** for production deployments
6. **Enable audit logging** for compliance

## References

- [Kustomize Documentation](https://kustomize.io/)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)
- [DORA Metrics Guide](https://dora.dev/)
