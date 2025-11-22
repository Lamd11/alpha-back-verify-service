# Testing the Verify Service Locally

This guide explains how to test the verification service on your local machine without deploying to AWS.

## Prerequisites

1. **Python 3.9+** installed
2. **Java JDK 11+** installed (for compiling .class files)
3. Python dependencies installed:
   ```bash
   pip install -r requirements.txt
   ```

## Quick Start

### Step 1: Set up the AlphaBack interfaces

You need Justin's AlphaBack model interfaces to compile test models. Clone or copy from:
https://github.com/JustinTsangg/alphaback-model

Or use the stub files in `tests/fixtures/alphaback_stubs/`:

```bash
# The directory structure should be:
tests/fixtures/alphaback_stubs/
└── com/
    └── ttsudio/
        └── alphaback/
            ├── Model.java
            ├── State.java
            └── Order.java
```

### Step 2: Compile a test model

```bash
# Navigate to the java_models directory
cd tests/fixtures/java_models/valid_model

# Compile with the stubs in classpath
javac -cp ../../alphaback_stubs TrendFollowerModel.java

# This creates: TrendFollowerModel.class
```

### Step 3: Run verification

```bash
# From project root
python tests/test_local.py tests/fixtures/java_models/valid_model/TrendFollowerModel.class
```

## Expected Output

### Valid Model (passes all checks)
```
Verifying: tests/fixtures/java_models/valid_model/TrendFollowerModel.class
  Class: com/example/TrendFollowerModel
  Interfaces: ['com/ttsudio/alphaback/Model']
  Methods: ['<init>', 'simulateStep']

============================================================
MODEL: TrendFollowerModel
VERIFIED: ✓ YES
============================================================

Checks:
  ✓ fileSize
  ✓ s3FileReadable
  ✓ classFileValid
  ✓ implementsInterface
  ✓ hasSimulateStep
  ✓ securityScan

Execution time: 127ms
```

### Invalid Model (fails security scan)
```
Verifying: tests/fixtures/java_models/invalid_model/MaliciousModel.class

============================================================
MODEL: MaliciousModel
VERIFIED: ✗ NO
============================================================

Checks:
  ✓ fileSize
  ✓ s3FileReadable
  ✓ classFileValid
  ✓ implementsInterface
  ✓ hasSimulateStep
  ✗ securityScan
      Error: Blocked package: java/io/File; Blocked package: java/net/URL...

Errors:
  - securityScan: Blocked package: java/io/File; ...
```

## Sample Reports

See `tests/fixtures/sample_reports/` for example JSON output:

- `valid_model_report.json` - All checks pass
- `invalid_model_report.json` - Fails security scan (blocked imports)
- `missing_interface_report.json` - Doesn't implement Model interface
- `wrong_signature_report.json` - simulateStep has wrong signature

## Running Unit Tests

```bash
# Run all pytest tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/verifier
```

## Troubleshooting

### "jawa" import error
```bash
pip install jawa
```

### Java compilation errors
Make sure you have JDK installed:
```bash
java -version   # Should show 11+
javac -version  # Should show 11+
```

### "Model interface not found" during compilation
Make sure the alphaback stubs are in your classpath:
```bash
javac -cp path/to/alphaback_stubs YourModel.java
```
