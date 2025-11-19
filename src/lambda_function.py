"""
AlphaBack Verify Service - Lambda Handler
Main entry point for model verification Lambda function

Triggered by S3 upload events, validates models, and writes results to DynamoDB
"""

import json
import os
import boto3
from typing import Dict, Any
import logging

# Import verification modules
from verifier.code_scanner import CodeScanner
from verifier.structure_checker import StructureChecker
from verifier.metadata_validator import MetadataValidator
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

# Load configuration
def load_config():
    """Load verification configuration from local files"""
    config_dir = os.path.join(os.path.dirname(__file__), 'config')

    with open(os.path.join(config_dir, 'allowed_imports.json'), 'r') as f:
        import_config = json.load(f)

    with open(os.path.join(config_dir, 'validation_rules.json'), 'r') as f:
        validation_config = json.load(f)

    return import_config, validation_config


# Initialize configuration at cold start
import_config, validation_config = load_config()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler - triggered by S3 upload events

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

        logger.info(f"Processing model: s3://{bucket_name}/{object_key} ({file_size} bytes)")

        # Initialize report generator
        report = ReportGenerator()
        report.start_timing()

        # Step 1: Download model file from S3
        logger.info("Downloading model from S3...")
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        model_file_content = response['Body'].read()

        # Step 2: Check file size
        logger.info("Checking file size...")
        structure_checker = StructureChecker(
            required_files=validation_config['required_files'],
            max_size_bytes=validation_config['max_file_size_bytes'],
            required_class=validation_config['required_class_name'],
            required_method=validation_config['required_method_name']
        )

        if not structure_checker.check_file_size(file_size, report):
            return _complete_validation(report, None, bucket_name, object_key, "INVALID")

        # Step 3: Extract archive
        logger.info("Extracting model archive...")
        filename = object_key.split('/')[-1]
        extracted_files = structure_checker.extract_archive(model_file_content, filename)

        if extracted_files is None:
            report.add_error(
                "INVALID_ARCHIVE",
                f"Unable to extract archive. Ensure file is .tar.gz or .zip format",
                "CRITICAL"
            )
            return _complete_validation(report, None, bucket_name, object_key, "INVALID")

        # Step 4: Validate structure
        logger.info("Validating model structure...")
        if not structure_checker.validate_structure(extracted_files, report):
            return _complete_validation(report, None, bucket_name, object_key, "INVALID")

        # Step 5: Validate metadata
        logger.info("Validating metadata...")
        metadata_validator = MetadataValidator(
            required_fields=validation_config['required_metadata_fields']
        )

        metadata_content = extracted_files['metadata.json'].decode('utf-8')
        if not metadata_validator.validate(metadata_content, report):
            return _complete_validation(report, None, bucket_name, object_key, "INVALID")

        # Extract model_id for reporting
        model_id = metadata_validator.extract_model_id(metadata_content)
        if not model_id:
            model_id = object_key.replace('/', '_').replace('.tar.gz', '').replace('.zip', '')

        # Step 6: Validate model class structure
        logger.info("Validating model class structure...")
        model_code = extracted_files['model.py'].decode('utf-8')
        if not structure_checker.validate_model_class(model_code, report):
            return _complete_validation(report, model_id, bucket_name, object_key, "INVALID")

        # Step 7: Scan code for security issues
        logger.info("Scanning code for security violations...")
        code_scanner = CodeScanner(
            allowed_imports=import_config['allowed_imports'],
            blocked_imports=import_config['blocked_imports'],
            blocked_builtins=import_config['blocked_builtins']
        )

        if not code_scanner.scan(model_code, report):
            return _complete_validation(report, model_id, bucket_name, object_key, "INVALID")

        # All checks passed!
        logger.info(f"Model {model_id} passed all validation checks")
        return _complete_validation(report, model_id, bucket_name, object_key, "VALID")

    except KeyError as e:
        logger.error(f"Invalid event structure: {str(e)}")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': f'Invalid event structure: {str(e)}'})
        }

    except Exception as e:
        logger.error(f"Unexpected error during validation: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Validation failed: {str(e)}'})
        }


def _complete_validation(report: ReportGenerator, model_id: str,
                        bucket_name: str, object_key: str,
                        status: str) -> Dict[str, Any]:
    """
    Complete validation and write results to DynamoDB

    Args:
        report: Report generator with validation results
        model_id: Model identifier
        bucket_name: S3 bucket name
        object_key: S3 object key
        status: Validation status (VALID or INVALID)

    Returns:
        Lambda response dictionary
    """
    report.end_timing()

    # Use object key as fallback model_id
    if not model_id:
        model_id = object_key.replace('/', '_').replace('.tar.gz', '').replace('.zip', '')

    # Generate report
    validation_report = report.generate_report(model_id)
    logger.info(f"Validation complete: {json.dumps(validation_report)}")

    # Write to DynamoDB
    try:
        _write_to_model_registry(model_id, bucket_name, object_key, validation_report)
        _update_upload_status(model_id, status, validation_report)
        logger.info(f"Successfully wrote validation results to DynamoDB")
    except Exception as e:
        logger.error(f"Failed to write to DynamoDB: {str(e)}", exc_info=True)
        # Continue anyway - validation completed

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Validation complete',
            'model_id': model_id,
            'status': status,
            'report': validation_report
        })
    }


def _write_to_model_registry(model_id: str, bucket: str, key: str,
                             validation_report: Dict[str, Any]):
    """Write validation results to Model Registry table"""
    table = dynamodb.Table(MODEL_REGISTRY_TABLE)

    item = {
        'model_id': model_id,
        's3_bucket': bucket,
        's3_key': key,
        'validation_status': validation_report['status'],
        'validation_timestamp': validation_report['timestamp'],
        'validation_report': json.dumps(validation_report),
        'checks_passed': validation_report.get('checks_passed', []),
        'execution_time_ms': validation_report['execution_time_ms']
    }

    # Add errors if present
    if 'errors' in validation_report:
        item['validation_errors'] = json.dumps(validation_report['errors'])

    table.put_item(Item=item)
    logger.info(f"Wrote to {MODEL_REGISTRY_TABLE}: {model_id}")


def _update_upload_status(model_id: str, status: str, validation_report: Dict[str, Any]):
    """Update upload status table with validation results"""
    table = dynamodb.Table(UPLOAD_STATUS_TABLE)

    table.update_item(
        Key={'model_id': model_id},
        UpdateExpression='SET validation_status = :status, validation_timestamp = :timestamp, validation_complete = :complete',
        ExpressionAttributeValues={
            ':status': status,
            ':timestamp': validation_report['timestamp'],
            ':complete': True
        }
    )
    logger.info(f"Updated {UPLOAD_STATUS_TABLE}: {model_id}")
