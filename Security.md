# Security in DevOps (DevSecOps)

In this section, we cover best practices for securing your applications and infrastructure. We discuss network security, identity and access management, and encryption. We also cover security testing and compliance.

## DevSecOps: Integrating Security into DevOps

DevSecOps is the practice of integrating security into every phase of the software development lifecycle. Rather than treating security as a separate phase or an afterthought, DevSecOps makes it a shared responsibility across the entire team.

## Key Security Principles

1. **Shift Left Security**: Move security testing and validation earlier in the development process
2. **Defense in Depth**: Multiple layers of security controls throughout the stack
3. **Least Privilege**: Grant minimum necessary permissions
4. **Zero Trust**: Never trust, always verify
5. **Continuous Security**: Automated security testing and monitoring

## Security in the CI/CD Pipeline

### Static Application Security Testing (SAST)

SAST analyzes source code for security vulnerabilities without executing the program.

**Example: Integrating SAST with GitHub Actions**
```yaml
name: Security Scan

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  security:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    # JavaScript/TypeScript Security Scan
    - name: Run ESLint Security Plugin
      run: |
        npm install --save-dev eslint-plugin-security
        npx eslint --ext .js,.ts --plugin security --rule 'security/detect-object-injection: error' .
    
    # Python Security Scan with Bandit
    - name: Run Bandit Security Scan
      uses: gaurav-nelson/bandit-action@v1
      with:
        path: "."
        level: "medium"
        confidence: "medium"
        exit_zero: false
    
    # General purpose security scanning with Semgrep
    - name: Semgrep Security Scan
      uses: returntocorp/semgrep-action@v1
      with:
        config: >-
          p/security-audit
          p/secrets
          p/owasp-top-ten
    
    # Dependency vulnerability scanning
    - name: Run Snyk to check for vulnerabilities
      uses: snyk/actions/node@master
      env:
        SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
      with:
        args: --severity-threshold=high
```

### Dynamic Application Security Testing (DAST)

DAST tests running applications for security vulnerabilities.

**Example: OWASP ZAP in CI/CD Pipeline**
```yaml
name: DAST Scan

on:
  schedule:
    - cron: '0 2 * * *'  # Run daily at 2 AM
  workflow_dispatch:

jobs:
  dast:
    runs-on: ubuntu-latest
    
    steps:
    - name: Deploy to Test Environment
      run: |
        # Deploy application to test environment
        echo "Deploying application..."
    
    - name: OWASP ZAP Baseline Scan
      uses: zaproxy/action-baseline@v0.7.0
      with:
        target: 'https://test.mycompany.com'
        rules_file_name: '.zap/rules.tsv'
        cmd_options: '-a -j -l WARN'
    
    - name: Upload ZAP Report
      uses: actions/upload-artifact@v3
      with:
        name: zap-report
        path: report_html.html
```

## Container Security

### Dockerfile Security Best Practices

```dockerfile
# Use specific version tags, not latest
FROM node:18.17.0-alpine AS builder

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001

# Set working directory
WORKDIR /app

# Copy only package files first (better caching)
COPY package*.json ./

# Install dependencies as root (needed for some packages)
RUN npm ci --only=production && \
    npm cache clean --force

# Copy application files
COPY --chown=nodejs:nodejs . .

# Switch to non-root user
USER nodejs

# Use specific port
EXPOSE 3000

# Security headers
ENV NODE_ENV=production

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node healthcheck.js

# Run with limited privileges
CMD ["node", "--max-old-space-size=256", "server.js"]
```

### Container Image Scanning

**Example: Trivy Integration**
```yaml
name: Container Security Scan

on:
  push:
    branches: [ main ]
    paths:
      - 'Dockerfile'
      - 'package*.json'

jobs:
  scan:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Build Docker Image
      run: docker build -t myapp:${{ github.sha }} .
    
    - name: Run Trivy vulnerability scanner
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: 'myapp:${{ github.sha }}'
        format: 'sarif'
        output: 'trivy-results.sarif'
        severity: 'CRITICAL,HIGH'
        exit-code: '1'
    
    - name: Upload Trivy scan results to GitHub Security tab
      uses: github/codeql-action/upload-sarif@v2
      if: always()
      with:
        sarif_file: 'trivy-results.sarif'
    
    - name: Scan with Grype
      uses: anchore/scan-action@v3
      with:
        image: 'myapp:${{ github.sha }}'
        fail-build: true
        severity-cutoff: high
```

## Kubernetes Security

### Pod Security Standards

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secure-pod
  namespace: production
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 2000
    seccompProfile:
      type: RuntimeDefault
  
  containers:
  - name: app
    image: myapp:1.0.0
    imagePullPolicy: Always
    
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      runAsNonRoot: true
      runAsUser: 1000
      capabilities:
        drop:
          - ALL
        add:
          - NET_BIND_SERVICE
    
    resources:
      requests:
        memory: "128Mi"
        cpu: "100m"
      limits:
        memory: "256Mi"
        cpu: "200m"
    
    volumeMounts:
    - name: tmp
      mountPath: /tmp
    - name: cache
      mountPath: /app/cache
    
    livenessProbe:
      httpGet:
        path: /health
        port: 8080
      initialDelaySeconds: 30
      periodSeconds: 10
    
    readinessProbe:
      httpGet:
        path: /ready
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 5
  
  volumes:
  - name: tmp
    emptyDir: {}
  - name: cache
    emptyDir: {}
```

### Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-network-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Ingress
  - Egress
  
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: production
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 8080
  
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: production
    - podSelector:
        matchLabels:
          app: database
    ports:
    - protocol: TCP
      port: 5432
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
    - podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
```

### RBAC Configuration

```yaml
# ServiceAccount
apiVersion: v1
kind: ServiceAccount
metadata:
  name: app-service-account
  namespace: production
---
# Role with minimal permissions
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: app-role
  namespace: production
rules:
- apiGroups: [""]
  resources: ["configmaps"]
  resourceNames: ["app-config"]
  verbs: ["get", "watch"]
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["app-secrets"]
  verbs: ["get"]
---
# RoleBinding
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: app-role-binding
  namespace: production
subjects:
- kind: ServiceAccount
  name: app-service-account
  namespace: production
roleRef:
  kind: Role
  name: app-role
  apiGroup: rbac.authorization.k8s.io
```

## Secrets Management

### HashiCorp Vault Integration

**Vault Configuration:**
```hcl
# Enable KV v2 secrets engine
path "secret/data/myapp/*" {
  capabilities = ["read", "list"]
}

# Database secret engine
path "database/creds/myapp-db" {
  capabilities = ["read"]
}

# PKI secret engine for TLS certificates
path "pki/issue/myapp" {
  capabilities = ["create", "update"]
}
```

**Application Integration Example (Node.js):**
```javascript
const vault = require('node-vault')({
  endpoint: process.env.VAULT_ADDR,
  token: process.env.VAULT_TOKEN,
});

async function getSecrets() {
  try {
    // Get static secrets
    const staticSecrets = await vault.read('secret/data/myapp/config');
    
    // Get dynamic database credentials
    const dbCreds = await vault.read('database/creds/myapp-db');
    
    // Get TLS certificate
    const cert = await vault.write('pki/issue/myapp', {
      common_name: 'myapp.mycompany.com',
      ttl: '720h',
    });
    
    return {
      config: staticSecrets.data.data,
      database: {
        username: dbCreds.data.username,
        password: dbCreds.data.password,
      },
      tls: {
        certificate: cert.data.certificate,
        private_key: cert.data.private_key,
        ca_chain: cert.data.ca_chain,
      },
    };
  } catch (error) {
    console.error('Failed to retrieve secrets:', error);
    throw error;
  }
}

// Refresh credentials before they expire
setInterval(async () => {
  const secrets = await getSecrets();
  updateDatabaseConnection(secrets.database);
}, 3600000); // Every hour
```

### AWS Secrets Manager

```javascript
const AWS = require('aws-sdk');
const secretsManager = new AWS.SecretsManager({ region: 'us-east-1' });

async function getSecret(secretName) {
  try {
    const data = await secretsManager.getSecretValue({ 
      SecretId: secretName 
    }).promise();
    
    if ('SecretString' in data) {
      return JSON.parse(data.SecretString);
    } else {
      const buff = Buffer.from(data.SecretBinary, 'base64');
      return JSON.parse(buff.toString('ascii'));
    }
  } catch (error) {
    console.error('Error retrieving secret:', error);
    throw error;
  }
}

// Usage with automatic rotation
async function initializeApp() {
  const dbCredentials = await getSecret('myapp/database/credentials');
  
  // Set up database connection
  const connection = await createDatabaseConnection({
    host: dbCredentials.host,
    username: dbCredentials.username,
    password: dbCredentials.password,
    database: dbCredentials.dbname,
  });
  
  // Listen for rotation events
  AWS.Lambda.on('SecretsManagerRotation', async (event) => {
    const newCredentials = await getSecret('myapp/database/credentials');
    await updateDatabaseConnection(newCredentials);
  });
}
```

## Infrastructure Security

### Terraform Security Scanning with Checkov

```yaml
name: Terraform Security Scan

on:
  pull_request:
    paths:
      - '**.tf'

jobs:
  checkov:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Run Checkov
      uses: bridgecrewio/checkov-action@master
      with:
        directory: terraform/
        framework: terraform
        output_format: sarif
        output_file_path: checkov.sarif
        soft_fail: false
        skip_check: CKV_AWS_8,CKV_AWS_79
    
    - name: Upload Checkov results
      uses: github/codeql-action/upload-sarif@v2
      if: always()
      with:
        sarif_file: checkov.sarif
```

### Open Policy Agent (OPA) for Policy as Code

**Terraform Policy Example:**
```rego
package terraform.aws.security

import future.keywords.contains
import future.keywords.if

# Deny public S3 buckets
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_s3_bucket"
  resource.change.after.acl == "public-read"
  msg := sprintf("S3 bucket %v has public-read access", [resource.address])
}

# Require encryption for RDS instances
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_db_instance"
  not resource.change.after.storage_encrypted
  msg := sprintf("RDS instance %v is not encrypted", [resource.address])
}

# Enforce tagging standards
required_tags := ["Environment", "Owner", "CostCenter", "Project"]

deny[msg] {
  resource := input.resource_changes[_]
  tags := resource.change.after.tags
  missing := required_tags[_]
  not tags[missing]
  msg := sprintf("Resource %v is missing required tag: %v", [resource.address, missing])
}
```

## Application Security

### Input Validation and Sanitization

**Node.js Example with Express:**
```javascript
const express = require('express');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const validator = require('validator');
const xss = require('xss');

const app = express();

// Security headers
app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      styleSrc: ["'self'", "'unsafe-inline'"],
      scriptSrc: ["'self'"],
      imgSrc: ["'self'", "data:", "https:"],
    },
  },
  hsts: {
    maxAge: 31536000,
    includeSubDomains: true,
    preload: true,
  },
}));

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
  message: 'Too many requests from this IP',
});
app.use('/api/', limiter);

// Input validation middleware
const validateInput = (req, res, next) => {
  const { email, username, comment } = req.body;
  
  // Email validation
  if (email && !validator.isEmail(email)) {
    return res.status(400).json({ error: 'Invalid email format' });
  }
  
  // Username validation (alphanumeric, 3-20 chars)
  if (username && !validator.isAlphanumeric(username) || 
      username.length < 3 || username.length > 20) {
    return res.status(400).json({ error: 'Invalid username' });
  }
  
  // XSS prevention
  if (comment) {
    req.body.comment = xss(comment);
  }
  
  next();
};

// SQL injection prevention with parameterized queries
const { Pool } = require('pg');
const pool = new Pool();

app.get('/api/users/:id', async (req, res) => {
  const userId = parseInt(req.params.id);
  
  if (isNaN(userId)) {
    return res.status(400).json({ error: 'Invalid user ID' });
  }
  
  try {
    // Parameterized query prevents SQL injection
    const result = await pool.query(
      'SELECT id, username, email FROM users WHERE id = $1',
      [userId]
    );
    
    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    res.json(result.rows[0]);
  } catch (error) {
    console.error('Database error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// CORS configuration
const cors = require('cors');
app.use(cors({
  origin: process.env.ALLOWED_ORIGINS?.split(',') || ['https://mycompany.com'],
  credentials: true,
  optionsSuccessStatus: 200,
}));

app.listen(3000);
```

### Authentication and Authorization

**JWT Implementation with Refresh Tokens:**
```javascript
const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');
const redis = require('redis');

const redisClient = redis.createClient();
const SALT_ROUNDS = 12;

// Generate tokens
function generateTokens(userId) {
  const accessToken = jwt.sign(
    { userId, type: 'access' },
    process.env.ACCESS_TOKEN_SECRET,
    { expiresIn: '15m' }
  );
  
  const refreshToken = jwt.sign(
    { userId, type: 'refresh' },
    process.env.REFRESH_TOKEN_SECRET,
    { expiresIn: '7d' }
  );
  
  return { accessToken, refreshToken };
}

// Login endpoint
app.post('/auth/login', async (req, res) => {
  const { email, password } = req.body;
  
  try {
    // Get user from database
    const user = await getUserByEmail(email);
    if (!user) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    
    // Verify password
    const validPassword = await bcrypt.compare(password, user.passwordHash);
    if (!validPassword) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    
    // Generate tokens
    const { accessToken, refreshToken } = generateTokens(user.id);
    
    // Store refresh token in Redis
    await redisClient.setex(
      `refresh_token:${user.id}`,
      7 * 24 * 60 * 60, // 7 days
      refreshToken
    );
    
    // Set secure HTTP-only cookies
    res.cookie('accessToken', accessToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      maxAge: 15 * 60 * 1000, // 15 minutes
    });
    
    res.cookie('refreshToken', refreshToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days
    });
    
    res.json({ message: 'Login successful' });
  } catch (error) {
    console.error('Login error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Middleware to verify access token
const authenticateToken = async (req, res, next) => {
  const token = req.cookies.accessToken;
  
  if (!token) {
    return res.status(401).json({ error: 'Access token required' });
  }
  
  try {
    const payload = jwt.verify(token, process.env.ACCESS_TOKEN_SECRET);
    if (payload.type !== 'access') {
      return res.status(401).json({ error: 'Invalid token type' });
    }
    
    req.userId = payload.userId;
    next();
  } catch (error) {
    if (error.name === 'TokenExpiredError') {
      return res.status(401).json({ error: 'Access token expired' });
    }
    return res.status(401).json({ error: 'Invalid token' });
  }
};
```

## Security Monitoring and Incident Response

### Security Information and Event Management (SIEM)

**Falco Runtime Security:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: falco-rules
  namespace: falco
data:
  custom-rules.yaml: |
    - rule: Unauthorized Process in Container
      desc: Detect unauthorized process running in container
      condition: >
        container and
        not proc.name in (nginx, node, python, java) and
        not proc.pname in (nginx, node, python, java)
      output: >
        Unauthorized process started in container 
        (user=%user.name command=%proc.cmdline container=%container.name)
      priority: WARNING
      tags: [container, process]
    
    - rule: Sensitive File Access
      desc: Detect access to sensitive files
      condition: >
        open_read and 
        (fd.name contains "/etc/passwd" or
         fd.name contains "/etc/shadow" or
         fd.name contains ".ssh/id_rsa" or
         fd.name contains ".aws/credentials")
      output: >
        Sensitive file opened for reading
        (user=%user.name command=%proc.cmdline file=%fd.name)
      priority: WARNING
      tags: [filesystem, secrets]
    
    - rule: Container Escape Attempt
      desc: Detect potential container escape
      condition: >
        container and
        (proc.name = "nsenter" or
         proc.name = "docker" or
         proc.cmdline contains "mount.*proc")
      output: >
        Potential container escape detected
        (user=%user.name command=%proc.cmdline container=%container.name)
      priority: CRITICAL
      tags: [container, escape]
```

## Security Best Practices Summary

1. **Automate Security Testing**
   - Integrate SAST, DAST, and dependency scanning in CI/CD
   - Use Infrastructure as Code scanning
   - Implement runtime security monitoring

2. **Implement Zero Trust**
   - Authenticate and authorize every request
   - Use mutual TLS for service-to-service communication
   - Implement network segmentation

3. **Secure Secrets Management**
   - Never store secrets in code or images
   - Use dedicated secret management tools
   - Rotate secrets regularly

4. **Container Security**
   - Scan images for vulnerabilities
   - Use minimal base images
   - Run containers as non-root users

5. **Continuous Monitoring**
   - Implement comprehensive logging
   - Set up security alerts
   - Conduct regular security reviews

6. **Incident Response**
   - Have a documented incident response plan
   - Practice incident response procedures
   - Maintain audit trails

7. **Compliance**
   - Automate compliance checks
   - Document security controls
   - Regular security audits

---

[Back to Main README](./README.md)