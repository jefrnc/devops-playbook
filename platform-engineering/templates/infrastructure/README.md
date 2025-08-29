# Infrastructure Templates

This directory contains reusable infrastructure modules and templates for platform resources.

## Available Modules

### Compute Resources
- **EKS Cluster**: Production-ready Kubernetes cluster
- **EC2 Auto-scaling**: Auto-scaling groups with load balancing
- **Lambda Functions**: Serverless compute templates
- **Container Services**: ECS/Fargate configurations

### Data Storage
- **RDS Instances**: Multi-AZ database setups
- **DynamoDB Tables**: NoSQL database configurations
- **S3 Buckets**: Object storage with lifecycle policies
- **ElastiCache**: Redis/Memcached clusters

### Networking
- **VPC**: Multi-tier VPC with public/private subnets
- **API Gateway**: REST and WebSocket APIs
- **CloudFront**: CDN distributions
- **Load Balancers**: ALB/NLB configurations

### Security
- **IAM Roles**: Least-privilege role templates
- **Security Groups**: Common security group patterns
- **KMS Keys**: Encryption key management
- **Secrets Manager**: Secret rotation configurations

## Usage

Each module includes:
- Terraform/CloudFormation templates
- Variable definitions
- Example usage
- Best practices documentation

## Standards

All infrastructure templates follow:
- Security best practices
- Cost optimization guidelines
- High availability patterns
- Monitoring and alerting setup

## Contributing

When adding new infrastructure templates:
1. Follow existing naming conventions
2. Include comprehensive documentation
3. Add cost estimation
4. Provide destroy/cleanup procedures