# AlphaBack Verify Service

**Model verification microservice for the AlphaBack trading platform**

This service validates user-submitted trading models for security, correctness, and compliance before they are executed in the simulation environment.

## 🎯 Purpose

The Verify Service ensures that all trading models:
- ✅ Have valid structure (required files and class/method signatures)
- ✅ Contain safe code (no malicious imports or operations)
- ✅ Include proper metadata (model ID, version, inputs/outputs)
- ✅ Meet performance requirements (< 5 second verification, < 10MB size)

## 🏗️ Architecture

```
S3 Upload → Lambda Trigger → Verification → DynamoDB Result
```

- **Trigger:** S3 ObjectCreated event (`.tar.gz` files in `models/` prefix)
- **Runtime:** AWS Lambda (Python 3.10)
- **Storage:** S3 for models, DynamoDB for results
- **Processing:** Serverless, auto-scaling

## 📋 Service Contract

### Input

**Model Package Format:**
```
user-model.tar.gz
├── model.py          # Python class with TradingModel.predict()
├── metadata.json     # Model configuration and specifications
└── requirements.txt  # (Optional) Dependencies
```

**S3 Event Trigger:**
```json
{
  "Records": [{
    "s3": {
      "bucket": {"name": "alphaback-model-uploads"},
      "object": {
        "key": "models/user123/model_abc.tar.gz",
        "size": 8388608
      }
    }
  }]
}
```

### Output

**Validation Report (VALID):**
```json
{
  "model_id": "trend_follower_v1",
  "status": "VALID",
  "timestamp": "2025-11-19T10:35:12Z",
  "checks_passed": [
    "structure_validation",
    "metadata_validation",
    "class_structure_validation",
    "code_safety_scan"
  ],
  "execution_time_ms": 1247
}
```

**Validation Report (INVALID):**
```json
{
  "model_id": "malicious_model",
  "status": "INVALID",
  "timestamp": "2025-11-19T10:36:45Z",
  "checks_passed": ["structure_validation"],
  "errors": [
    {
      "code": "DISALLOWED_IMPORT",
      "message": "Disallowed import 'os' found at line 12",
      "severity": "CRITICAL"
    }
  ],
  "execution_time_ms": 892
}
```

## 🔧 Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Runtime | Python 3.10 | Lambda execution environment |
| Hosting | AWS Lambda | Serverless compute |
| Trigger | S3 Events | Automatic invocation |
| Code Analysis | Python `ast` module | Security scanning |
| Storage | S3 + DynamoDB | Model files + validation results |
| Deployment | AWS SAM | Infrastructure as Code |

## 🚀 Quick Start

### Prerequisites

- AWS CLI configured with credentials
- AWS SAM CLI installed
- Python 3.10+
- Git

### Local Testing

```bash
# Clone repository
git clone https://github.com/your-org/alpha-back-verify-service.git
cd alpha-back-verify-service

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/

# Test with sample models
python -m src.lambda_function tests/fixtures/valid_model.tar.gz
```

### Deploy to AWS

```bash
# Build the Lambda package
sam build

# Deploy to AWS (first time)
sam deploy --guided

# Deploy updates
sam deploy
```

**During guided deployment, provide:**
- Stack name: `alphaback-verify-dev`
- AWS Region: `us-east-1` (or your preferred region)
- ModelUploadBucketName: `alphaback-model-uploads-dev`
- Environment: `dev`

## 📦 Project Structure

```
alpha-back-verify-service/
├── src/
│   ├── lambda_function.py          # Main Lambda handler
│   ├── verifier/
│   │   ├── code_scanner.py         # AST security analysis
│   │   ├── structure_checker.py    # File structure validation
│   │   ├── metadata_validator.py   # Metadata checking
│   │   └── report_generator.py     # Result formatting
│   └── config/
│       ├── allowed_imports.json    # Import whitelist
│       └── validation_rules.json   # Validation configuration
├── tests/
│   └── fixtures/
│       ├── valid_model.tar.gz      # Sample valid model
│       └── invalid_model.tar.gz    # Sample invalid model
├── template.yaml                   # AWS SAM template
└── README.md
```

## 🔒 Security Checks

### Blocked Imports
```python
# ❌ These imports will cause validation failure
import os
import subprocess
import socket
import requests
import sys
```

### Blocked Operations
```python
# ❌ These operations are forbidden
eval("code")
exec("code")
open("/etc/passwd")
__import__("os")
```

### Allowed Imports
```python
# ✅ These imports are permitted
import numpy as np
import pandas as pd
import datetime
import math
from typing import Dict
```

## 📊 Validation Checks

| Check | Requirement | Error Code |
|-------|-------------|------------|
| **File Size** | < 10 MB | `FILE_TOO_LARGE` |
| **Structure** | Must include `model.py` and `metadata.json` | `MISSING_REQUIRED_FILES` |
| **Class** | Must have `TradingModel` class | `MISSING_REQUIRED_CLASS` |
| **Method** | Must have `predict(self, stock_prices, volume, timestamps)` | `MISSING_REQUIRED_METHOD` |
| **Metadata** | Must have required fields | `MISSING_METADATA_FIELDS` |
| **Imports** | Only whitelisted modules | `DISALLOWED_IMPORT` |
| **Builtins** | No `eval`, `exec`, `open` | `DISALLOWED_BUILTIN` |
| **File Ops** | No file system access | `DISALLOWED_FILE_OPERATION` |
| **Network** | No network operations | `DISALLOWED_NETWORK_OPERATION` |

## 🔗 Integration with Other Services

### Model Upload Service
- Uploads model to S3
- Writes entry to `UploadStatus` table with `validation_status: "PENDING"`
- S3 upload triggers Verify Service

### Verify Service (You)
- Triggered by S3 event
- Validates model
- Writes result to `ModelRegistry` table
- Updates `UploadStatus` table with `validation_status: "VALID" | "INVALID"`

### Simulator Service
- Reads from `ModelRegistry` table
- Only executes models with `validation_status: "VALID"`
- Rejects models marked as `"INVALID"`

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Test specific module
pytest tests/test_code_scanner.py

# Test with sample models
pytest tests/test_integration.py
```

## 📈 Monitoring

### CloudWatch Metrics
- **Invocations:** Number of verification requests
- **Errors:** Failed validations or Lambda errors
- **Duration:** Time to validate each model
- **Throttles:** Rate limiting events

### CloudWatch Alarms
- **Error Rate:** Alerts if > 5 errors in 5 minutes
- **Duration:** Alerts if average duration > 25 seconds

### Logs
All verification attempts are logged to CloudWatch:
```
[INFO] Processing model: s3://alphaback-model-uploads/models/user123/model.tar.gz
[INFO] Checking file size...
[INFO] Extracting model archive...
[INFO] Validating model structure...
[INFO] Validating metadata...
[INFO] Scanning code for security violations...
[INFO] Model trend_follower_v1 passed all validation checks
```

## 🔄 CI/CD Pipeline

GitHub Actions workflow automatically:
1. Runs tests on pull requests
2. Deploys to AWS on merge to `main`
3. Validates code quality and coverage

```bash
# Workflow file: .github/workflows/deploy.yml
git push origin main  # Triggers automatic deployment
```

## 📝 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MODEL_REGISTRY_TABLE` | DynamoDB table for validated models | `ModelRegistry` |
| `UPLOAD_STATUS_TABLE` | DynamoDB table for upload tracking | `UploadStatus` |
| `ENVIRONMENT` | Deployment environment | `dev` |

### Validation Rules (`src/config/validation_rules.json`)

```json
{
  "max_file_size_bytes": 10485760,
  "max_lines_of_code": 5000,
  "required_files": ["model.py", "metadata.json"],
  "required_class_name": "TradingModel",
  "required_method_name": "predict",
  "timeout_seconds": 5
}
```

## 🐛 Troubleshooting

### Common Issues

**Issue:** Lambda timeout after 30 seconds
- **Solution:** Reduce model size or increase Lambda timeout in `template.yaml`

**Issue:** Import errors in Lambda
- **Solution:** Ensure all dependencies are in `requirements.txt` and deployed with Lambda

**Issue:** S3 event not triggering Lambda
- **Solution:** Check S3 event configuration, ensure `.tar.gz` files are in `models/` prefix

**Issue:** DynamoDB write failures
- **Solution:** Verify Lambda has correct IAM permissions for DynamoDB

## 🤝 Contributing

This service is maintained by [Your Name] as part of the AlphaBack platform.

## 📄 License

Internal use only - AlphaBack Trading Platform

## 📞 Support

For issues or questions:
- Create an issue in this repository
- Contact the AlphaBack team
- Check CloudWatch logs for error details

---

**Service ID:** S04
**Owner:** [Your Name]
**Last Updated:** 2025-11-19
