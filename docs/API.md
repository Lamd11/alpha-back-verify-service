# Verify Service API Documentation

## Overview

The Verify Service is triggered by S3 events and validates trading models for security and correctness.

## Service Interface

### Input Contract

**Trigger:** S3 ObjectCreated event

**Event Structure:**
```json
{
  "Records": [
    {
      "eventVersion": "2.1",
      "eventSource": "aws:s3",
      "eventName": "ObjectCreated:Put",
      "s3": {
        "bucket": {
          "name": "alphaback-model-uploads"
        },
        "object": {
          "key": "models/user123/model_abc123.tar.gz",
          "size": 8388608
        }
      }
    }
  ]
}
```

**Model Package Requirements:**

The uploaded `.tar.gz` file must contain:

1. **model.py** - Python file with TradingModel class
2. **metadata.json** - Model metadata and configuration
3. **requirements.txt** (optional) - Python dependencies

### model.py Structure

```python
class TradingModel:
    """Required class name"""

    def predict(self, stock_prices, volume, timestamps):
        """
        Required method signature

        Args:
            stock_prices: List/array of float - Historical prices
            volume: List/array of int - Trading volumes
            timestamps: List/array of str - ISO 8601 timestamps

        Returns:
            dict: Must contain 'signal' and 'confidence'
                {
                    "signal": "BUY" | "SELL" | "HOLD",
                    "confidence": float (0.0 to 1.0)
                }
        """
        pass
```

### metadata.json Structure

```json
{
  "model_id": "string (required) - Unique identifier",
  "version": "string (required) - Semantic version (e.g., '1.0.0')",
  "author": "string (required) - User ID or name",
  "description": "string (optional) - Model description",
  "created_at": "string (optional) - ISO 8601 timestamp",
  "expected_inputs": {
    "stock_prices": "string - Description of expected format",
    "volume": "string - Description of expected format",
    "timestamps": "string - Description of expected format"
  },
  "output_format": {
    "signal": "string - Description of signal values",
    "confidence": "string - Description of confidence score"
  }
}
```

## Output Contract

### Success Response (VALID Model)

**Status Code:** 200

**Response Body:**
```json
{
  "message": "Validation complete",
  "model_id": "trend_follower_v1",
  "status": "VALID",
  "report": {
    "model_id": "trend_follower_v1",
    "status": "VALID",
    "timestamp": "2025-11-19T10:35:12Z",
    "checks_passed": [
      "file_size_validation",
      "structure_validation",
      "metadata_validation",
      "class_structure_validation",
      "code_safety_scan"
    ],
    "execution_time_ms": 1247
  }
}
```

### Failure Response (INVALID Model)

**Status Code:** 200 (Lambda succeeded, model failed validation)

**Response Body:**
```json
{
  "message": "Validation complete",
  "model_id": "malicious_model_v1",
  "status": "INVALID",
  "report": {
    "model_id": "malicious_model_v1",
    "status": "INVALID",
    "timestamp": "2025-11-19T10:36:45Z",
    "checks_passed": [
      "file_size_validation",
      "structure_validation",
      "metadata_validation"
    ],
    "errors": [
      {
        "code": "DISALLOWED_IMPORT",
        "message": "Disallowed import 'os' found at line 12",
        "severity": "CRITICAL"
      },
      {
        "code": "DISALLOWED_IMPORT",
        "message": "Disallowed import 'subprocess' found at line 15",
        "severity": "CRITICAL"
      },
      {
        "code": "DISALLOWED_BUILTIN",
        "message": "Disallowed builtin function 'eval' called at line 28",
        "severity": "CRITICAL"
      }
    ],
    "execution_time_ms": 892
  }
}
```

### Error Response (System Failure)

**Status Code:** 500

**Response Body:**
```json
{
  "error": "Validation failed: S3 object not found"
}
```

## DynamoDB Output

### ModelRegistry Table

**Item Structure:**
```json
{
  "model_id": "trend_follower_v1",
  "validation_timestamp": "2025-11-19T10:35:12Z",
  "s3_bucket": "alphaback-model-uploads",
  "s3_key": "models/user123/model_abc123.tar.gz",
  "validation_status": "VALID",
  "validation_report": "{...json...}",
  "checks_passed": ["structure_validation", "..."],
  "execution_time_ms": 1247
}
```

### UploadStatus Table

**Updated Fields:**
```json
{
  "model_id": "trend_follower_v1",
  "validation_status": "VALID",
  "validation_timestamp": "2025-11-19T10:35:12Z",
  "validation_complete": true
}
```

## Validation Checks

### Check 1: File Size Validation
- **Requirement:** Model package < 10 MB
- **Error Code:** `FILE_TOO_LARGE`
- **Severity:** CRITICAL

### Check 2: Structure Validation
- **Requirement:** Package contains `model.py` and `metadata.json`
- **Error Code:** `MISSING_REQUIRED_FILES`
- **Severity:** CRITICAL

### Check 3: Metadata Validation
- **Requirement:** All required fields present and valid
- **Error Codes:**
  - `INVALID_JSON` - Malformed JSON
  - `MISSING_METADATA_FIELDS` - Required fields missing
  - `INVALID_MODEL_ID` - Invalid model ID format
  - `INVALID_VERSION` - Invalid version string
  - `MISSING_INPUT_FIELDS` - Missing expected_inputs fields
  - `MISSING_OUTPUT_FIELDS` - Missing output_format fields
- **Severity:** CRITICAL

### Check 4: Class Structure Validation
- **Requirement:** `TradingModel` class with `predict()` method
- **Error Codes:**
  - `SYNTAX_ERROR` - Python syntax error
  - `MISSING_REQUIRED_CLASS` - TradingModel class not found
  - `MISSING_REQUIRED_METHOD` - predict() method not found
  - `INVALID_METHOD_SIGNATURE` - Wrong method signature
- **Severity:** CRITICAL

### Check 5: Code Safety Scan
- **Requirement:** No disallowed imports or dangerous operations
- **Error Codes:**
  - `DISALLOWED_IMPORT` - Blocked import used
  - `IMPORT_NOT_WHITELISTED` - Import not in allowed list
  - `DISALLOWED_BUILTIN` - Dangerous builtin used
  - `DISALLOWED_FILE_OPERATION` - File system access
  - `DISALLOWED_NETWORK_OPERATION` - Network operation
  - `DANGEROUS_PATTERN` - Other dangerous code pattern
- **Severity:** CRITICAL

## Allowed Imports

```python
# Data manipulation
import numpy
import pandas

# Standard library
import datetime
import typing
import collections
import math
import statistics
import dataclasses
import enum
import decimal
import fractions
import random
import json
import re
import itertools
import functools
import operator
```

## Blocked Imports

```python
# File system
import os
import sys

# Process execution
import subprocess

# Network
import socket
import urllib
import requests
import http

# Dynamic code execution
import importlib
import pickle
import marshal

# Threading/multiprocessing
import threading
import multiprocessing
```

## Performance Requirements

| Metric | Target | Alarm Threshold |
|--------|--------|-----------------|
| Validation Time | < 5 seconds | > 25 seconds |
| Accuracy | > 95% | N/A |
| Throughput | 10 concurrent | > 5 errors/5min |
| File Size Limit | 10 MB | N/A |

## Integration Points

### Upstream: Model Upload Service
- Uploads model to S3
- Writes to UploadStatus table
- S3 upload triggers Verify Service

### Downstream: Model Registry Service
- Reads validation results from ModelRegistry table
- Only processes models with `validation_status: "VALID"`

### Downstream: Simulator Service
- Queries ModelRegistry for validated models
- Retrieves model from S3
- Executes simulation

## Example Usage

### Valid Model Upload Flow

```
1. User submits model via Upload Service
2. Upload Service uploads to S3: models/user123/trend_v1.tar.gz
3. S3 event triggers Verify Lambda
4. Verify Lambda:
   - Downloads model from S3
   - Validates structure (✓)
   - Validates metadata (✓)
   - Scans code (✓)
5. Verify Lambda writes to DynamoDB:
   - ModelRegistry: {status: "VALID", ...}
   - UploadStatus: {validation_status: "VALID"}
6. Simulator can now execute this model
```

### Invalid Model Upload Flow

```
1. User submits malicious model
2. Upload Service uploads to S3: models/user456/hack_v1.tar.gz
3. S3 event triggers Verify Lambda
4. Verify Lambda:
   - Downloads model from S3
   - Validates structure (✓)
   - Validates metadata (✓)
   - Scans code (✗) - Found: import os
5. Verify Lambda writes to DynamoDB:
   - ModelRegistry: {status: "INVALID", errors: [...]}
   - UploadStatus: {validation_status: "INVALID"}
6. Simulator rejects this model
```

## Error Handling

| Scenario | Behavior | User Impact |
|----------|----------|-------------|
| S3 object not found | Log error, return 500 | Upload failed, retry needed |
| Invalid archive format | Return INVALID with error | Fix package format |
| DynamoDB write failure | Log error, continue | Validation succeeds but result may not persist |
| Lambda timeout | Partial validation, retry | Large models may fail, reduce size |
| Syntax error in model.py | Return INVALID with error | Fix Python syntax |
| Disallowed import | Return INVALID with error | Remove unsafe imports |

## Monitoring & Observability

### CloudWatch Metrics
- `Invocations` - Total validation requests
- `Errors` - Lambda execution errors
- `Duration` - Validation time
- `Throttles` - Rate limit events

### CloudWatch Logs
All validation events logged with:
- Model ID
- Validation result
- Execution time
- Error details (if any)

### Custom Metrics
- Validation success rate
- Average validation time
- Error type distribution

## Rate Limits

- **Concurrent Executions:** 10 (configurable)
- **S3 Event Rate:** Unlimited (handled by Lambda scaling)
- **DynamoDB Writes:** 40 WCU (on-demand, auto-scales)

## Versioning

**API Version:** 1.0
**Last Updated:** 2025-11-19
**Breaking Changes:** None
