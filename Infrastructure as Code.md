# Infrastructure as Code (IaC)

In this section, we explain how to use tools like Pulumi and Terraform to create infrastructure as code. We also cover configuration management tools like Ansible and best practices for managing infrastructure code.

## What is Infrastructure as Code?

Infrastructure as Code (IaC) is the practice of managing and provisioning computing infrastructure through machine-readable definition files, rather than physical hardware configuration or interactive configuration tools. This approach brings many of the benefits of software development practices to infrastructure management.

## Key Benefits of IaC

- **Consistency**: Eliminate configuration drift and ensure environments are identical
- **Speed**: Provision infrastructure in minutes instead of days or weeks
- **Version Control**: Track changes, review history, and rollback when needed
- **Collaboration**: Teams can review and contribute to infrastructure changes
- **Cost Optimization**: Easily spin up and tear down environments as needed
- **Documentation**: The code itself serves as documentation of your infrastructure

## IaC Principles

1. **Declarative vs Imperative**
   - **Declarative**: Describe the desired end state (Terraform, Pulumi, CloudFormation)
   - **Imperative**: Specify the exact steps to achieve the desired state (Ansible, Chef)

2. **Idempotency**
   - Running the same configuration multiple times produces the same result
   - Prevents unintended changes and ensures predictability

3. **Immutability**
   - Infrastructure is replaced rather than changed
   - Reduces configuration drift and improves reliability

## Pulumi: Modern Infrastructure as Code

Pulumi is a modern infrastructure as code platform that allows you to use familiar programming languages to define, deploy, and manage cloud infrastructure. Unlike traditional IaC tools that use domain-specific languages, Pulumi lets you use languages like TypeScript, Python, Go, and C#.

### Why Pulumi?

- **Real Programming Languages**: Use loops, conditionals, functions, and classes
- **Strong Typing**: Catch errors at compile time with IDE support
- **Reusable Components**: Create and share infrastructure components as packages
- **Multi-Cloud**: Support for AWS, Azure, GCP, Kubernetes, and 60+ providers
- **Secrets Management**: Built-in encryption for sensitive configuration
- **State Management**: Automatic state tracking and management

### Getting Started with Pulumi

**Installation:**
```bash
# macOS
brew install pulumi

# Linux
curl -fsSL https://get.pulumi.com | sh

# Windows
choco install pulumi
```

**Basic Pulumi Project Structure:**
```
my-infrastructure/
├── Pulumi.yaml          # Project metadata
├── Pulumi.dev.yaml      # Stack-specific configuration
├── Pulumi.prod.yaml     # Production configuration
├── index.ts             # Main program file
├── package.json         # Node.js dependencies
└── tsconfig.json        # TypeScript configuration
```

### Pulumi Examples

**Example 1: Creating an S3 Bucket with Website Hosting (TypeScript)**
```typescript
import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";

// Create an S3 bucket configured as a website
const siteBucket = new aws.s3.Bucket("my-website", {
    website: {
        indexDocument: "index.html",
        errorDocument: "404.html",
    },
});

// Configure public access block
const publicAccessBlock = new aws.s3.BucketPublicAccessBlock("public-access-block", {
    bucket: siteBucket.id,
    blockPublicAcls: false,
    blockPublicPolicy: false,
    ignorePublicAcls: false,
    restrictPublicBuckets: false,
});

// Create a bucket policy to allow public read access
const bucketPolicy = new aws.s3.BucketPolicy("bucket-policy", {
    bucket: siteBucket.id,
    policy: siteBucket.id.apply(bucketName => JSON.stringify({
        Version: "2012-10-17",
        Statement: [{
            Effect: "Allow",
            Principal: "*",
            Action: ["s3:GetObject"],
            Resource: [`arn:aws:s3:::${bucketName}/*`],
        }],
    })),
}, { dependsOn: [publicAccessBlock] });

// Upload website content
const indexHtml = new aws.s3.BucketObject("index.html", {
    bucket: siteBucket,
    source: new pulumi.asset.FileAsset("./website/index.html"),
    contentType: "text/html",
});

// Export the website URL
export const websiteUrl = siteBucket.websiteEndpoint;
```

**Example 2: Kubernetes Deployment with Pulumi (Python)**
```python
import pulumi
from pulumi_kubernetes import Provider, apps, core

# Create a Kubernetes provider
k8s_provider = Provider("k8s", kubeconfig=kubeconfig)

# Define the application
app_labels = {"app": "nginx"}

# Create a Namespace
namespace = core.v1.Namespace(
    "app-namespace",
    metadata={"name": "production"},
    opts=pulumi.ResourceOptions(provider=k8s_provider)
)

# Create a Deployment
deployment = apps.v1.Deployment(
    "nginx-deployment",
    metadata={
        "namespace": namespace.metadata["name"],
        "name": "nginx-deployment"
    },
    spec={
        "replicas": 3,
        "selector": {"matchLabels": app_labels},
        "template": {
            "metadata": {"labels": app_labels},
            "spec": {
                "containers": [{
                    "name": "nginx",
                    "image": "nginx:1.21",
                    "ports": [{"containerPort": 80}],
                    "resources": {
                        "requests": {
                            "cpu": "100m",
                            "memory": "128Mi"
                        },
                        "limits": {
                            "cpu": "200m",
                            "memory": "256Mi"
                        }
                    }
                }]
            }
        }
    },
    opts=pulumi.ResourceOptions(provider=k8s_provider)
)

# Create a Service
service = core.v1.Service(
    "nginx-service",
    metadata={
        "namespace": namespace.metadata["name"],
        "name": "nginx-service"
    },
    spec={
        "type": "LoadBalancer",
        "selector": app_labels,
        "ports": [{"port": 80, "targetPort": 80}]
    },
    opts=pulumi.ResourceOptions(provider=k8s_provider)
)

# Export the service endpoint
pulumi.export("service_endpoint", service.status["load_balancer"]["ingress"][0]["hostname"])
```

**Example 3: Multi-Cloud Infrastructure with Pulumi (Go)**
```go
package main

import (
    "github.com/pulumi/pulumi-aws/sdk/v5/go/aws/ec2"
    "github.com/pulumi/pulumi-azure-native/sdk/go/azure/compute"
    "github.com/pulumi/pulumi-azure-native/sdk/go/azure/network"
    "github.com/pulumi/pulumi-azure-native/sdk/go/azure/resources"
    "github.com/pulumi/pulumi/sdk/v3/go/pulumi"
)

func main() {
    pulumi.Run(func(ctx *pulumi.Context) error {
        // AWS Resources
        // Create VPC
        vpc, err := ec2.NewVpc(ctx, "main", &ec2.VpcArgs{
            CidrBlock: pulumi.String("10.0.0.0/16"),
            Tags: pulumi.StringMap{
                "Name": pulumi.String("main-vpc"),
            },
        })
        if err != nil {
            return err
        }

        // Create Subnet
        subnet, err := ec2.NewSubnet(ctx, "main", &ec2.SubnetArgs{
            VpcId:     vpc.ID(),
            CidrBlock: pulumi.String("10.0.1.0/24"),
            Tags: pulumi.StringMap{
                "Name": pulumi.String("main-subnet"),
            },
        })
        if err != nil {
            return err
        }

        // Azure Resources
        // Create Resource Group
        resourceGroup, err := resources.NewResourceGroup(ctx, "main", &resources.ResourceGroupArgs{
            Location: pulumi.String("East US"),
        })
        if err != nil {
            return err
        }

        // Create Virtual Network
        virtualNetwork, err := network.NewVirtualNetwork(ctx, "main", &network.VirtualNetworkArgs{
            ResourceGroupName: resourceGroup.Name,
            Location:          resourceGroup.Location,
            AddressSpace: &network.AddressSpaceArgs{
                AddressPrefixes: pulumi.StringArray{
                    pulumi.String("10.1.0.0/16"),
                },
            },
        })
        if err != nil {
            return err
        }

        // Export the IDs
        ctx.Export("awsVpcId", vpc.ID())
        ctx.Export("awsSubnetId", subnet.ID())
        ctx.Export("azureVnetId", virtualNetwork.ID())

        return nil
    })
}
```

**Example 4: Component Resources - Reusable Infrastructure Patterns**
```typescript
import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";

// Define a reusable web server component
class WebServerStack extends pulumi.ComponentResource {
    public readonly instanceId: pulumi.Output<string>;
    public readonly publicIp: pulumi.Output<string>;
    public readonly publicDns: pulumi.Output<string>;

    constructor(name: string, args: WebServerArgs, opts?: pulumi.ComponentResourceOptions) {
        super("custom:app:WebServerStack", name, {}, opts);

        // Create security group
        const securityGroup = new aws.ec2.SecurityGroup(`${name}-sg`, {
            description: "Enable HTTP and SSH access",
            ingress: [
                { protocol: "tcp", fromPort: 80, toPort: 80, cidrBlocks: ["0.0.0.0/0"] },
                { protocol: "tcp", fromPort: 22, toPort: 22, cidrBlocks: ["0.0.0.0/0"] },
            ],
            egress: [
                { protocol: "-1", fromPort: 0, toPort: 0, cidrBlocks: ["0.0.0.0/0"] },
            ],
        }, { parent: this });

        // Create EC2 instance
        const server = new aws.ec2.Instance(`${name}-instance`, {
            instanceType: args.instanceType || "t2.micro",
            ami: args.ami,
            keyName: args.keyName,
            vpcSecurityGroupIds: [securityGroup.id],
            userData: args.userData,
            tags: {
                Name: `${name}-webserver`,
                Environment: args.environment,
            },
        }, { parent: this });

        // Create Elastic IP
        const eip = new aws.ec2.Eip(`${name}-eip`, {
            instance: server.id,
        }, { parent: this });

        this.instanceId = server.id;
        this.publicIp = eip.publicIp;
        this.publicDns = server.publicDns;

        this.registerOutputs({
            instanceId: this.instanceId,
            publicIp: this.publicIp,
            publicDns: this.publicDns,
        });
    }
}

interface WebServerArgs {
    ami: pulumi.Input<string>;
    instanceType?: pulumi.Input<string>;
    keyName: pulumi.Input<string>;
    userData?: pulumi.Input<string>;
    environment: pulumi.Input<string>;
}

// Use the component
const devServer = new WebServerStack("dev", {
    ami: "ami-0c55b159cbfafe1f0",
    keyName: "my-key-pair",
    environment: "development",
    userData: `#!/bin/bash
        yum update -y
        yum install -y httpd
        systemctl start httpd
        systemctl enable httpd
        echo "<h1>Welcome to our Infrastructure!</h1>" > /var/www/html/index.html
    `,
});

export const devServerIp = devServer.publicIp;
export const devServerDns = devServer.publicDns;
```

## Terraform: HashiCorp's Infrastructure as Code

Terraform is one of the most popular IaC tools, using HashiCorp Configuration Language (HCL) to define infrastructure.

### Key Features

- **Declarative Configuration**: Define what you want, not how to build it
- **Provider Ecosystem**: Support for hundreds of cloud and service providers
- **State Management**: Tracks the current state of your infrastructure
- **Plan and Apply**: Preview changes before applying them
- **Modules**: Reusable infrastructure components

### Basic Terraform Example

```hcl
# Configure the AWS Provider
provider "aws" {
  region = "us-west-2"
}

# Create a VPC
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
  
  tags = {
    Name = "main-vpc"
  }
}

# Create a subnet
resource "aws_subnet" "main" {
  vpc_id     = aws_vpc.main.id
  cidr_block = "10.0.1.0/24"

  tags = {
    Name = "main-subnet"
  }
}

# Create an internet gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "main-igw"
  }
}

# Create an EC2 instance
resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t2.micro"
  subnet_id     = aws_subnet.main.id

  tags = {
    Name = "web-server"
  }
}

# Output the public IP
output "instance_ip" {
  value = aws_instance.web.public_ip
}
```

## Configuration Management with Ansible

While Terraform and Pulumi excel at provisioning infrastructure, Ansible is perfect for configuring and managing that infrastructure once it's created.

### Ansible Example: Configure Web Servers

```yaml
---
- name: Configure web servers
  hosts: webservers
  become: yes
  
  tasks:
    - name: Install nginx
      package:
        name: nginx
        state: present
    
    - name: Start and enable nginx
      service:
        name: nginx
        state: started
        enabled: yes
    
    - name: Deploy website content
      template:
        src: templates/index.html.j2
        dest: /var/www/html/index.html
        owner: nginx
        group: nginx
        mode: '0644'
    
    - name: Configure nginx
      template:
        src: templates/nginx.conf.j2
        dest: /etc/nginx/nginx.conf
        backup: yes
      notify: restart nginx
  
  handlers:
    - name: restart nginx
      service:
        name: nginx
        state: restarted
```

## Best Practices for Infrastructure as Code

1. **Version Control Everything**
   - Store all IaC files in Git
   - Use meaningful commit messages
   - Tag releases and infrastructure versions
   - Review changes through pull requests

2. **Use Remote State**
   - Store Terraform state in S3, Azure Storage, or Terraform Cloud
   - Enable state locking to prevent concurrent modifications
   - Encrypt sensitive state data

3. **Modularize Your Code**
   - Create reusable modules for common patterns
   - Use variables for configuration
   - Keep modules small and focused
   - Document module inputs and outputs

4. **Test Your Infrastructure**
   - Use tools like Terratest for automated testing
   - Validate configurations before applying
   - Test in non-production environments first
   - Implement smoke tests after deployment

5. **Implement Security Best Practices**
   - Never hardcode secrets in IaC files
   - Use secret management services (AWS Secrets Manager, HashiCorp Vault)
   - Implement least privilege access
   - Enable audit logging for infrastructure changes

6. **Plan for Disaster Recovery**
   - Document recovery procedures
   - Test infrastructure rebuilds regularly
   - Maintain backups of critical state
   - Consider multi-region deployments

## Getting Started with IaC

1. **Choose Your Tool**
   - Evaluate based on team skills and requirements
   - Consider multi-cloud needs
   - Factor in existing tooling and workflows

2. **Start Small**
   - Begin with non-critical infrastructure
   - Learn the tool's concepts and best practices
   - Build confidence through small wins

3. **Establish Standards**
   - Define naming conventions
   - Create coding standards
   - Document architectural decisions
   - Set up code review processes

4. **Automate Gradually**
   - Move existing infrastructure to IaC incrementally
   - Focus on new projects first
   - Document manual processes before automating

5. **Monitor and Iterate**
   - Track deployment success rates
   - Monitor infrastructure drift
   - Gather team feedback
   - Continuously improve processes

---

[Back to Main README](./README.md)
