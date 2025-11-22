"""
AlphaBack Verify Service - Lambda Handler for Java .class Files
Validates a single compiled Java .class file directly

Triggered by S3 upload events when .class files are uploaded
"""

import json
import os
import boto3
from typing import Dict, Any
import logging

from verifier.java_bytecode_scanner import JavaBytecodeScanner
from verifier.report_generator import ReportGenerator

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Environment variables
MODEL_REGISTRY_TABLE = os.environ.get('MODEL_REGISTRY_TABLE', 'ModelRegistry')
UPLOAD_STATUS_TABLE = os.environ.get('UPLOAD_STATUS_TABLE', 'UploadStatus')


def load_config():
    """Load verification configuration from local files"""
    config_dir = os.path.join(os.path.dirname(__file__), 'config')

    with open(os.path.join(config_dir, 'allowed_imports.json'), 'r') as f:
        security_config = json.load(f)

    with open(os.path.join(config_dir, 'validation_rules.json'), 'r') as f:
        validation_config = json.load(f)

    return security_config, validation_config


# Initialize configuration at cold start
security_config, validation_config = load_config()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler - triggered by S3 upload of .class files

    Args:
        event: S3 event containing bucket and object information
        context: Lambda context object

    Returns:
        Response dictionary with status and validation result
    """
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        # Extract S3 information from event
        record = event['Records'][0]
        bucket_name = record['s3']['bucket']['name']
        object_key = record['s3']['object']['key']
        file_size = record['s3']['object']['size']

        logger.info(f"Processing: s3://{bucket_name}/{object_key} ({file_size} bytes)")

        # Initialize report generator
        report = ReportGenerator()
        report.start_timing()

        # Extract model_id from the filename
        # e.g., "models/user123/TrendFollower.class" → "TrendFollower"
        filename = object_key.split('/')[-1]
        model_id = filename.replace('.class', '')

        logger.info(f"Model ID: {model_id}")

        # Step 1: Check file size
        max_size = validation_config.get('max_file_size_bytes', 10485760)
        if file_size > max_size:
            report.add_error(
                "FILE_TOO_LARGE",
                f"File size ({file_size} bytes) exceeds maximum ({max_size} bytes)",
                "CRITICAL"
            )
            return _complete_validation(report, model_id, bucket_name, object_key, "INVALID")

        report.add_check_passed("file_size_validation")

        # Step 2: Download .class file from S3
        logger.info("Downloading .class file...")
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        class_bytes = response['Body'].read()

        # Step 3: Initialize bytecode scanner
        bytecode_scanner = JavaBytecodeScanner(
            allowed_packages=security_config['allowed_packages'],
            blocked_packages=security_config['blocked_packages'],
            blocked_classes=security_config['blocked_classes'],
            blocked_methods=security_config['blocked_methods']
        )

        # Step 4: Verify it's a valid .class file
        logger.info("Parsing .class file...")
        class_info = bytecode_scanner.get_class_info(class_bytes)

        if 'error' in class_info:
            report.add_error(
                "INVALID_CLASS_FILE",
                f"Cannot parse .class file: {class_info['error']}",
                "CRITICAL"
            )
            return _complete_validation(report, model_id, bucket_name, object_key, "INVALID")

        logger.info(f"Class: {class_info['class_name']}, Interfaces: {class_info['interfaces']}")
        report.add_check_passed("class_file_valid")

        # Step 5: Check implements Model interface
        logger.info("Checking Model interface...")
        required_interface = validation_config['required_interface']

        if not bytecode_scanner.check_implements_interface(class_bytes, required_interface, report):
            return _complete_validation(report, model_id, bucket_name, object_key, "INVALID")

        # Step 6: Check simulateStep method exists
        logger.info("Checking simulateStep method...")
        required_method = validation_config['required_method_name']
        required_signature = validation_config['required_method_signature']

        if not bytecode_scanner.check_has_method(class_bytes, required_method, required_signature, report):
            return _complete_validation(report, model_id, bucket_name, object_key, "INVALID")

        # Step 7: Scan for security violations
        logger.info("Scanning for security violations...")
        if not bytecode_scanner.scan_class_file(class_bytes, report, model_id):
            return _complete_validation(report, model_id, bucket_name, object_key, "INVALID")

        # All checks passed!
        logger.info(f"Model {model_id} VALID")
        return _complete_validation(report, model_id, bucket_name, object_key, "VALID")

    except KeyError as e:
        logger.error(f"Invalid event: {str(e)}")
        return {'statusCode': 400, 'body': json.dumps({'error': str(e)})}

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}


def _complete_validation(report: ReportGenerator, model_id: str,
                        bucket_name: str, object_key: str,
                        status: str) -> Dict[str, Any]:
    """Complete validation and write results to DynamoDB"""
    report.end_timing()
    validation_report = report.generate_report(model_id)
    logger.info(f"Result: {json.dumps(validation_report)}")

    try:
        # Write to Model Registry
        table = dynamodb.Table(MODEL_REGISTRY_TABLE)
        table.put_item(Item={
            'model_id': model_id,
            's3_bucket': bucket_name,
            's3_key': object_key,
            'validation_status': status,
            'validation_timestamp': validation_report['timestamp'],
            'validation_report': json.dumps(validation_report),
            'checks_passed': validation_report.get('checks_passed', []),
            'execution_time_ms': validation_report['execution_time_ms']
        })

        # Update Upload Status
        table = dynamodb.Table(UPLOAD_STATUS_TABLE)
        table.update_item(
            Key={'model_id': model_id},
            UpdateExpression='SET validation_status = :s, validation_timestamp = :t, validation_complete = :c',
            ExpressionAttributeValues={
                ':s': status,
                ':t': validation_report['timestamp'],
                ':c': True
            }
        )
    except Exception as e:
        logger.error(f"DynamoDB error: {str(e)}")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'model_id': model_id,
            'status': status,
            'report': validation_report
        })
    }
