# Quick Start Guide

Get the Verify Service running in **under 10 minutes**.

## Step 1: Prerequisites (2 min)

```bash
# Install AWS SAM CLI (if not installed)
brew install aws-sam-cli  # macOS
# Or download from: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html

# Verify installation
sam --version
aws --version
python3 --version
```

## Step 2: Clone & Setup (1 min)

```bash
git clone https://github.com/your-org/alpha-back-verify-service.git
cd alpha-back-verify-service
pip install -r requirements.txt
```

## Step 3: Deploy to AWS (5 min)

```bash
# Build
sam build

# Deploy (follow prompts)
sam deploy --guided
```

**Prompts - Use These Values:**
- Stack name: `alphaback-verify-dev`
- Region: `us-east-1`
- ModelUploadBucketName: `alphaback-model-uploads-dev` (must be globally unique!)
- Environment: `dev`
- Confirm everything else as default (press Enter)

## Step 4: Test It (2 min)

```bash
# Upload test model to S3
aws s3 cp tests/fixtures/valid_model.tar.gz \
  s3://alphaback-model-uploads-dev/models/test/valid_model.tar.gz

# Watch the logs
sam logs -n VerifyFunction --stack-name alphaback-verify-dev --tail
```

**Expected Output:**
```
INFO Processing model: s3://alphaback-model-uploads-dev/models/test/valid_model.tar.gz
INFO Checking file size...
INFO Extracting model archive...
INFO Validating model structure...
INFO Validating metadata...
INFO Scanning code for security violations...
INFO Model moving_average_crossover_v1 passed all validation checks
```

## Done! ✅

Your verification service is now live and processing models automatically.

## What Happens Now?

1. **Upload a model** → S3 bucket `alphaback-model-uploads-dev/models/`
2. **Lambda triggered** → Automatically validates the model
3. **Results stored** → DynamoDB tables `ModelRegistry` and `UploadStatus`
4. **Other services** → Can query the validation status

## Next Steps

- Read [API.md](docs/API.md) for integration details
- Read [DEPLOYMENT.md](docs/DEPLOYMENT.md) for production deployment
- Run `make test` to test locally
- Check CloudWatch for monitoring

## Common Commands

```bash
# Run tests locally
make test

# View logs
make logs-dev

# Redeploy after changes
make deploy-dev

# Clean up
sam delete --stack-name alphaback-verify-dev
```

## Troubleshooting

**Error: Bucket already exists**
→ Change `ModelUploadBucketName` to something unique (S3 buckets are global)

**Error: Access denied**
→ Run `aws configure` and set your credentials

**Lambda not triggering**
→ Ensure files are uploaded to `models/` prefix with `.tar.gz` extension

## Help

- Check [README.md](README.md) for full documentation
- View logs: `sam logs -n VerifyFunction --stack-name alphaback-verify-dev --tail`
- GitHub Issues: [Create an issue](https://github.com/your-org/alpha-back-verify-service/issues)
