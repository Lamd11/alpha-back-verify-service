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
    """
    logger.info(f"Received event: {json.dumps(event)}")

    report = ReportGenerator()
    report.start_timing()
    model_id = "unknown"

    try:
        # Extract S3 information from event
        record = event['Records'][0]
        bucket_name = record['s3']['bucket']['name']
        object_key = record['s3']['object']['key']
        file_size = record['s3']['object']['size']

        # Extract model_id from filename
        filename = object_key.split('/')[-1]
        model_id = filename.replace('.class', '')

        logger.info(f"Processing: {model_id} ({file_size} bytes)")

        # CHECK 1: File Size
        max_size = validation_config.get('max_file_size_bytes', 10485760)
        if file_size > max_size:
            report.add_check_failed("fileSize", f"File too large: {file_size} bytes (max: {max_size})")
            return _complete_validation(report, model_id, bucket_name, object_key)

        report.add_check_passed("fileSize")

        # CHECK 2: S3 File Readable
        logger.info("Downloading .class file...")
        try:
            response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
            class_bytes = response['Body'].read()
            report.add_check_passed("s3FileReadable")
        except Exception as e:
            report.add_check_failed("s3FileReadable", f"Cannot read file from S3: {str(e)}")
            return _complete_validation(report, model_id, bucket_name, object_key)

        # Initialize bytecode scanner
        bytecode_scanner = JavaBytecodeScanner(
            allowed_packages=security_config['allowed_packages'],
            blocked_packages=security_config['blocked_packages'],
            blocked_classes=security_config['blocked_classes'],
            blocked_methods=security_config['blocked_methods']
        )

        # CHECK 3: Valid Class File
        logger.info("Parsing .class file...")
        class_info = bytecode_scanner.get_class_info(class_bytes)

        if 'error' in class_info:
            report.add_check_failed("classFileValid", f"Invalid .class file: {class_info['error']}")
            return _complete_validation(report, model_id, bucket_name, object_key)

        report.add_check_passed("classFileValid")
        logger.info(f"Class: {class_info['class_name']}")

        # CHECK 4: Implements Model Interface
        logger.info("Checking Model interface...")
        required_interface = validation_config['required_interface']

        if not bytecode_scanner.check_implements_interface(class_bytes, required_interface, report):
            return _complete_validation(report, model_id, bucket_name, object_key)

        # CHECK 5: Has simulateStep Method
        logger.info("Checking simulateStep method...")
        required_method = validation_config['required_method_name']
        required_signature = validation_config['required_method_signature']

        if not bytecode_scanner.check_has_method(class_bytes, required_method, required_signature, report):
            return _complete_validation(report, model_id, bucket_name, object_key)

        # CHECK 6: Security Scan (no blocked packages/methods)
        logger.info("Scanning for security violations...")
        if not bytecode_scanner.scan_class_file(class_bytes, report, model_id):
            return _complete_validation(report, model_id, bucket_name, object_key)

        # All checks passed!
        logger.info(f"Model {model_id} VERIFIED")
        return _complete_validation(report, model_id, bucket_name, object_key)

    except KeyError as e:
        logger.error(f"Invalid event: {str(e)}")
        report.add_check_failed("eventParsing", f"Invalid S3 event: {str(e)}")
        return _complete_validation(report, model_id, "", "")

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        report.add_check_failed("unexpectedError", str(e))
        return _complete_validation(report, model_id, "", "")


def _complete_validation(report: ReportGenerator, model_id: str,
                        bucket_name: str, object_key: str) -> Dict[str, Any]:
    """Complete validation and write results to DynamoDB"""
    report.end_timing()
    validation_report = report.generate_report(model_id)

    logger.info(f"Result: verified={validation_report['verified']}, "
                f"errors={len(validation_report['overallErrors'])}")

    # Write to DynamoDB
    try:
        if bucket_name and object_key:
            # Write to Model Registry
            table = dynamodb.Table(MODEL_REGISTRY_TABLE)
            table.put_item(Item={
                'model_id': model_id,
                's3_bucket': bucket_name,
                's3_key': object_key,
                'verified': validation_report['verified'],
                'timestamp': validation_report['timestamp'],
                'report': json.dumps(validation_report),
                'executionTimeMs': validation_report['executionTimeMs']
            })

            # Update Upload Status
            table = dynamodb.Table(UPLOAD_STATUS_TABLE)
            table.update_item(
                Key={'model_id': model_id},
                UpdateExpression='SET verified = :v, #ts = :t, validation_complete = :c',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':v': validation_report['verified'],
                    ':t': validation_report['timestamp'],
                    ':c': True
                }
            )
    except Exception as e:
        logger.error(f"DynamoDB error: {str(e)}")

    return {
        'statusCode': 200,
        'body': json.dumps(validation_report)
    }
