#!/usr/bin/env python3
"""
Local testing script for the Verify Service
Tests the Lambda function with sample S3 events without requiring AWS
"""

import json
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Mock boto3 before importing lambda_function
import boto3
from moto import mock_s3, mock_dynamodb

# Now import the lambda function
from lambda_function import lambda_handler


def create_s3_event(bucket_name: str, object_key: str, file_size: int) -> dict:
    """Create a mock S3 event"""
    return {
        "Records": [{
            "s3": {
                "bucket": {"name": bucket_name},
                "object": {
                    "key": object_key,
                    "size": file_size
                }
            }
        }]
    }


@mock_s3
@mock_dynamodb
def test_valid_model():
    """Test with a valid model"""
    print("\n" + "="*60)
    print("Testing VALID model")
    print("="*60)
    
    # Setup S3
    s3_client = boto3.client('s3', region_name='us-east-1')
    bucket_name = 'test-model-bucket'
    s3_client.create_bucket(Bucket=bucket_name)
    
    # Read valid model file
    model_path = 'tests/fixtures/valid_model.tar.gz'
    if not os.path.exists(model_path):
        print(f"ERROR: Test fixture not found: {model_path}")
        print("Please ensure the test fixtures are available")
        return
    
    with open(model_path, 'rb') as f:
        model_content = f.read()
    
    # Upload to mock S3
    object_key = 'models/user123/valid_model.tar.gz'
    s3_client.put_object(
        Bucket=bucket_name,
        Key=object_key,
        Body=model_content
    )
    
    # Setup DynamoDB
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    dynamodb.create_table(
        TableName='ModelRegistry',
        KeySchema=[
            {'AttributeName': 'model_id', 'KeyType': 'HASH'},
            {'AttributeName': 'validation_timestamp', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'model_id', 'AttributeType': 'S'},
            {'AttributeName': 'validation_timestamp', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )
    dynamodb.create_table(
        TableName='UploadStatus',
        KeySchema=[
            {'AttributeName': 'model_id', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'model_id', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )
    
    # Set environment variables
    os.environ['MODEL_REGISTRY_TABLE'] = 'ModelRegistry'
    os.environ['UPLOAD_STATUS_TABLE'] = 'UploadStatus'
    
    # Create event
    event = create_s3_event(bucket_name, object_key, len(model_content))
    
    # Invoke Lambda
    context = Mock()
    context.function_name = 'test-verify'
    
    try:
        response = lambda_handler(event, context)
        print(f"\nResponse Status: {response['statusCode']}")
        body = json.loads(response['body'])
        print(f"Model ID: {body.get('model_id')}")
        print(f"Status: {body.get('status')}")
        
        if 'report' in body:
            report = body['report']
            print(f"\nChecks Passed: {len(report.get('checks_passed', []))}")
            for check in report.get('checks_passed', []):
                print(f"  ✓ {check}")
            
            if 'errors' in report:
                print(f"\nErrors Found: {len(report['errors'])}")
                for error in report['errors']:
                    print(f"  ✗ {error['code']}: {error['message']}")
        
        print("\n✅ Test completed successfully!")
        return body.get('status') == 'VALID'
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


@mock_s3
@mock_dynamodb
def test_invalid_model():
    """Test with an invalid model"""
    print("\n" + "="*60)
    print("Testing INVALID model (should fail validation)")
    print("="*60)
    
    # Setup S3
    s3_client = boto3.client('s3', region_name='us-east-1')
    bucket_name = 'test-model-bucket'
    s3_client.create_bucket(Bucket=bucket_name)
    
    # Read invalid model file
    model_path = 'tests/fixtures/invalid_model.tar.gz'
    if not os.path.exists(model_path):
        print(f"ERROR: Test fixture not found: {model_path}")
        return
    
    with open(model_path, 'rb') as f:
        model_content = f.read()
    
    # Upload to mock S3
    object_key = 'models/user123/invalid_model.tar.gz'
    s3_client.put_object(
        Bucket=bucket_name,
        Key=object_key,
        Body=model_content
    )
    
    # Setup DynamoDB
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    dynamodb.create_table(
        TableName='ModelRegistry',
        KeySchema=[
            {'AttributeName': 'model_id', 'KeyType': 'HASH'},
            {'AttributeName': 'validation_timestamp', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'model_id', 'AttributeType': 'S'},
            {'AttributeName': 'validation_timestamp', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )
    dynamodb.create_table(
        TableName='UploadStatus',
        KeySchema=[
            {'AttributeName': 'model_id', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'model_id', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )
    
    # Set environment variables
    os.environ['MODEL_REGISTRY_TABLE'] = 'ModelRegistry'
    os.environ['UPLOAD_STATUS_TABLE'] = 'UploadStatus'
    
    # Create event
    event = create_s3_event(bucket_name, object_key, len(model_content))
    
    # Invoke Lambda
    context = Mock()
    context.function_name = 'test-verify'
    
    try:
        response = lambda_handler(event, context)
        print(f"\nResponse Status: {response['statusCode']}")
        body = json.loads(response['body'])
        print(f"Model ID: {body.get('model_id')}")
        print(f"Status: {body.get('status')}")
        
        if 'report' in body:
            report = body['report']
            if 'errors' in report:
                print(f"\nErrors Found: {len(report['errors'])}")
                for error in report['errors']:
                    print(f"  ✗ [{error['severity']}] {error['code']}: {error['message']}")
        
        print("\n✅ Test completed (model correctly rejected as INVALID)")
        return body.get('status') == 'INVALID'
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("AlphaBack Verify Service - Local Testing")
    print("="*60)
    
    # Test valid model
    valid_result = test_valid_model()
    
    # Test invalid model
    invalid_result = test_invalid_model()
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    print(f"Valid Model Test: {'PASSED' if valid_result else 'FAILED'}")
    print(f"Invalid Model Test: {'PASSED' if invalid_result else 'FAILED'}")
    
    if valid_result and invalid_result:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed")
        sys.exit(1)

