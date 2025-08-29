# Serverless Architectures

## Introduction to Serverless Computing

Okay, let's talk serverless. After spending way too many nights debugging EC2 instances and fighting with auto-scaling groups, I've become a huge fan of serverless architectures. It's not a silver bullet (nothing ever is), but when used correctly, it's pretty amazing.

### What is Serverless?

First off, "serverless" is a terrible name - there are definitely servers involved! But here's what it really means:
- You don't manage infrastructure (finally!)
- Resources scale automatically based on demand
- You only pay for what you actually use (your CFO will love this)
- The cloud provider handles all the ops headaches

### Why I Love (and Sometimes Hate) Serverless

**The Good Stuff:**
1. **No Server Management**: Seriously, not having to patch servers at 3 AM is life-changing
2. **Event-Driven**: Everything is reactive, which maps perfectly to modern app architectures
3. **Auto-scaling**: From 0 to 10,000 requests without breaking a sweat
4. **Cost Model**: We cut our AWS bill by 70% moving some workloads to Lambda
5. **Built-in HA**: Multi-AZ by default, one less thing to worry about

**The Not-So-Good:**
- Cold starts can be painful (especially for Java/C#)
- Vendor lock-in is real
- Debugging distributed systems is still hard
- 15-minute timeout on Lambda can be limiting

## Serverless Platforms

### AWS Lambda (The OG)

Lambda is where most people start, and honestly, it's still my go-to for most serverless workloads. AWS has had years to refine it, and it shows.

#### Basic Lambda Function (Python)

```python
import json
import boto3
from datetime import datetime

# Initialize AWS services
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

def lambda_handler(event, context):
    """
    Process incoming API Gateway requests
    """
    try:
        # Parse request body
        body = json.loads(event['body']) if event.get('body') else {}
        
        # Process business logic
        result = process_order(body)
        
        # Store in DynamoDB
        table = dynamodb.Table('Orders')
        table.put_item(Item={
            'orderId': result['orderId'],
            'timestamp': datetime.utcnow().isoformat(),
            'data': result
        })
        
        # Send notification
        sns.publish(
            TopicArn='arn:aws:sns:us-east-1:123456789:order-notifications',
            Message=json.dumps(result),
            Subject='New Order Processed'
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'orderId': result['orderId']
            })
        }
        
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }

def process_order(order_data):
    """Process order business logic"""
    return {
        'orderId': generate_order_id(),
        'status': 'processed',
        'items': order_data.get('items', [])
    }

def generate_order_id():
    """Generate unique order ID"""
    from uuid import uuid4
    return str(uuid4())
```

#### Lambda with Layers

```python
# buildspec.yml for Lambda Layer
version: 0.2

phases:
  install:
    runtime-versions:
      python: 3.11
    commands:
      - pip install --target python/lib/python3.11/site-packages/ -r requirements.txt
      
  build:
    commands:
      - zip -r layer.zip python/

artifacts:
  files:
    - layer.zip
```

### Azure Functions (The Enterprise Choice)

If you're in a Microsoft shop, Azure Functions is solid. The Visual Studio integration is fantastic, and if you're already using Azure DevOps, it's a no-brainer.

#### HTTP Trigger Function (TypeScript)

```typescript
import { AzureFunction, Context, HttpRequest } from "@azure/functions"
import { CosmosClient } from "@azure/cosmos"

const cosmosClient = new CosmosClient({
    endpoint: process.env.COSMOS_ENDPOINT,
    key: process.env.COSMOS_KEY
});

const httpTrigger: AzureFunction = async function (
    context: Context, 
    req: HttpRequest
): Promise<void> {
    context.log('Processing HTTP request');
    
    try {
        const name = req.query.name || (req.body && req.body.name);
        
        if (!name) {
            context.res = {
                status: 400,
                body: "Please provide a name parameter"
            };
            return;
        }
        
        // Process data
        const result = await processData(name);
        
        // Store in Cosmos DB
        const database = cosmosClient.database('ServerlessDB');
        const container = database.container('Events');
        
        await container.items.create({
            id: generateId(),
            name: name,
            timestamp: new Date().toISOString(),
            result: result
        });
        
        context.res = {
            status: 200,
            body: {
                message: `Hello, ${name}!`,
                result: result
            }
        };
        
    } catch (error) {
        context.log.error('Error processing request:', error);
        context.res = {
            status: 500,
            body: "Internal server error"
        };
    }
};

async function processData(name: string): Promise<any> {
    // Business logic here
    return {
        processed: true,
        name: name.toUpperCase()
    };
}

function generateId(): string {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

export default httpTrigger;
```

### Google Cloud Functions (The Underdog)

Don't sleep on GCP Functions! They have some killer features like native Cloud Firestore triggers. Plus, their cold start times are impressive.

#### Event-Driven Function (Node.js)

```javascript
const { Storage } = require('@google-cloud/storage');
const { BigQuery } = require('@google-cloud/bigquery');
const sharp = require('sharp');

const storage = new Storage();
const bigquery = new BigQuery();

/**
 * Cloud Storage trigger - process uploaded images
 */
exports.processImage = async (file, context) => {
    console.log(`Processing file: ${file.name}`);
    
    const bucketName = file.bucket;
    const fileName = file.name;
    
    // Skip if already processed
    if (fileName.includes('thumb_')) {
        return;
    }
    
    try {
        // Download original image
        const bucket = storage.bucket(bucketName);
        const imageBuffer = await bucket.file(fileName).download();
        
        // Create thumbnail
        const thumbnail = await sharp(imageBuffer[0])
            .resize(200, 200)
            .toBuffer();
        
        // Upload thumbnail
        const thumbFileName = `thumb_${fileName}`;
        await bucket.file(thumbFileName).save(thumbnail, {
            metadata: {
                contentType: file.contentType,
            }
        });
        
        // Log to BigQuery
        const dataset = bigquery.dataset('image_processing');
        const table = dataset.table('processed_images');
        
        await table.insert({
            original_file: fileName,
            thumbnail_file: thumbFileName,
            processed_at: new Date().toISOString(),
            size_original: file.size,
            size_thumbnail: thumbnail.length
        });
        
        console.log(`Successfully processed ${fileName}`);
        
    } catch (error) {
        console.error('Error processing image:', error);
        throw error;
    }
};

/**
 * HTTP trigger - image metadata API
 */
exports.getImageMetadata = async (req, res) => {
    const fileName = req.query.file;
    
    if (!fileName) {
        res.status(400).send('Missing file parameter');
        return;
    }
    
    try {
        const bucket = storage.bucket('image-uploads');
        const file = bucket.file(fileName);
        const [metadata] = await file.getMetadata();
        
        res.json({
            name: fileName,
            size: metadata.size,
            contentType: metadata.contentType,
            created: metadata.timeCreated,
            updated: metadata.updated,
            md5Hash: metadata.md5Hash
        });
        
    } catch (error) {
        console.error('Error fetching metadata:', error);
        res.status(500).send('Internal server error');
    }
};
```

## Serverless Frameworks

### Serverless Framework (Still the King)

I've tried them all - SAM, CDK, Terraform, Pulumi - but I keep coming back to Serverless Framework for pure Lambda projects. The plugin ecosystem is unmatched.

#### serverless.yml Configuration

```yaml
service: microservice-api

provider:
  name: aws
  runtime: python3.11
  stage: ${opt:stage, 'dev'}
  region: ${opt:region, 'us-east-1'}
  
  environment:
    STAGE: ${self:provider.stage}
    DYNAMODB_TABLE: ${self:service}-${self:provider.stage}
    SNS_TOPIC: !Ref NotificationTopic
    
  iam:
    role:
      statements:
        - Effect: Allow
          Action:
            - dynamodb:Query
            - dynamodb:Scan
            - dynamodb:GetItem
            - dynamodb:PutItem
            - dynamodb:UpdateItem
            - dynamodb:DeleteItem
          Resource: 
            - !GetAtt UsersTable.Arn
            - !Sub "${UsersTable.Arn}/index/*"
        - Effect: Allow
          Action:
            - sns:Publish
          Resource: !Ref NotificationTopic
        - Effect: Allow
          Action:
            - s3:GetObject
            - s3:PutObject
          Resource: !Sub "${FilesBucket.Arn}/*"

functions:
  createUser:
    handler: handlers/users.create
    events:
      - http:
          path: users
          method: post
          cors: true
          authorizer:
            type: COGNITO_USER_POOLS
            authorizerId: !Ref ApiGatewayAuthorizer
            
  getUser:
    handler: handlers/users.get
    events:
      - http:
          path: users/{id}
          method: get
          cors: true
          
  processUpload:
    handler: handlers/files.process
    events:
      - s3:
          bucket: !Ref FilesBucket
          event: s3:ObjectCreated:*
          rules:
            - prefix: uploads/
            - suffix: .csv
          
  scheduledTask:
    handler: handlers/scheduled.cleanup
    events:
      - schedule:
          rate: rate(1 hour)
          enabled: true
          
  streamProcessor:
    handler: handlers/stream.process
    events:
      - stream:
          type: dynamodb
          arn: !GetAtt UsersTable.StreamArn
          batchSize: 10
          startingPosition: LATEST

plugins:
  - serverless-python-requirements
  - serverless-plugin-tracing
  - serverless-offline
  - serverless-domain-manager

custom:
  pythonRequirements:
    dockerizePip: true
    layer: true
    
  customDomain:
    domainName: api.example.com
    stage: ${self:provider.stage}
    basePath: v1
    certificateName: '*.example.com'
    createRoute53Record: true
    
  alerts:
    stages:
      - prod
    topics:
      alarm:
        topic: ${self:service}-${self:provider.stage}-alerts
        notifications:
          - protocol: email
            endpoint: ops@example.com
    alarms:
      - functionErrors
      - functionThrottles
      - functionDuration

resources:
  Resources:
    UsersTable:
      Type: AWS::DynamoDB::Table
      Properties:
        TableName: ${self:provider.environment.DYNAMODB_TABLE}
        AttributeDefinitions:
          - AttributeName: id
            AttributeType: S
          - AttributeName: email
            AttributeType: S
        KeySchema:
          - AttributeName: id
            KeyType: HASH
        GlobalSecondaryIndexes:
          - IndexName: email-index
            KeySchema:
              - AttributeName: email
                KeyType: HASH
            Projection:
              ProjectionType: ALL
            ProvisionedThroughput:
              ReadCapacityUnits: 5
              WriteCapacityUnits: 5
        StreamSpecification:
          StreamViewType: NEW_AND_OLD_IMAGES
        BillingMode: PAY_PER_REQUEST
        
    FilesBucket:
      Type: AWS::S3::Bucket
      Properties:
        BucketName: ${self:service}-${self:provider.stage}-files
        CorsConfiguration:
          CorsRules:
            - AllowedOrigins:
                - '*'
              AllowedMethods:
                - GET
                - PUT
                - POST
              AllowedHeaders:
                - '*'
        LifecycleConfiguration:
          Rules:
            - Id: DeleteOldFiles
              Status: Enabled
              ExpirationInDays: 30
              
    NotificationTopic:
      Type: AWS::SNS::Topic
      Properties:
        DisplayName: ${self:service} Notifications
        TopicName: ${self:service}-${self:provider.stage}-notifications
```

### AWS SAM (Serverless Application Model)

#### template.yaml

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Serverless Application Model Example

Globals:
  Function:
    Timeout: 30
    Runtime: python3.11
    Tracing: Active
    Environment:
      Variables:
        POWERTOOLS_SERVICE_NAME: serverless-app
        POWERTOOLS_METRICS_NAMESPACE: ServerlessApp
        LOG_LEVEL: INFO

Parameters:
  Environment:
    Type: String
    Default: dev
    AllowedValues:
      - dev
      - staging
      - prod

Resources:
  # API Gateway
  ApiGateway:
    Type: AWS::Serverless::Api
    Properties:
      StageName: !Ref Environment
      TracingEnabled: true
      Cors:
        AllowOrigin: "'*'"
        AllowHeaders: "'*'"
        AllowMethods: "'*'"
      Auth:
        DefaultAuthorizer: CognitoAuth
        Authorizers:
          CognitoAuth:
            UserPoolArn: !GetAtt UserPool.Arn

  # Lambda Functions
  OrderFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/orders/
      Handler: app.lambda_handler
      Architectures:
        - arm64
      Layers:
        - !Ref DependenciesLayer
      Environment:
        Variables:
          TABLE_NAME: !Ref OrdersTable
          QUEUE_URL: !Ref ProcessingQueue
      Events:
        CreateOrder:
          Type: Api
          Properties:
            RestApiId: !Ref ApiGateway
            Path: /orders
            Method: POST
        GetOrder:
          Type: Api
          Properties:
            RestApiId: !Ref ApiGateway
            Path: /orders/{id}
            Method: GET
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref OrdersTable
        - SQSSendMessagePolicy:
            QueueName: !GetAtt ProcessingQueue.QueueName

  ProcessorFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/processor/
      Handler: app.lambda_handler
      ReservedConcurrentExecutions: 10
      Events:
        QueueEvent:
          Type: SQS
          Properties:
            Queue: !GetAtt ProcessingQueue.Arn
            BatchSize: 10
            MaximumBatchingWindowInSeconds: 5
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref OrdersTable
        - S3CrudPolicy:
            BucketName: !Ref DataBucket

  # Step Functions
  OrderWorkflow:
    Type: AWS::Serverless::StateMachine
    Properties:
      DefinitionUri: statemachine/order_workflow.asl.json
      DefinitionSubstitutions:
        ValidateFunctionArn: !GetAtt ValidateFunction.Arn
        ProcessFunctionArn: !GetAtt ProcessFunction.Arn
        NotifyFunctionArn: !GetAtt NotifyFunction.Arn
      Policies:
        - LambdaInvokePolicy:
            FunctionName: !Ref ValidateFunction
        - LambdaInvokePolicy:
            FunctionName: !Ref ProcessFunction
        - LambdaInvokePolicy:
            FunctionName: !Ref NotifyFunction

  # Lambda Layer
  DependenciesLayer:
    Type: AWS::Serverless::LayerVersion
    Properties:
      LayerName: dependencies
      ContentUri: layers/
      CompatibleRuntimes:
        - python3.11
      CompatibleArchitectures:
        - arm64
        - x86_64
    Metadata:
      BuildMethod: python3.11
      BuildArchitecture: arm64

  # DynamoDB
  OrdersTable:
    Type: AWS::Serverless::SimpleTable
    Properties:
      PrimaryKey:
        Name: id
        Type: String
      ProvisionedThroughput:
        ReadCapacityUnits: 5
        WriteCapacityUnits: 5

  # SQS Queue
  ProcessingQueue:
    Type: AWS::SQS::Queue
    Properties:
      VisibilityTimeout: 180
      MessageRetentionPeriod: 1209600
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt DeadLetterQueue.Arn
        maxReceiveCount: 3

  DeadLetterQueue:
    Type: AWS::SQS::Queue
    Properties:
      MessageRetentionPeriod: 1209600

  # S3 Bucket
  DataBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: AES256
      VersioningConfiguration:
        Status: Enabled

  # Cognito User Pool
  UserPool:
    Type: AWS::Cognito::UserPool
    Properties:
      UserPoolName: !Sub ${AWS::StackName}-users
      Schema:
        - AttributeDataType: String
          Name: email
          Required: true
          Mutable: false

Outputs:
  ApiEndpoint:
    Description: API Gateway endpoint URL
    Value: !Sub https://${ApiGateway}.execute-api.${AWS::Region}.amazonaws.com/${Environment}
  
  UserPoolId:
    Description: Cognito User Pool ID
    Value: !Ref UserPool
```

### Pulumi for Serverless (My New Favorite)

Okay, I'm a Pulumi convert. Being able to use real programming languages instead of YAML? Game changer. Plus, the type safety in TypeScript has saved me from so many deployment failures.

#### Pulumi TypeScript Serverless Setup

```typescript
import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import * as apigateway from "@pulumi/aws-apigateway";

// Configuration
const config = new pulumi.Config();
const environment = config.require("environment");

// Create Lambda execution role
const lambdaRole = new aws.iam.Role("lambdaRole", {
    assumeRolePolicy: aws.iam.assumeRolePolicyForPrincipal({
        Service: "lambda.amazonaws.com"
    })
});

// Attach policies to Lambda role
new aws.iam.RolePolicyAttachment("lambdaExecutionPolicy", {
    role: lambdaRole,
    policyArn: aws.iam.ManagedPolicy.AWSLambdaBasicExecutionRole
});

new aws.iam.RolePolicyAttachment("lambdaVPCAccessPolicy", {
    role: lambdaRole,
    policyArn: aws.iam.ManagedPolicy.AWSLambdaVPCAccessExecutionRole
});

// DynamoDB table
const ordersTable = new aws.dynamodb.Table("orders", {
    attributes: [
        { name: "orderId", type: "S" },
        { name: "customerId", type: "S" },
        { name: "timestamp", type: "N" }
    ],
    hashKey: "orderId",
    rangeKey: "timestamp",
    globalSecondaryIndexes: [{
        name: "CustomerIndex",
        hashKey: "customerId",
        rangeKey: "timestamp",
        projectionType: "ALL",
        readCapacity: 5,
        writeCapacity: 5
    }],
    billingMode: "PROVISIONED",
    readCapacity: 10,
    writeCapacity: 10,
    streamEnabled: true,
    streamViewType: "NEW_AND_OLD_IMAGES",
    tags: {
        Environment: environment,
        Service: "orders"
    }
});

// S3 bucket for uploads
const uploadsBucket = new aws.s3.Bucket("uploads", {
    acl: "private",
    versioning: {
        enabled: true
    },
    lifecycleRules: [{
        enabled: true,
        expiration: {
            days: 30
        },
        transitions: [{
            days: 7,
            storageClass: "GLACIER"
        }]
    }],
    serverSideEncryptionConfiguration: {
        rule: {
            applyServerSideEncryptionByDefault: {
                sseAlgorithm: "AES256"
            }
        }
    }
});

// Lambda function for order processing
const orderProcessor = new aws.lambda.Function("orderProcessor", {
    code: new pulumi.asset.AssetArchive({
        ".": new pulumi.asset.FileArchive("./functions/order-processor")
    }),
    runtime: "nodejs18.x",
    handler: "index.handler",
    role: lambdaRole.arn,
    timeout: 30,
    memorySize: 512,
    environment: {
        variables: {
            TABLE_NAME: ordersTable.name,
            BUCKET_NAME: uploadsBucket.bucket,
            ENVIRONMENT: environment
        }
    },
    tracingConfig: {
        mode: "Active"
    }
});

// Grant Lambda permissions to access DynamoDB
const dynamoPolicy = new aws.iam.Policy("dynamoPolicy", {
    policy: ordersTable.arn.apply(arn => JSON.stringify({
        Version: "2012-10-17",
        Statement: [{
            Effect: "Allow",
            Action: [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Query",
                "dynamodb:Scan"
            ],
            Resource: [arn, `${arn}/index/*`]
        }]
    }))
});

new aws.iam.RolePolicyAttachment("lambdaDynamoAttachment", {
    role: lambdaRole,
    policyArn: dynamoPolicy.arn
});

// API Gateway
const api = new apigateway.RestAPI("api", {
    routes: [
        {
            path: "/orders",
            method: "POST",
            eventHandler: orderProcessor
        },
        {
            path: "/orders/{id}",
            method: "GET",
            eventHandler: new aws.lambda.CallbackFunction("getOrder", {
                callback: async (event: any) => {
                    const AWS = require("aws-sdk");
                    const dynamodb = new AWS.DynamoDB.DocumentClient();
                    
                    try {
                        const result = await dynamodb.get({
                            TableName: process.env.TABLE_NAME,
                            Key: {
                                orderId: event.pathParameters.id
                            }
                        }).promise();
                        
                        return {
                            statusCode: 200,
                            body: JSON.stringify(result.Item)
                        };
                    } catch (error) {
                        return {
                            statusCode: 500,
                            body: JSON.stringify({ error: "Internal server error" })
                        };
                    }
                },
                runtime: "nodejs18.x",
                environment: {
                    variables: {
                        TABLE_NAME: ordersTable.name
                    }
                }
            })
        }
    ],
    stageName: environment
});

// SQS Queue for async processing
const processingQueue = new aws.sqs.Queue("processingQueue", {
    visibilityTimeoutSeconds: 300,
    messageRetentionSeconds: 1209600,
    maxMessageSize: 262144,
    delaySeconds: 0,
    receiveWaitTimeSeconds: 20,
    redrivePolicy: {
        deadLetterTargetArn: deadLetterQueue.arn,
        maxReceiveCount: 3
    }
});

const deadLetterQueue = new aws.sqs.Queue("deadLetterQueue", {
    messageRetentionSeconds: 1209600
});

// Lambda for queue processing
const queueProcessor = new aws.lambda.Function("queueProcessor", {
    code: new pulumi.asset.AssetArchive({
        ".": new pulumi.asset.FileArchive("./functions/queue-processor")
    }),
    runtime: "python3.11",
    handler: "handler.process",
    role: lambdaRole.arn,
    timeout: 300,
    reservedConcurrentExecutions: 10,
    environment: {
        variables: {
            TABLE_NAME: ordersTable.name,
            QUEUE_URL: processingQueue.url
        }
    }
});

// Event source mapping for SQS
new aws.lambda.EventSourceMapping("queueEventSource", {
    eventSourceArn: processingQueue.arn,
    functionName: queueProcessor.name,
    batchSize: 10,
    maximumBatchingWindowInSeconds: 5
});

// CloudWatch Alarms
const errorAlarm = new aws.cloudwatch.MetricAlarm("lambdaErrors", {
    comparisonOperator: "GreaterThanThreshold",
    evaluationPeriods: 2,
    metricName: "Errors",
    namespace: "AWS/Lambda",
    period: 300,
    statistic: "Sum",
    threshold: 10,
    alarmDescription: "Lambda function error rate is too high",
    dimensions: {
        FunctionName: orderProcessor.name
    }
});

// Exports
export const apiUrl = api.url;
export const queueUrl = processingQueue.url;
export const tableName = ordersTable.name;
export const bucketName = uploadsBucket.bucket;
```

## Event-Driven Architecture

### Event Sources and Triggers

```python
# Event Router Lambda
import json
import boto3
from typing import Dict, Any, List

sns = boto3.client('sns')
eventbridge = boto3.client('events')
sqs = boto3.client('sqs')

class EventRouter:
    def __init__(self):
        self.routing_rules = {
            'order.created': self.route_order_created,
            'payment.processed': self.route_payment_processed,
            'inventory.updated': self.route_inventory_updated,
            'user.registered': self.route_user_registered
        }
    
    def route_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Main routing logic"""
        event_type = event.get('type')
        
        if event_type not in self.routing_rules:
            return self.handle_unknown_event(event)
        
        # Route to appropriate handler
        handler = self.routing_rules[event_type]
        return handler(event)
    
    def route_order_created(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle order created events"""
        order_data = event.get('data', {})
        
        # Send to multiple targets
        targets = []
        
        # Notify inventory service
        targets.append({
            'Source': 'order.service',
            'DetailType': 'OrderCreated',
            'Detail': json.dumps(order_data)
        })
        
        # Trigger payment processing
        sqs.send_message(
            QueueUrl=os.environ['PAYMENT_QUEUE_URL'],
            MessageBody=json.dumps({
                'orderId': order_data['orderId'],
                'amount': order_data['total']
            })
        )
        
        # Send customer notification
        sns.publish(
            TopicArn=os.environ['CUSTOMER_TOPIC_ARN'],
            Message=json.dumps(order_data),
            Subject='Order Confirmation'
        )
        
        # Put events to EventBridge
        eventbridge.put_events(Entries=targets)
        
        return {
            'status': 'routed',
            'targets': len(targets)
        }
    
    def route_payment_processed(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle payment processed events"""
        payment_data = event.get('data', {})
        
        # Update order status
        self.update_order_status(
            payment_data['orderId'], 
            'payment_confirmed'
        )
        
        # Trigger fulfillment
        eventbridge.put_events(
            Entries=[{
                'Source': 'payment.service',
                'DetailType': 'PaymentCompleted',
                'Detail': json.dumps(payment_data)
            }]
        )
        
        return {'status': 'processed'}
    
    def route_inventory_updated(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle inventory updates"""
        inventory_data = event.get('data', {})
        
        # Check for low stock
        if inventory_data.get('quantity', 0) < 10:
            sns.publish(
                TopicArn=os.environ['ALERTS_TOPIC_ARN'],
                Message=f"Low stock alert for {inventory_data['productId']}",
                Subject='Low Stock Alert'
            )
        
        return {'status': 'monitored'}
    
    def route_user_registered(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user registration events"""
        user_data = event.get('data', {})
        
        # Trigger welcome email workflow
        eventbridge.put_events(
            Entries=[{
                'Source': 'user.service',
                'DetailType': 'UserRegistered',
                'Detail': json.dumps(user_data)
            }]
        )
        
        # Add to CRM
        sqs.send_message(
            QueueUrl=os.environ['CRM_QUEUE_URL'],
            MessageBody=json.dumps(user_data),
            DelaySeconds=10
        )
        
        return {'status': 'welcomed'}
    
    def handle_unknown_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle unknown event types"""
        print(f"Unknown event type: {event.get('type')}")
        
        # Send to DLQ for investigation
        sqs.send_message(
            QueueUrl=os.environ['DLQ_URL'],
            MessageBody=json.dumps(event)
        )
        
        return {'status': 'unknown', 'action': 'sent_to_dlq'}

def lambda_handler(event, context):
    """Lambda entry point"""
    router = EventRouter()
    
    # Handle different event sources
    if 'Records' in event:
        # SQS/SNS/Kinesis batch
        results = []
        for record in event['Records']:
            if 'body' in record:
                # SQS
                body = json.loads(record['body'])
                results.append(router.route_event(body))
            elif 'Sns' in record:
                # SNS
                message = json.loads(record['Sns']['Message'])
                results.append(router.route_event(message))
        return {'results': results}
    else:
        # Direct invocation or API Gateway
        return router.route_event(event)
```

### Event Orchestration with Step Functions

```json
{
  "Comment": "Order Processing Workflow",
  "StartAt": "ValidateOrder",
  "States": {
    "ValidateOrder": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:ValidateOrder",
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 2,
          "MaxAttempts": 3,
          "BackoffRate": 2
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["ValidationError"],
          "Next": "OrderValidationFailed"
        }
      ],
      "Next": "CheckInventory"
    },
    
    "CheckInventory": {
      "Type": "Parallel",
      "Branches": [
        {
          "StartAt": "CheckStock",
          "States": {
            "CheckStock": {
              "Type": "Task",
              "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:CheckStock",
              "End": true
            }
          }
        },
        {
          "StartAt": "ReserveInventory",
          "States": {
            "ReserveInventory": {
              "Type": "Task",
              "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:ReserveInventory",
              "End": true
            }
          }
        }
      ],
      "Next": "ProcessPayment"
    },
    
    "ProcessPayment": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke.waitForTaskToken",
      "Parameters": {
        "FunctionName": "ProcessPayment",
        "Payload": {
          "orderId.$": "$.orderId",
          "amount.$": "$.amount",
          "token.$": "$$.Task.Token"
        }
      },
      "TimeoutSeconds": 300,
      "Catch": [
        {
          "ErrorEquals": ["PaymentFailed"],
          "Next": "PaymentFailedHandler"
        }
      ],
      "Next": "FulfillOrder"
    },
    
    "FulfillOrder": {
      "Type": "Map",
      "ItemsPath": "$.items",
      "MaxConcurrency": 5,
      "Iterator": {
        "StartAt": "PrepareItem",
        "States": {
          "PrepareItem": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:PrepareItem",
            "Next": "ShipItem"
          },
          "ShipItem": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:ShipItem",
            "End": true
          }
        }
      },
      "Next": "SendConfirmation"
    },
    
    "SendConfirmation": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "arn:aws:sns:REGION:ACCOUNT:order-confirmations",
        "Message.$": "$.confirmation"
      },
      "Next": "OrderComplete"
    },
    
    "OrderComplete": {
      "Type": "Succeed"
    },
    
    "OrderValidationFailed": {
      "Type": "Fail",
      "Error": "OrderValidationFailed",
      "Cause": "Order validation failed"
    },
    
    "PaymentFailedHandler": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:HandlePaymentFailure",
      "Next": "OrderCancelled"
    },
    
    "OrderCancelled": {
      "Type": "Fail",
      "Error": "OrderCancelled",
      "Cause": "Payment processing failed"
    }
  }
}
```

## Performance Optimization

### Cold Start Optimization (The Eternal Battle)

Let me save you some pain - cold starts are real, and they will bite you in production. Here's what actually works:

```python
# Optimized Lambda with connection pooling and caching
import json
import os
import boto3
from functools import lru_cache
from typing import Dict, Any, Optional
import redis
import psycopg2
from psycopg2 import pool

# Initialize outside handler for connection reuse
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

# Connection pooling for Redis
redis_pool = redis.ConnectionPool(
    host=os.environ.get('REDIS_HOST', 'localhost'),
    port=int(os.environ.get('REDIS_PORT', 6379)),
    db=0,
    max_connections=10
)
redis_client = redis.Redis(connection_pool=redis_pool)

# PostgreSQL connection pool
postgres_pool = psycopg2.pool.SimpleConnectionPool(
    1, 20,
    host=os.environ.get('DB_HOST'),
    database=os.environ.get('DB_NAME'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD')
)

# Preload heavy dependencies
import pandas as pd
import numpy as np

# Cache frequently accessed data
@lru_cache(maxsize=128)
def get_config(key: str) -> Any:
    """Cache configuration values"""
    table = dynamodb.Table('config')
    response = table.get_item(Key={'key': key})
    return response.get('Item', {}).get('value')

class OptimizedHandler:
    def __init__(self):
        # Pre-warm connections
        self.warm_connections()
        
    def warm_connections(self):
        """Pre-warm database connections"""
        try:
            # Test Redis connection
            redis_client.ping()
            
            # Test PostgreSQL connection
            conn = postgres_pool.getconn()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            postgres_pool.putconn(conn)
            
        except Exception as e:
            print(f"Connection warming failed: {e}")
    
    def get_cached_data(self, key: str) -> Optional[Dict]:
        """Get data from cache"""
        try:
            cached = redis_client.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            print(f"Cache read failed: {e}")
        return None
    
    def set_cached_data(self, key: str, data: Dict, ttl: int = 300):
        """Set data in cache with TTL"""
        try:
            redis_client.setex(
                key, 
                ttl, 
                json.dumps(data)
            )
        except Exception as e:
            print(f"Cache write failed: {e}")
    
    def process_request(self, event: Dict) -> Dict:
        """Main processing logic"""
        request_id = event.get('requestId')
        
        # Check cache first
        cached_result = self.get_cached_data(f"result:{request_id}")
        if cached_result:
            return cached_result
        
        # Process data
        result = self.heavy_computation(event)
        
        # Cache result
        self.set_cached_data(f"result:{request_id}", result)
        
        return result
    
    def heavy_computation(self, event: Dict) -> Dict:
        """Simulated heavy computation"""
        # Use connection from pool
        conn = postgres_pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM orders WHERE customer_id = %s",
                (event.get('customerId'),)
            )
            orders = cursor.fetchall()
            cursor.close()
            
            # Process with pandas
            df = pd.DataFrame(orders)
            summary = df.describe().to_dict()
            
            return {
                'summary': summary,
                'count': len(orders)
            }
            
        finally:
            postgres_pool.putconn(conn)

# Initialize handler outside of handler function
handler_instance = OptimizedHandler()

def lambda_handler(event, context):
    """Lambda entry point"""
    try:
        # Use pre-initialized handler
        result = handler_instance.process_request(event)
        
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
        
    except Exception as e:
        print(f"Error processing request: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

# Provisioned concurrency warm-up
def provision_concurrency_warmup():
    """Called when provisioned concurrency is initialized"""
    print("Warming up provisioned concurrency")
    handler_instance.warm_connections()
    
    # Pre-load ML models if needed
    # model = load_model()
    
    # Pre-compile regex patterns
    # patterns = compile_patterns()
```

### Lambda Extensions for Monitoring

```python
#!/usr/bin/env python3
# Lambda Extension for custom metrics collection

import json
import os
import sys
import time
import requests
from threading import Thread
from queue import Queue
import signal

# Extension API endpoints
LAMBDA_EXTENSION_NAME = "custom-metrics-extension"
RUNTIME_API_ENDPOINT = f"http://{os.environ['AWS_LAMBDA_RUNTIME_API']}/2020-01-01/extension"

class MetricsExtension:
    def __init__(self):
        self.metrics_queue = Queue()
        self.running = True
        
    def register_extension(self):
        """Register the extension with Lambda"""
        response = requests.post(
            f"{RUNTIME_API_ENDPOINT}/register",
            json={
                "events": ["INVOKE", "SHUTDOWN"]
            },
            headers={
                "Lambda-Extension-Name": LAMBDA_EXTENSION_NAME
            }
        )
        ext_id = response.headers.get("Lambda-Extension-Identifier")
        return ext_id
    
    def process_events(self, ext_id):
        """Process extension lifecycle events"""
        while self.running:
            response = requests.get(
                f"{RUNTIME_API_ENDPOINT}/event/next",
                headers={
                    "Lambda-Extension-Identifier": ext_id
                }
            )
            
            event = response.json()
            event_type = event.get("eventType")
            
            if event_type == "INVOKE":
                self.handle_invoke(event)
            elif event_type == "SHUTDOWN":
                self.handle_shutdown()
                break
    
    def handle_invoke(self, event):
        """Handle function invocation"""
        request_id = event.get("requestId")
        
        # Collect metrics
        metrics = {
            "requestId": request_id,
            "timestamp": time.time(),
            "memorySize": os.environ.get("AWS_LAMBDA_FUNCTION_MEMORY_SIZE"),
            "region": os.environ.get("AWS_REGION"),
            "functionName": os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
        }
        
        self.metrics_queue.put(metrics)
        
        # Batch and send metrics
        if self.metrics_queue.qsize() >= 10:
            self.flush_metrics()
    
    def handle_shutdown(self):
        """Handle extension shutdown"""
        print("Extension shutting down")
        self.running = False
        self.flush_metrics()
    
    def flush_metrics(self):
        """Send metrics to monitoring service"""
        metrics_batch = []
        
        while not self.metrics_queue.empty():
            metrics_batch.append(self.metrics_queue.get())
        
        if metrics_batch:
            # Send to CloudWatch, Datadog, etc.
            self.send_to_monitoring(metrics_batch)
    
    def send_to_monitoring(self, metrics):
        """Send metrics to monitoring service"""
        try:
            # Example: Send to CloudWatch
            cloudwatch = boto3.client('cloudwatch')
            
            metric_data = []
            for metric in metrics:
                metric_data.append({
                    'MetricName': 'FunctionInvocation',
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': metric['timestamp'],
                    'Dimensions': [
                        {
                            'Name': 'FunctionName',
                            'Value': metric['functionName']
                        }
                    ]
                })
            
            cloudwatch.put_metric_data(
                Namespace='CustomLambdaMetrics',
                MetricData=metric_data
            )
            
        except Exception as e:
            print(f"Failed to send metrics: {e}")

def main():
    extension = MetricsExtension()
    ext_id = extension.register_extension()
    extension.process_events(ext_id)

if __name__ == "__main__":
    main()
```

## Cost Management

### Cost Optimization Strategies (Your Finance Team Will Thank You)

True story: we once had a Lambda function with an infinite loop that cost us $30k in one weekend. Don't be like us. Here's how to avoid bankruptcy:

```python
# Cost-optimized serverless architecture
import json
import boto3
import gzip
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Any

class CostOptimizer:
    def __init__(self):
        self.s3 = boto3.client('s3')
        self.lambda_client = boto3.client('lambda')
        self.cloudwatch = boto3.client('cloudwatch')
        
    def optimize_lambda_memory(self, function_name: str) -> Dict:
        """Auto-tune Lambda memory for cost/performance balance"""
        
        # Get current configuration
        response = self.lambda_client.get_function_configuration(
            FunctionName=function_name
        )
        current_memory = response['MemorySize']
        
        # Get performance metrics
        metrics = self.get_lambda_metrics(function_name)
        
        # Calculate optimal memory
        optimal_memory = self.calculate_optimal_memory(
            metrics, 
            current_memory
        )
        
        if optimal_memory != current_memory:
            # Update function configuration
            self.lambda_client.update_function_configuration(
                FunctionName=function_name,
                MemorySize=optimal_memory
            )
            
            return {
                'optimized': True,
                'previous_memory': current_memory,
                'new_memory': optimal_memory,
                'estimated_savings': self.estimate_savings(
                    current_memory, 
                    optimal_memory, 
                    metrics
                )
            }
        
        return {'optimized': False, 'current_memory': current_memory}
    
    def calculate_optimal_memory(self, metrics: Dict, current: int) -> int:
        """Calculate optimal memory allocation"""
        avg_duration = metrics.get('avg_duration', 0)
        max_memory_used = metrics.get('max_memory_used', 0)
        
        # Add 20% buffer to max memory used
        recommended = int(max_memory_used * 1.2)
        
        # Round to nearest 64MB increment
        recommended = ((recommended + 63) // 64) * 64
        
        # Ensure within Lambda limits
        return max(128, min(recommended, 10240))
    
    def implement_request_batching(self, events: List[Dict]) -> List[Dict]:
        """Batch multiple requests to reduce invocations"""
        
        batched_events = []
        current_batch = []
        current_size = 0
        max_batch_size = 6000000  # 6MB limit
        
        for event in events:
            event_size = len(json.dumps(event))
            
            if current_size + event_size > max_batch_size:
                # Send current batch
                if current_batch:
                    batched_events.append({
                        'batch': current_batch,
                        'count': len(current_batch)
                    })
                current_batch = [event]
                current_size = event_size
            else:
                current_batch.append(event)
                current_size += event_size
        
        # Add remaining batch
        if current_batch:
            batched_events.append({
                'batch': current_batch,
                'count': len(current_batch)
            })
        
        return batched_events
    
    def compress_payload(self, data: Dict) -> str:
        """Compress payload to reduce data transfer costs"""
        json_str = json.dumps(data)
        compressed = gzip.compress(json_str.encode())
        return base64.b64encode(compressed).decode()
    
    def decompress_payload(self, compressed_data: str) -> Dict:
        """Decompress payload"""
        compressed = base64.b64decode(compressed_data)
        decompressed = gzip.decompress(compressed)
        return json.loads(decompressed.decode())
    
    def implement_caching_strategy(self, key: str, data: Any, ttl: int = 300):
        """Implement intelligent caching to reduce compute"""
        
        # Use S3 for large objects, Parameter Store for small
        data_size = len(json.dumps(data))
        
        if data_size < 4096:  # 4KB limit for Parameter Store
            # Use Parameter Store (free tier)
            ssm = boto3.client('ssm')
            ssm.put_parameter(
                Name=f"/cache/{key}",
                Value=json.dumps(data),
                Type='String',
                Overwrite=True
            )
        else:
            # Use S3 with lifecycle rules
            self.s3.put_object(
                Bucket='cache-bucket',
                Key=f"cache/{key}",
                Body=json.dumps(data),
                Metadata={
                    'ttl': str(ttl),
                    'expires': str(datetime.utcnow() + timedelta(seconds=ttl))
                }
            )
    
    def analyze_invocation_patterns(self, function_name: str) -> Dict:
        """Analyze patterns to optimize scheduling"""
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=7)
        
        response = self.cloudwatch.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName='Invocations',
            Dimensions=[
                {'Name': 'FunctionName', 'Value': function_name}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,  # Hourly
            Statistics=['Sum']
        )
        
        # Analyze patterns
        hourly_invocations = {}
        for point in response['Datapoints']:
            hour = point['Timestamp'].hour
            if hour not in hourly_invocations:
                hourly_invocations[hour] = []
            hourly_invocations[hour].append(point['Sum'])
        
        # Calculate average invocations per hour
        patterns = {}
        for hour, invocations in hourly_invocations.items():
            patterns[hour] = {
                'average': sum(invocations) / len(invocations),
                'peak': max(invocations),
                'minimum': min(invocations)
            }
        
        return patterns
    
    def recommend_provisioned_concurrency(self, patterns: Dict) -> Dict:
        """Recommend provisioned concurrency settings"""
        
        recommendations = []
        
        for hour, stats in patterns.items():
            if stats['average'] > 100:  # High traffic hour
                recommendations.append({
                    'hour': hour,
                    'provisioned_concurrency': int(stats['average'] * 0.8),
                    'estimated_cost': self.calculate_provisioned_cost(
                        int(stats['average'] * 0.8)
                    )
                })
        
        return {
            'recommendations': recommendations,
            'estimated_monthly_cost': sum(
                r['estimated_cost'] for r in recommendations
            ) * 30
        }
    
    def calculate_provisioned_cost(self, concurrency: int) -> float:
        """Calculate provisioned concurrency cost"""
        # AWS pricing example (varies by region)
        price_per_gb_hour = 0.0000166667
        price_per_provisioned = 0.0000041667
        
        memory_gb = 0.512  # 512MB example
        hours = 1
        
        compute_cost = concurrency * memory_gb * hours * price_per_gb_hour
        provisioned_cost = concurrency * hours * price_per_provisioned
        
        return compute_cost + provisioned_cost

# Usage in Lambda function
cost_optimizer = CostOptimizer()

def lambda_handler(event, context):
    """Cost-optimized Lambda handler"""
    
    # Check if batch processing
    if 'batch' in event:
        results = []
        for item in event['batch']:
            results.append(process_item(item))
        return {'results': results}
    
    # Check cache first
    cache_key = generate_cache_key(event)
    cached_result = get_from_cache(cache_key)
    
    if cached_result:
        return cached_result
    
    # Process request
    result = process_item(event)
    
    # Cache result
    cost_optimizer.implement_caching_strategy(cache_key, result)
    
    return result
```

## Security Best Practices

### Secure Serverless Implementation

```python
# Security-hardened Lambda function
import json
import os
import boto3
import hashlib
import hmac
from typing import Dict, Any, Optional
from functools import wraps
import jwt
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Environment variables
SECRET_KEY = os.environ['SECRET_KEY']
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '').split(',')

class SecurityValidator:
    def __init__(self):
        self.kms = boto3.client('kms')
        self.secrets_manager = boto3.client('secretsmanager')
        
    def validate_jwt_token(self, token: str) -> Optional[Dict]:
        """Validate JWT token"""
        try:
            decoded = jwt.decode(
                token,
                self.get_secret('jwt_secret'),
                algorithms=['HS256']
            )
            return decoded
        except jwt.ExpiredSignatureError:
            logger.error("Token expired")
            return None
        except jwt.InvalidTokenError:
            logger.error("Invalid token")
            return None
    
    def get_secret(self, secret_name: str) -> str:
        """Retrieve secret from AWS Secrets Manager"""
        try:
            response = self.secrets_manager.get_secret_value(
                SecretId=secret_name
            )
            return response['SecretString']
        except Exception as e:
            logger.error(f"Failed to retrieve secret: {e}")
            raise
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data using KMS"""
        response = self.kms.encrypt(
            KeyId=os.environ['KMS_KEY_ID'],
            Plaintext=data
        )
        return base64.b64encode(response['CiphertextBlob']).decode()
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data using KMS"""
        ciphertext = base64.b64decode(encrypted_data)
        response = self.kms.decrypt(CiphertextBlob=ciphertext)
        return response['Plaintext'].decode()
    
    def validate_input(self, data: Dict) -> bool:
        """Validate and sanitize input data"""
        # Check for SQL injection patterns
        sql_patterns = ['DROP', 'DELETE', 'INSERT', 'UPDATE', '--', ';']
        data_str = json.dumps(data).upper()
        
        for pattern in sql_patterns:
            if pattern in data_str:
                logger.warning(f"Potential SQL injection detected: {pattern}")
                return False
        
        # Check for XSS patterns
        xss_patterns = ['<script', 'javascript:', 'onerror=', 'onclick=']
        data_str_lower = json.dumps(data).lower()
        
        for pattern in xss_patterns:
            if pattern in data_str_lower:
                logger.warning(f"Potential XSS detected: {pattern}")
                return False
        
        return True
    
    def validate_api_signature(self, headers: Dict, body: str) -> bool:
        """Validate API request signature"""
        signature = headers.get('X-Signature')
        if not signature:
            return False
        
        expected_signature = hmac.new(
            SECRET_KEY.encode(),
            body.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)

def require_auth(f):
    """Decorator for authentication"""
    @wraps(f)
    def decorated_function(event, context):
        validator = SecurityValidator()
        
        # Extract token from Authorization header
        auth_header = event.get('headers', {}).get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Unauthorized'})
            }
        
        token = auth_header.replace('Bearer ', '')
        user = validator.validate_jwt_token(token)
        
        if not user:
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Invalid token'})
            }
        
        # Add user to event
        event['user'] = user
        return f(event, context)
    
    return decorated_function

def validate_cors(origin: str) -> Dict:
    """Validate CORS origin"""
    if origin in ALLOWED_ORIGINS or '*' in ALLOWED_ORIGINS:
        return {
            'Access-Control-Allow-Origin': origin,
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        }
    return {}

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics
@require_auth
def lambda_handler(event, context):
    """Secure Lambda handler"""
    
    validator = SecurityValidator()
    
    # Validate request signature
    if not validator.validate_api_signature(
        event.get('headers', {}),
        event.get('body', '')
    ):
        logger.warning("Invalid request signature")
        return {
            'statusCode': 403,
            'body': json.dumps({'error': 'Forbidden'})
        }
    
    # Parse and validate input
    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid JSON'})
        }
    
    if not validator.validate_input(body):
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid input'})
        }
    
    # Process request
    try:
        # Encrypt sensitive data before storing
        if 'ssn' in body:
            body['ssn'] = validator.encrypt_sensitive_data(body['ssn'])
        
        result = process_secure_request(body, event['user'])
        
        # Add security headers
        headers = {
            'Content-Type': 'application/json',
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'
        }
        
        # Add CORS headers if origin is valid
        origin = event.get('headers', {}).get('Origin')
        if origin:
            headers.update(validate_cors(origin))
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(result)
        }
        
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        metrics.add_metric(name="ProcessingError", unit=MetricUnit.Count, value=1)
        
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }

def process_secure_request(data: Dict, user: Dict) -> Dict:
    """Process the secured request"""
    # Implementation specific to your business logic
    return {
        'success': True,
        'userId': user['id'],
        'processed': True
    }
```

## Testing Serverless Applications

### Unit Testing

```python
# test_lambda_function.py
import unittest
import json
from unittest.mock import patch, MagicMock
import boto3
from moto import mock_dynamodb, mock_s3, mock_sqs
from lambda_function import lambda_handler

class TestLambdaFunction(unittest.TestCase):
    
    @mock_dynamodb
    def setUp(self):
        """Set up test fixtures"""
        # Create mock DynamoDB table
        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        self.table = self.dynamodb.create_table(
            TableName='test-table',
            KeySchema=[
                {'AttributeName': 'id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Set environment variables
        os.environ['TABLE_NAME'] = 'test-table'
        os.environ['REGION'] = 'us-east-1'
    
    def test_successful_request(self):
        """Test successful Lambda execution"""
        event = {
            'body': json.dumps({
                'name': 'Test User',
                'email': 'test@example.com'
            })
        }
        
        context = MagicMock()
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertTrue(body['success'])
    
    @mock_s3
    def test_s3_integration(self):
        """Test S3 integration"""
        # Create mock S3 bucket
        s3 = boto3.client('s3', region_name='us-east-1')
        s3.create_bucket(Bucket='test-bucket')
        
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': 'test-file.txt'}
                }
            }]
        }
        
        context = MagicMock()
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 200)
    
    @mock_sqs
    def test_sqs_processing(self):
        """Test SQS message processing"""
        # Create mock SQS queue
        sqs = boto3.client('sqs', region_name='us-east-1')
        queue_url = sqs.create_queue(QueueName='test-queue')['QueueUrl']
        
        event = {
            'Records': [{
                'body': json.dumps({'action': 'process', 'id': '123'}),
                'messageId': 'msg-123',
                'receiptHandle': 'handle-123'
            }]
        }
        
        context = MagicMock()
        response = lambda_handler(event, context)
        
        self.assertEqual(response['batchItemFailures'], [])
    
    def test_error_handling(self):
        """Test error handling"""
        event = {
            'body': 'invalid-json'
        }
        
        context = MagicMock()
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
    
    @patch('lambda_function.requests.get')
    def test_external_api_call(self, mock_get):
        """Test external API integration"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {'data': 'test'}
        
        event = {
            'queryStringParameters': {
                'apiEndpoint': 'https://api.example.com/data'
            }
        }
        
        context = MagicMock()
        response = lambda_handler(event, context)
        
        self.assertEqual(response['statusCode'], 200)
        mock_get.assert_called_once()

if __name__ == '__main__':
    unittest.main()
```

### Integration Testing

```python
# integration_test.py
import boto3
import json
import time
from typing import Dict, Any

class ServerlessIntegrationTest:
    def __init__(self):
        self.lambda_client = boto3.client('lambda')
        self.api_gateway = boto3.client('apigatewayv2')
        self.step_functions = boto3.client('stepfunctions')
        
    def test_end_to_end_workflow(self):
        """Test complete serverless workflow"""
        
        # Step 1: Trigger Lambda via API Gateway
        api_response = self.invoke_api_endpoint({
            'orderId': 'test-123',
            'items': [
                {'sku': 'ITEM-1', 'quantity': 2},
                {'sku': 'ITEM-2', 'quantity': 1}
            ]
        })
        
        assert api_response['statusCode'] == 200
        
        # Step 2: Verify Step Function execution started
        execution_arn = json.loads(api_response['body'])['executionArn']
        
        # Step 3: Wait for workflow completion
        workflow_result = self.wait_for_execution(execution_arn)
        
        assert workflow_result['status'] == 'SUCCEEDED'
        
        # Step 4: Verify data in DynamoDB
        order = self.get_order_from_db('test-123')
        assert order['status'] == 'completed'
        
        # Step 5: Check SQS for notifications
        messages = self.check_notification_queue()
        assert len(messages) > 0
        
        return True
    
    def invoke_api_endpoint(self, payload: Dict) -> Dict:
        """Invoke API Gateway endpoint"""
        response = self.lambda_client.invoke(
            FunctionName='api-handler',
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'httpMethod': 'POST',
                'path': '/orders',
                'body': json.dumps(payload)
            })
        )
        
        return json.loads(response['Payload'].read())
    
    def wait_for_execution(self, execution_arn: str, timeout: int = 60) -> Dict:
        """Wait for Step Function execution to complete"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            response = self.step_functions.describe_execution(
                executionArn=execution_arn
            )
            
            if response['status'] in ['SUCCEEDED', 'FAILED', 'ABORTED']:
                return response
            
            time.sleep(2)
        
        raise TimeoutError("Execution did not complete within timeout")
    
    def get_order_from_db(self, order_id: str) -> Dict:
        """Retrieve order from DynamoDB"""
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('orders')
        
        response = table.get_item(Key={'orderId': order_id})
        return response.get('Item')
    
    def check_notification_queue(self) -> List[Dict]:
        """Check SQS queue for notifications"""
        sqs = boto3.client('sqs')
        
        response = sqs.receive_message(
            QueueUrl='https://sqs.us-east-1.amazonaws.com/123456789/notifications',
            MaxNumberOfMessages=10
        )
        
        return response.get('Messages', [])

# Run integration tests
if __name__ == '__main__':
    tester = ServerlessIntegrationTest()
    
    try:
        result = tester.test_end_to_end_workflow()
        print("✅ All integration tests passed")
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        raise
```

## Monitoring and Observability

### Distributed Tracing with X-Ray

```python
# Instrumented Lambda with X-Ray
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all
import json
import boto3

# Patch all AWS SDK calls
patch_all()

@xray_recorder.capture('lambda_handler')
def lambda_handler(event, context):
    """Lambda handler with X-Ray tracing"""
    
    # Add custom metadata
    xray_recorder.current_subsegment().put_metadata(
        'request_id', 
        context.request_id
    )
    
    # Trace custom function
    result = process_request(event)
    
    return {
        'statusCode': 200,
        'body': json.dumps(result)
    }

@xray_recorder.capture('process_request')
def process_request(event):
    """Process request with tracing"""
    
    # Add annotations for filtering
    xray_recorder.current_subsegment().put_annotation(
        'customer_id', 
        event.get('customerId')
    )
    
    # Trace DynamoDB operation
    with xray_recorder.capture('dynamodb_query'):
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('orders')
        
        response = table.query(
            KeyConditionExpression='customerId = :id',
            ExpressionAttributeValues={':id': event['customerId']}
        )
    
    # Trace external HTTP call
    with xray_recorder.capture('external_api'):
        result = call_external_api(event)
    
    return {
        'orders': response['Items'],
        'external_data': result
    }

@xray_recorder.capture('external_api_call')
def call_external_api(data):
    """Make external API call with tracing"""
    import requests
    
    # Add custom segment
    subsegment = xray_recorder.current_subsegment()
    subsegment.put_http_meta(
        'url', 
        'https://api.example.com/validate'
    )
    
    try:
        response = requests.post(
            'https://api.example.com/validate',
            json=data,
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        # Record exception in X-Ray
        subsegment.add_exception(e)
        raise
```

## Best Practices (Learned the Hard Way)

1. **Function Design**
   - Keep functions small and single-purpose
   - Minimize cold starts with provisioned concurrency
   - Use connection pooling for databases
   - Implement proper error handling and retries

2. **Performance**
   - Optimize memory allocation
   - Use Lambda layers for shared dependencies
   - Implement caching strategies
   - Batch processing when possible

3. **Security**
   - Use IAM roles with least privilege
   - Encrypt sensitive data with KMS
   - Validate all inputs
   - Implement API authentication

4. **Cost Optimization**
   - Right-size Lambda memory
   - Use Step Functions for orchestration
   - Implement request batching
   - Monitor and analyze usage patterns

5. **Observability**
   - Implement distributed tracing
   - Use structured logging
   - Set up alerts and dashboards
   - Monitor cold starts and errors

6. **Testing**
   - Write comprehensive unit tests
   - Implement integration tests
   - Use local testing tools
   - Test error scenarios

Look, serverless isn't perfect, but for the right use cases, it's absolutely brilliant. Start small, measure everything, and don't try to force-fit every workload into Lambda. Your future self will thank you.

And remember: just because you CAN make everything serverless doesn't mean you SHOULD. Sometimes a boring old container is exactly what you need.
