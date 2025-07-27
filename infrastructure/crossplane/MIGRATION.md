# Migration Guide: Terraform to Crossplane

This guide helps you migrate from Terraform to Crossplane for managing DORA metrics infrastructure.

## Why Migrate to Crossplane?

### Benefits
- **Kubernetes-Native**: Use kubectl, RBAC, and GitOps workflows
- **Self-Service**: Enable developers with safe infrastructure provisioning
- **Continuous Reconciliation**: Automatic drift detection and correction
- **Unified API**: Single control plane for multi-cloud resources
- **Composable**: Build reusable infrastructure APIs

### Trade-offs
- Learning curve for Kubernetes concepts
- Smaller community compared to Terraform
- Fewer providers available
- Requires Kubernetes cluster for control plane

## Migration Strategy

### Phase 1: Assessment
1. Inventory existing Terraform resources
2. Identify Crossplane provider coverage
3. Plan migration order (start with non-critical)

### Phase 2: Parallel Running
1. Deploy Crossplane alongside Terraform
2. Import existing resources
3. Validate reconciliation

### Phase 3: Cutover
1. Switch to Crossplane management
2. Remove Terraform state
3. Archive Terraform code

## Resource Mapping

### Terraform to Crossplane Resources

| Terraform Resource | Crossplane Resource | Notes |
|-------------------|--------------------|---------|
| `aws_vpc` | `ec2.aws.upbound.io/v1beta1/VPC` | Direct mapping |
| `aws_subnet` | `ec2.aws.upbound.io/v1beta1/Subnet` | Direct mapping |
| `aws_eks_cluster` | `eks.aws.upbound.io/v1beta1/Cluster` | Includes OIDC provider |
| `aws_rds_instance` | `rds.aws.upbound.io/v1beta1/Instance` | Password in K8s secret |
| `aws_s3_bucket` | `s3.aws.upbound.io/v1beta1/Bucket` | Versioning supported |
| `azurerm_kubernetes_cluster` | `containerservice.azure.upbound.io/v1beta1/KubernetesCluster` | Direct mapping |
| `google_container_cluster` | `container.gcp.upbound.io/v1beta1/Cluster` | Direct mapping |

## Import Existing Resources

### Step 1: Annotate for Import

```yaml
apiVersion: ec2.aws.upbound.io/v1beta1
kind: VPC
metadata:
  name: existing-vpc
  annotations:
    crossplane.io/external-name: vpc-0123456789abcdef0
spec:
  forProvider:
    region: us-east-1
    cidrBlock: 10.0.0.0/16
    # ... match existing configuration
```

### Step 2: Apply and Observe

```bash
# Apply the resource
kubectl apply -f existing-vpc.yaml

# Check import status
kubectl get vpc existing-vpc -o yaml
```

### Step 3: Verify No Changes

```bash
# Ensure SYNCED and READY
kubectl get managed | grep vpc
```

## Example Migration

### Terraform Code
```hcl
# terraform/eks.tf
resource "aws_eks_cluster" "dora" {
  name     = "dora-metrics"
  role_arn = aws_iam_role.eks_cluster.arn
  version  = "1.28"

  vpc_config {
    subnet_ids = aws_subnet.private[*].id
  }

  tags = {
    Environment = "production"
    Platform    = "dora"
  }
}

resource "aws_rds_instance" "dora" {
  identifier     = "dora-metrics-db"
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = "db.t3.medium"
  
  allocated_storage = 100
  storage_type      = "gp3"
  
  db_name  = "dorametrics"
  username = "doraadmin"
  password = var.db_password
  
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.dora.name
  
  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  
  tags = {
    Environment = "production"
    Platform    = "dora"
  }
}
```

### Crossplane Composition
```yaml
# crossplane/dora-platform.yaml
apiVersion: platform.dora.io/v1alpha1
kind: DORAPlatform
metadata:
  name: dora-prod
spec:
  parameters:
    cloudProvider: aws
    region: us-east-1
    environment: production
    kubernetesVersion: "1.28"
    nodeCount: 3
    nodeSize: t3.medium
    databaseSize: db.t3.medium
    databaseStorage: 100
    enableHighAvailability: true
    enableBackup: true
    tags:
      Environment: production
      Platform: dora
```

## Migration Script

```bash
#!/bin/bash
# migrate-to-crossplane.sh

# Export Terraform state
terraform show -json > terraform-state.json

# Parse and generate Crossplane resources
python3 <<EOF
import json
import yaml

with open('terraform-state.json', 'r') as f:
    tf_state = json.load(f)

# Extract resource external IDs
resources = {}
for resource in tf_state.get('values', {}).get('root_module', {}).get('resources', []):
    if resource['type'] == 'aws_vpc':
        resources['vpc'] = resource['values']['id']
    elif resource['type'] == 'aws_eks_cluster':
        resources['eks'] = resource['values']['name']
    elif resource['type'] == 'aws_rds_instance':
        resources['rds'] = resource['values']['identifier']

# Generate Crossplane import manifests
for res_type, res_id in resources.items():
    print(f"Resource {res_type}: {res_id}")
    # Generate YAML with external-name annotation
EOF

# Import resources
for resource in *.yaml; do
  kubectl apply -f $resource
  kubectl wait --for=condition=Ready -f $resource --timeout=300s
done
```

## Validation Checklist

- [ ] All resources imported successfully
- [ ] No infrastructure changes detected
- [ ] Connection secrets accessible
- [ ] Applications still functioning
- [ ] Monitoring and alerts working
- [ ] Backup jobs running
- [ ] Cost allocation tags present

## Rollback Plan

1. **Keep Terraform state** safe until migration is verified
2. **Document external IDs** of all resources
3. **Test rollback** in development first

```bash
# Emergency rollback
kubectl delete doraplatform dora-prod
# Resources retain due to deletion policy
# Re-import to Terraform using documented IDs
```

## Common Issues

### Issue: Provider not ready
```bash
# Check provider status
kubectl get providers
kubectl describe provider provider-aws

# Check credentials
kubectl get secret aws-credentials -n crossplane-system
```

### Issue: Import fails
```bash
# Check external name
kubectl get vpc -o jsonpath='{.items[*].metadata.annotations.crossplane\.io/external-name}'

# Force reconciliation
kubectl annotate vpc existing-vpc crossplane.io/paused-
```

### Issue: Drift detected
```bash
# Compare configurations
kubectl get vpc existing-vpc -o yaml > current.yaml
# Compare with Terraform state

# Update Crossplane spec to match
kubectl edit vpc existing-vpc
```

## Best Practices

1. **Start small**: Migrate dev environment first
2. **Use compositions**: Don't manage individual resources
3. **Version everything**: Tag compositions and providers
4. **Monitor closely**: Watch for drift during transition
5. **Document external IDs**: Critical for rollback

## Tools and Scripts

### Terraform State Converter
```python
# tf-to-crossplane.py
import json
import yaml
import sys

def convert_vpc(tf_resource):
    return {
        'apiVersion': 'ec2.aws.upbound.io/v1beta1',
        'kind': 'VPC',
        'metadata': {
            'name': tf_resource['values']['tags']['Name'],
            'annotations': {
                'crossplane.io/external-name': tf_resource['values']['id']
            }
        },
        'spec': {
            'forProvider': {
                'region': tf_resource['values']['region'],
                'cidrBlock': tf_resource['values']['cidr_block'],
                'enableDnsHostnames': tf_resource['values']['enable_dns_hostnames'],
                'enableDnsSupport': tf_resource['values']['enable_dns_support'],
                'tags': tf_resource['values']['tags']
            }
        }
    }

# Usage: python3 tf-to-crossplane.py terraform.tfstate
```

## References

- [Crossplane Import Documentation](https://docs.crossplane.io/latest/concepts/managed-resources/#importing-existing-resources)
- [Provider AWS Reference](https://marketplace.upbound.io/providers/upbound/provider-aws)
- [Terraform State Documentation](https://developer.hashicorp.com/terraform/language/state)
