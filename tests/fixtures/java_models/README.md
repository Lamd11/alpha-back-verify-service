# Java Model Test Fixtures

This directory contains sample Java models for testing the verification service.

## Prerequisites

1. **Java JDK 17+** installed
2. **alphaback-model library** (Justin's repo) compiled and available

## Directory Structure

```
java_models/
├── valid_model/
│   ├── TrendFollowerModel.java   # Valid model (passes all checks)
│   └── metadata.json
└── invalid_model/
    ├── MaliciousModel.java        # Invalid model (security violations)
    └── metadata.json
```

## How to Compile Models

### Step 1: Get the alphaback-model library

Clone Justin's repository:
```bash
git clone https://github.com/JustinTsangg/alphaback-model.git
cd alphaback-model/lib
./gradlew build
```

This creates `alphaback-model.jar` in `lib/build/libs/`

### Step 2: Compile the Valid Model

```bash
cd tests/fixtures/java_models/valid_model

# Compile the Java source
javac -cp /path/to/alphaback-model.jar TrendFollowerModel.java

# Create JAR with metadata
jar cf trend_follower_v1.jar \
    com/example/TrendFollowerModel.class \
    metadata.json

# Verify JAR contents
jar tf trend_follower_v1.jar
```

Expected output:
```
META-INF/
META-INF/MANIFEST.MF
com/example/TrendFollowerModel.class
metadata.json
```

### Step 3: Compile the Invalid Model

```bash
cd tests/fixtures/java_models/invalid_model

# Compile (will succeed - compilation doesn't check security)
javac -cp /path/to/alphaback-model.jar MaliciousModel.java

# Create JAR
jar cf malicious_model_v1.jar \
    com/example/MaliciousModel.class \
    metadata.json
```

## Quick Build Script

Create `build_models.sh`:

```bash
#!/bin/bash

# Set path to alphaback-model.jar
ALPHABACK_JAR="/path/to/alphaback-model/lib/build/libs/alphaback-model.jar"

# Build valid model
echo "Building valid model..."
cd valid_model
javac -cp $ALPHABACK_JAR TrendFollowerModel.java
jar cf trend_follower_v1.jar com/example/*.class metadata.json
echo "✅ Created trend_follower_v1.jar"

# Build invalid model
echo "Building invalid model..."
cd ../invalid_model
javac -cp $ALPHABACK_JAR MaliciousModel.java
jar cf malicious_model_v1.jar com/example/*.class metadata.json
echo "✅ Created malicious_model_v1.jar"

echo "Done!"
```

Make executable:
```bash
chmod +x build_models.sh
./build_models.sh
```

## Testing with the Verify Service

### Upload to S3

```bash
# Upload valid model
aws s3 cp valid_model/trend_follower_v1.jar \
  s3://alphaback-model-uploads-dev/models/test/trend_follower_v1.jar

# Upload invalid model
aws s3 cp invalid_model/malicious_model_v1.jar \
  s3://alphaback-model-uploads-dev/models/test/malicious_model_v1.jar
```

### Check CloudWatch Logs

```bash
sam logs -n VerifyFunction --stack-name alphaback-verify-dev --tail
```

### Expected Results

**Valid Model (trend_follower_v1.jar):**
```json
{
  "model_id": "trend_follower_v1",
  "status": "VALID",
  "checks_passed": [
    "file_size_validation",
    "jar_structure_validation",
    "metadata_validation",
    "interface_implementation",
    "method_signature_validation",
    "bytecode_safety_scan"
  ]
}
```

**Invalid Model (malicious_model_v1.jar):**
```json
{
  "model_id": "malicious_model_v1",
  "status": "INVALID",
  "errors": [
    {
      "code": "DISALLOWED_PACKAGE_REFERENCE",
      "message": "Reference to blocked package class 'java/io/File' found",
      "severity": "CRITICAL"
    },
    {
      "code": "DISALLOWED_PACKAGE_REFERENCE",
      "message": "Reference to blocked package class 'java/net/URL' found",
      "severity": "CRITICAL"
    }
  ]
}
```

## Model Requirements

All models MUST:

1. ✅ Implement `com.ttsudio.alphaback.Model` interface
2. ✅ Have `simulateStep(State state)` method returning `List<Order>`
3. ✅ Include `metadata.json` with required fields:
   - `model_id`
   - `version`
   - `author`
   - `model_class` (fully qualified class name)
4. ✅ Be packaged as a `.jar` file
5. ✅ Not use blocked packages (java.io, java.net, java.lang.reflect, etc.)
6. ✅ Not call dangerous methods (Runtime.exec, System.exit, etc.)

## Troubleshooting

**Error: Class not found**
→ Make sure classpath includes alphaback-model.jar

**Error: Package does not exist**
→ Verify alphaback-model.jar is properly built

**JAR doesn't contain .class files**
→ Check that compilation succeeded before creating JAR

**Verify service rejects valid model**
→ Check CloudWatch logs for specific error
→ Verify metadata.json has all required fields
