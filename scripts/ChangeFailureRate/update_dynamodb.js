// update_dynamodb.js
const AWS = require('aws-sdk');
const argv = require('minimist')(process.argv.slice(2));

const dynamodb = new AWS.DynamoDB.DocumentClient();

const updateDeploymentStatus = async (status) => {
  const params = {
    TableName: 'DeploymentStatus',
    Item: {
      id: Date.now().toString(),
      status: status,
      timestamp: new Date().toISOString(),
    },
  };

  try {
    await dynamodb.put(params).promise();
    console.log('Deployment status updated in DynamoDB');
  } catch (error) {
    console.error('Error updating DynamoDB:', error);
    process.exit(1);
  }
};

updateDeploymentStatus(argv.status);
