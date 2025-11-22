"""
AlphaBack Verify Service - Lambda Handler for Java Models
Main entry point for Java model verification Lambda function

Triggered by S3 upload events, validates Java models, and writes results to DynamoDB
"""

import json
import os
import boto3
from typing import Dict, Any
import logging

# Import verification modules
from verifier.java_bytecode_scanner import JavaBytecodeScanner
from verifier.jar_structure_checker import JarStructureChecker
from verifier.java_metadata_validator import JavaMetadataValidator
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
        security_config = json.load(f)

    with open(os.path.join(config_dir, 'validation_rules.json'), 'r') as f:
        validation_config = json.load(f)

    return security_config, validation_config


# Initialize configuration at cold start
security_config, validation_config = load_config()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler - triggered by S3 upload events for Java models

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

        logger.info(f"Processing Java model: s3://{bucket_name}/{object_key} ({file_size} bytes)")

        # Initialize report generator
        report = ReportGenerator()
        report.start_timing()

        # Step 1: Check file size
        logger.info("Checking file size...")
        jar_checker = JarStructureChecker(
            required_files=validation_config['required_files'],
            max_size_bytes=validation_config['max_file_size_bytes']
        )

        if not jar_checker.check_file_size(file_size, report):
            return _complete_validation(report, None, bucket_name, object_key, "INVALID")

        # Step 2: Download JAR file from S3
        logger.info("Downloading JAR from S3...")
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        jar_file_content = response['Body'].read()

        # Step 3: Extract JAR archive
        logger.info("Extracting JAR archive...")
        filename = object_key.split('/')[-1]
        extracted_files = jar_checker.extract_jar(jar_file_content, filename)

        if extracted_files is None:
            report.add_error(
                "INVALID_JAR",
                f"Unable to extract JAR. Ensure file is a valid .jar file",
                "CRITICAL"
            )
            return _complete_validation(report, None, bucket_name, object_key, "INVALID")

        # Log JAR contents
        jar_contents = jar_checker.list_jar_contents(extracted_files)
        logger.info(f"JAR contents: {jar_contents['class_files']} class files, "
                   f"{jar_contents['json_files']} JSON files")

        # Step 4: Validate JAR structure
        logger.info("Validating JAR structure...")
        if not jar_checker.validate_structure(extracted_files, report):
            return _complete_validation(report, None, bucket_name, object_key, "INVALID")

        # Step 5: Extract and validate metadata
        logger.info("Validating metadata...")
        metadata_validator = JavaMetadataValidator(
            required_fields=validation_config['required_metadata_fields']
        )

        metadata_bytes = jar_checker.get_metadata_file(extracted_files)
        if not metadata_bytes:
            report.add_error(
                "MISSING_METADATA",
                "metadata.json not found in JAR",
                "CRITICAL"
            )
            return _complete_validation(report, None, bucket_name, object_key, "INVALID")

        metadata_content = metadata_bytes.decode('utf-8')
        if not metadata_validator.validate(metadata_content, report):
            return _complete_validation(report, None, bucket_name, object_key, "INVALID")

        # Extract model_id and model_class
        model_id = metadata_validator.extract_model_id(metadata_content)
        model_class = metadata_validator.extract_model_class(metadata_content)

        if not model_id:
            model_id = object_key.replace('/', '_').replace('.jar', '')

        if not model_class:
            report.add_error(
                "MISSING_MODEL_CLASS",
                "metadata.json must specify 'model_class' field",
                "CRITICAL"
            )
            return _complete_validation(report, model_id, bucket_name, object_key, "INVALID")

        logger.info(f"Model class: {model_class}")

        # Step 6: Find the model class file
        logger.info(f"Finding model class: {model_class}...")
        model_class_bytes = jar_checker.find_model_class(extracted_files, model_class)

        if not model_class_bytes:
            report.add_error(
                "MODEL_CLASS_NOT_FOUND",
                f"Class '{model_class}' not found in JAR",
                "CRITICAL"
            )
            return _complete_validation(report, model_id, bucket_name, object_key, "INVALID")

        # Step 7: Initialize bytecode scanner
        logger.info("Initializing bytecode scanner...")
        bytecode_scanner = JavaBytecodeScanner(
            allowed_packages=security_config['allowed_packages'],
            blocked_packages=security_config['blocked_packages'],
            blocked_classes=security_config['blocked_classes'],
            blocked_methods=security_config['blocked_methods']
        )

        # Step 8: Check interface implementation
        logger.info("Checking if class implements Model interface...")
        required_interface = validation_config['required_interface']

        if not bytecode_scanner.check_implements_interface(
            model_class_bytes, required_interface, report
        ):
            return _complete_validation(report, model_id, bucket_name, object_key, "INVALID")

        # Step 9: Check required method
        logger.info("Checking for required simulateStep method...")
        required_method = validation_config['required_method_name']
        required_signature = validation_config['required_method_signature']

        if not bytecode_scanner.check_has_method(
            model_class_bytes, required_method, required_signature, report
        ):
            return _complete_validation(report, model_id, bucket_name, object_key, "INVALID")

        # Step 10: Scan bytecode for security violations
        logger.info("Scanning bytecode for security violations...")
        if not bytecode_scanner.scan_class_file(model_class_bytes, report, model_class):
            return _complete_validation(report, model_id, bucket_name, object_key, "INVALID")

        # Step 11: Scan all other class files in JAR (in case model uses helper classes)
        logger.info("Scanning helper classes...")
        class_files = jar_checker.find_all_class_files(extracted_files)

        for class_path, class_bytes in class_files.items():
            # Skip the main model class (already scanned)
            if model_class in class_path:
                continue

            # Skip interface/record classes (State, Order, Model)
            if any(skip in class_path for skip in ['State.class', 'Order.class', 'Model.class']):
                continue

            logger.info(f"Scanning helper class: {class_path}")
            if not bytecode_scanner.scan_class_file(class_bytes, report, class_path):
                # Helper class has violations
                logger.warning(f"Helper class {class_path} has security violations")

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
        model_id = object_key.replace('/', '_').replace('.jar', '')

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
