# Continuous Integration and Delivery (CI/CD)

This section covers continuous integration and delivery (CI/CD) pipelines and how to implement them using tools such as Jenkins, Travis CI, and CircleCI. We also discuss best practices for testing and deployment, including blue-green and canary deployments.

## What is CI/CD?

Continuous Integration (CI) is the practice of automating the integration of code changes from multiple contributors into a single software project. It's a crucial DevOps practice that allows developers to frequently merge code changes into a central repository where builds and tests run automatically.

Continuous Delivery (CD) extends CI by automatically deploying all code changes to a testing or production environment after the build stage. This means that on top of automated testing, you have an automated release process and can deploy your application at any point in time by clicking a button.

## Key Benefits of CI/CD

- **Faster Time to Market**: Automated pipelines reduce manual work and speed up the release process
- **Improved Code Quality**: Automated testing catches bugs early in the development cycle
- **Reduced Risk**: Smaller, frequent deployments are easier to troubleshoot than large, infrequent ones
- **Better Collaboration**: Teams can integrate their work frequently, reducing integration conflicts
- **Increased Confidence**: Automated testing and deployment processes ensure consistency

## Core Components of a CI/CD Pipeline

1. **Source Control Management (SCM)**
   - Git repositories (GitHub, GitLab, Bitbucket)
   - Branching strategies (GitFlow, GitHub Flow, Trunk-Based Development)
   - Code review processes and pull requests

2. **Build Stage**
   - Compilation of source code
   - Dependency management
   - Artifact creation
   - Container image building

3. **Testing Stage**
   - Unit tests
   - Integration tests
   - End-to-end tests
   - Security scanning
   - Code quality analysis

4. **Deployment Stage**
   - Environment provisioning
   - Configuration management
   - Database migrations
   - Application deployment
   - Post-deployment verification

## Popular CI/CD Tools

### Jenkins
Jenkins is an open-source automation server that enables developers to build, test, and deploy their software. It's highly extensible with a rich ecosystem of plugins.

**Key Features:**
- Distributed builds across multiple machines
- Easy installation and configuration
- Extensive plugin ecosystem (over 1,500 plugins)
- Support for various version control systems
- Pipeline as Code with Jenkinsfile

**Example Jenkinsfile:**
```groovy
pipeline {
    agent any
    
    stages {
        stage('Build') {
            steps {
                sh 'npm install'
                sh 'npm run build'
            }
        }
        
        stage('Test') {
            steps {
                sh 'npm test'
                sh 'npm run lint'
            }
        }
        
        stage('Deploy to Staging') {
            when {
                branch 'develop'
            }
            steps {
                sh './deploy.sh staging'
            }
        }
        
        stage('Deploy to Production') {
            when {
                branch 'main'
            }
            steps {
                input 'Deploy to production?'
                sh './deploy.sh production'
            }
        }
    }
    
    post {
        always {
            cleanWs()
        }
        success {
            echo 'Pipeline succeeded!'
        }
        failure {
            echo 'Pipeline failed!'
        }
    }
}
```

### GitHub Actions
GitHub Actions is a CI/CD platform that allows you to automate your build, test, and deployment pipeline directly from GitHub.

**Key Features:**
- Native integration with GitHub
- YAML-based workflow configuration
- Large marketplace of pre-built actions
- Matrix builds for testing across multiple versions
- Built-in secret management

**Example GitHub Actions Workflow:**
```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    
    strategy:
      matrix:
        node-version: [14.x, 16.x, 18.x]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Use Node.js ${{ matrix.node-version }}
      uses: actions/setup-node@v3
      with:
        node-version: ${{ matrix.node-version }}
    
    - name: Install dependencies
      run: npm ci
    
    - name: Run tests
      run: npm test
    
    - name: Run linter
      run: npm run lint
    
    - name: Build application
      run: npm run build
    
    - name: Upload artifacts
      uses: actions/upload-artifact@v3
      with:
        name: build-artifacts
        path: dist/
  
  deploy:
    needs: build-and-test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Download artifacts
      uses: actions/download-artifact@v3
      with:
        name: build-artifacts
        path: dist/
    
    - name: Deploy to production
      env:
        DEPLOY_KEY: ${{ secrets.DEPLOY_KEY }}
      run: |
        # Deploy script here
        echo "Deploying to production..."
```

### GitLab CI/CD
GitLab provides a complete DevOps platform with built-in CI/CD capabilities.

**Key Features:**
- Integrated with GitLab repositories
- Auto DevOps for automatic pipeline configuration
- Built-in container registry
- Review apps for merge requests
- Advanced deployment strategies

**Example .gitlab-ci.yml:**
```yaml
stages:
  - build
  - test
  - deploy

variables:
  DOCKER_DRIVER: overlay2

build:
  stage: build
  image: node:16
  script:
    - npm ci
    - npm run build
  artifacts:
    paths:
      - dist/
    expire_in: 1 hour

test:
  stage: test
  image: node:16
  script:
    - npm ci
    - npm test
    - npm run lint
  coverage: '/Coverage: \d+\.\d+%/'

deploy-staging:
  stage: deploy
  script:
    - echo "Deploying to staging environment"
    - ./deploy.sh staging
  environment:
    name: staging
    url: https://staging.mycompany.com
  only:
    - develop

deploy-production:
  stage: deploy
  script:
    - echo "Deploying to production environment"
    - ./deploy.sh production
  environment:
    name: production
    url: https://www.mycompany.com
  when: manual
  only:
    - main
```

## Deployment Strategies

### Blue-Green Deployment
Blue-green deployment is a technique that reduces downtime and risk by running two identical production environments called Blue and Green.

**How it works:**
1. Blue is the currently running production environment
2. Green is the new version of the application
3. Once Green is tested and ready, traffic is switched from Blue to Green
4. Blue becomes the staging environment for the next release

**Benefits:**
- Zero downtime deployments
- Easy rollback (just switch back to Blue)
- Testing in production-like environment before going live

**Implementation Example:**
```bash
#!/bin/bash
# Blue-Green Deployment Script

CURRENT_ENV=$(kubectl get service app-service -o jsonpath='{.spec.selector.deployment}')
if [ "$CURRENT_ENV" == "blue" ]; then
    NEW_ENV="green"
else
    NEW_ENV="blue"
fi

echo "Current environment: $CURRENT_ENV"
echo "Deploying to: $NEW_ENV"

# Deploy new version
kubectl set image deployment/app-$NEW_ENV app=myapp:$VERSION

# Wait for rollout to complete
kubectl rollout status deployment/app-$NEW_ENV

# Run smoke tests
./run-smoke-tests.sh $NEW_ENV

if [ $? -eq 0 ]; then
    # Switch traffic to new environment
    kubectl patch service app-service -p '{"spec":{"selector":{"deployment":"'$NEW_ENV'"}}}'
    echo "Successfully switched to $NEW_ENV environment"
else
    echo "Smoke tests failed, keeping traffic on $CURRENT_ENV"
    exit 1
fi
```

### Canary Deployment
Canary deployment is a pattern that rolls out new features to a small subset of users before rolling it out to the entire infrastructure.

**How it works:**
1. Deploy the new version alongside the old version
2. Route a small percentage of traffic to the new version
3. Monitor metrics and error rates
4. Gradually increase traffic to the new version
5. Roll back if issues are detected

**Benefits:**
- Reduced risk of widespread issues
- Real-world testing with actual users
- Gradual rollout allows for monitoring and adjustment

**Implementation with Kubernetes:**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: app-service
spec:
  selector:
    app: myapp
  ports:
    - port: 80
      targetPort: 8080
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-stable
spec:
  replicas: 9
  selector:
    matchLabels:
      app: myapp
      version: stable
  template:
    metadata:
      labels:
        app: myapp
        version: stable
    spec:
      containers:
      - name: app
        image: myapp:1.0.0
        ports:
        - containerPort: 8080
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-canary
spec:
  replicas: 1
  selector:
    matchLabels:
      app: myapp
      version: canary
  template:
    metadata:
      labels:
        app: myapp
        version: canary
    spec:
      containers:
      - name: app
        image: myapp:2.0.0
        ports:
        - containerPort: 8080
```

## Best Practices for CI/CD

1. **Keep Builds Fast**
   - Parallelize tests where possible
   - Use build caching
   - Run quick tests first, longer tests later
   - Optimize build tools and dependencies

2. **Fail Fast**
   - Run fastest tests first
   - Stop the pipeline on first failure
   - Provide clear error messages

3. **Version Everything**
   - Use semantic versioning for releases
   - Tag Docker images with git commit SHA
   - Version database schemas
   - Track infrastructure changes

4. **Secure Your Pipeline**
   - Never hardcode secrets
   - Use secret management tools
   - Scan for vulnerabilities
   - Implement least privilege access

5. **Monitor Your Pipeline**
   - Track build times and success rates
   - Alert on pipeline failures
   - Measure deployment frequency
   - Monitor application performance post-deployment

6. **Automate Everything**
   - Database migrations
   - Environment provisioning
   - Testing at all levels
   - Rollback procedures

## Getting Started with CI/CD

1. **Start Small**
   - Begin with a simple pipeline that builds and tests
   - Add deployment automation gradually
   - Focus on one application or service first

2. **Choose the Right Tools**
   - Consider your team's expertise
   - Evaluate integration with existing tools
   - Factor in cost and maintenance

3. **Define Your Pipeline Stages**
   - Build → Test → Security Scan → Deploy to Staging → Deploy to Production
   - Add stages based on your needs

4. **Implement Gradually**
   - Start with CI (automated builds and tests)
   - Add CD to staging environments
   - Finally, automate production deployments

5. **Measure Success**
   - Track deployment frequency
   - Monitor lead time for changes
   - Measure mean time to recovery (MTTR)
   - Calculate change failure rate

---

[Back to Main README](./README.md)