# Crossplane Infrastructure as Code

Crossplane enables infrastructure provisioning using Kubernetes-native APIs, allowing you to manage cloud resources through standard Kubernetes tooling.

## Overview

This directory contains Crossplane configurations for provisioning infrastructure needed for DORA metrics collection across multiple cloud providers.

## Architecture

```
crossplane/
├── providers/          # Cloud provider configurations
├── compositions/       # XR compositions for reusable infrastructure
├── configurations/     # Packaged configurations
└── examples/          # Example claims for provisioning
```

## Key Benefits

- **Kubernetes-Native**: Manage infrastructure using kubectl, GitOps, and K8s RBAC
- **Multi-Cloud**: Single API for AWS, Azure, GCP, and more
- **Composable**: Build reusable infrastructure templates
- **Self-Service**: Enable developers to provision infrastructure safely
- **Drift Detection**: Automatic reconciliation of infrastructure state

## Installation

### 1. Install Crossplane

```bash
# Add Crossplane Helm repository
helm repo add crossplane-stable https://charts.crossplane.io/stable
helm repo update

# Install Crossplane
helm install crossplane \
  --namespace crossplane-system \
  --create-namespace \
  crossplane-stable/crossplane \
  --version 1.14.0

# Verify installation
kubectl get pods -n crossplane-system
kubectl get crds | grep crossplane
```

### 2. Install Providers

```bash
# Install AWS Provider
kubectl apply -f providers/provider-aws.yaml

# Install Azure Provider
kubectl apply -f providers/provider-azure.yaml

# Install GCP Provider
kubectl apply -f providers/provider-gcp.yaml

# Install Kubernetes Provider
kubectl apply -f providers/provider-kubernetes.yaml

# Wait for providers to be healthy
kubectl get providers
```

### 3. Configure Provider Credentials

#### AWS
```bash
# Create credentials file
cat > aws-credentials.txt <<EOF
[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY
EOF

# Create secret
kubectl create secret generic aws-credentials \
  -n crossplane-system \
  --from-file=credentials=aws-credentials.txt

# Apply ProviderConfig
kubectl apply -f providers/providerconfig-aws.yaml
```

#### Azure
```bash
# Create service principal
az ad sp create-for-rbac --sdk-auth > azure-credentials.json

# Create secret
kubectl create secret generic azure-credentials \
  -n crossplane-system \
  --from-file=credentials=azure-credentials.json

# Apply ProviderConfig
kubectl apply -f providers/providerconfig-azure.yaml
```

## Usage

### Provision DORA Metrics Infrastructure

```bash
# Create complete DORA metrics platform
kubectl apply -f examples/dora-platform-aws.yaml

# Check status
kubectl get doraplatform
kubectl describe doraplatform dora-prod
```

### Provision Individual Components

```bash
# Create just the monitoring stack
kubectl apply -f examples/monitoring-stack.yaml

# Create just the database
kubectl apply -f examples/database-claim.yaml
```

## Composition Reference

### DORADPlatform
Complete DORA metrics infrastructure including:
- VPC with public/private subnets
- EKS/AKS/GKE cluster
- RDS/CloudSQL database
- S3/Blob storage for backups
- IAM roles and policies
- Monitoring stack (Prometheus, Grafana)

### MonitoringStack
Observability infrastructure:
- Managed Prometheus
- Managed Grafana
- CloudWatch/Azure Monitor integration
- Alert routing

### Database
Managed database for metrics storage:
- Multi-AZ deployment
- Automated backups
- Read replicas
- Performance insights

## GitOps Integration

### With ArgoCD

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: crossplane-infra
  namespace: argocd
spec:
  source:
    repoURL: https://github.com/jefrnc/devops-playbook
    targetRevision: main
    path: infrastructure/crossplane/examples
  destination:
    server: https://kubernetes.default.svc
    namespace: default
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### With Flux

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: crossplane-infra
  namespace: flux-system
spec:
  interval: 10m
  path: ./infrastructure/crossplane/examples
  prune: true
  sourceRef:
    kind: GitRepository
    name: devops-playbook
```

## Best Practices

1. **Version Control**: Always version your compositions
2. **Least Privilege**: Use minimal IAM permissions
3. **Resource Tagging**: Tag all resources for cost tracking
4. **Deletion Protection**: Enable for production databases
5. **Backup Strategy**: Automate backups before updates

## Troubleshooting

### Check Provider Status
```bash
kubectl get providers
kubectl describe provider provider-aws
```

### View Managed Resources
```bash
kubectl get managed
kubectl get managed -o wide
```

### Debug Composition
```bash
kubectl describe composition dora-platform
kubectl get composite -o wide
```

### Common Issues

1. **Provider not ready**: Check credentials and IAM permissions
2. **Resource stuck**: Check AWS/Azure console for manual changes
3. **Composition invalid**: Validate with `kubectl explain`

## Migration from Terraform

See [migration guide](./MIGRATION.md) for moving from Terraform to Crossplane.

## References

- [Crossplane Documentation](https://docs.crossplane.io/)
- [Provider AWS](https://marketplace.upbound.io/providers/crossplane-contrib/provider-aws)
- [Provider Azure](https://marketplace.upbound.io/providers/upbound/provider-azure)
- [Provider GCP](https://marketplace.upbound.io/providers/upbound/provider-gcp)