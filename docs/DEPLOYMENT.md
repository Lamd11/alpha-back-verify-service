# Deployment Guide

## Prerequisites

Before deploying the Verify Service, ensure you have:

### Required Tools
- ✅ AWS CLI (v2.x or later)
- ✅ AWS SAM CLI (v1.x or later)
- ✅ Python 3.10+
- ✅ Git
- ✅ Make (optional, for convenience commands)

### AWS Account Setup
- ✅ AWS account with admin or deployment permissions
- ✅ AWS credentials configured (`aws configure`)
- ✅ S3 bucket for SAM deployment artifacts (auto-created by SAM)

### Verify Installation

```bash
# Check AWS CLI
aws --version
# Expected: aws-cli/2.x.x

# Check SAM CLI
sam --version
# Expected: SAM CLI, version 1.x.x

# Check Python
python3 --version
# Expected: Python 3.10.x or later

# Verify AWS credentials
aws sts get-caller-identity
# Should show your account ID
```

## Deployment Steps

### Step 1: Clone Repository

```bash
git clone https://github.com/your-org/alpha-back-verify-service.git
cd alpha-back-verify-service
```

### Step 2: Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install development dependencies (optional)
pip install pytest pytest-cov flake8
```

### Step 3: Run Tests (Optional but Recommended)

```bash
# Run all tests
make test

# Or manually
pytest tests/ -v
```

### Step 4: Build Lambda Package

```bash
# Using Makefile
make build

# Or manually
sam build
```

This creates a `.aws-sam/` directory with your Lambda deployment package.

### Step 5: Deploy to AWS

#### First Time Deployment (Guided)

```bash
sam deploy --guided
```

**You'll be prompted for:**

1. **Stack Name:** `alphaback-verify-dev` (or your preferred name)
2. **AWS Region:** `us-east-1` (or your preferred region)
3. **Parameter ModelUploadBucketName:** `alphaback-model-uploads-dev`
4. **Parameter ModelRegistryTableName:** `ModelRegistry`
5. **Parameter UploadStatusTableName:** `UploadStatus`
6. **Parameter Environment:** `dev`
7. **Confirm changes before deploy:** `Y`
8. **Allow SAM CLI IAM role creation:** `Y`
9. **Save arguments to configuration file:** `Y`
10. **SAM configuration file:** `samconfig.toml`
11. **SAM configuration environment:** `default`

#### Subsequent Deployments

```bash
# Using Makefile
make deploy-dev

# Or manually
sam deploy
```

### Step 6: Verify Deployment

```bash
# Check CloudFormation stack status
aws cloudformation describe-stacks \
  --stack-name alphaback-verify-dev \
  --query 'Stacks[0].StackStatus'

# Should output: "CREATE_COMPLETE" or "UPDATE_COMPLETE"

# Get Lambda function ARN
aws cloudformation describe-stacks \
  --stack-name alphaback-verify-dev \
  --query 'Stacks[0].Outputs'
```

### Step 7: Test Deployment

```bash
# Upload a test model to S3
aws s3 cp tests/fixtures/valid_model.tar.gz \
  s3://alphaback-model-uploads-dev/models/test/valid_model.tar.gz

# Check CloudWatch logs
sam logs -n VerifyFunction --stack-name alphaback-verify-dev --tail

# Or manually
aws logs tail /aws/lambda/alphaback-verify-dev --follow
```

## Environment-Specific Deployments

### Development Environment

```bash
sam deploy \
  --stack-name alphaback-verify-dev \
  --parameter-overrides \
    Environment=dev \
    ModelUploadBucketName=alphaback-model-uploads-dev
```

### Staging Environment

```bash
sam deploy \
  --stack-name alphaback-verify-staging \
  --parameter-overrides \
    Environment=staging \
    ModelUploadBucketName=alphaback-model-uploads-staging
```

### Production Environment

```bash
# Requires production credentials
sam deploy \
  --stack-name alphaback-verify-prod \
  --parameter-overrides \
    Environment=prod \
    ModelUploadBucketName=alphaback-model-uploads-prod
```

## CI/CD Deployment (GitHub Actions)

### Setup GitHub Secrets

In your GitHub repository settings, add:

**For Development/Staging:**
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

**For Production:**
- `AWS_ACCESS_KEY_ID_PROD`
- `AWS_SECRET_ACCESS_KEY_PROD`

### Automatic Deployment

Deployments trigger automatically:

```bash
# Deploy to dev
git push origin develop

# Deploy to production
git push origin main
```

## Configuration

### Environment Variables

Set in `template.yaml` under `Environment.Variables`:

```yaml
Environment:
  Variables:
    MODEL_REGISTRY_TABLE: ModelRegistry
    UPLOAD_STATUS_TABLE: UploadStatus
    ENVIRONMENT: dev
```

### Lambda Configuration

Adjust in `template.yaml`:

```yaml
VerifyFunction:
  Type: AWS::Serverless::Function
  Properties:
    Timeout: 30        # Max execution time (seconds)
    MemorySize: 512    # RAM allocation (MB)
```

### S3 Event Filter

Modify trigger configuration in `template.yaml`:

```yaml
Events:
  S3Event:
    Type: S3
    Properties:
      Events: s3:ObjectCreated:*
      Filter:
        S3Key:
          Rules:
            - Name: prefix
              Value: models/      # Only files in models/
            - Name: suffix
              Value: .tar.gz      # Only .tar.gz files
```

## Rollback

If deployment fails or has issues:

```bash
# Rollback to previous version
aws cloudformation rollback-stack \
  --stack-name alphaback-verify-dev

# Or delete and redeploy
sam delete --stack-name alphaback-verify-dev
sam deploy --guided
```

## Updating the Service

### Code Changes

```bash
# 1. Make changes to src/
# 2. Test locally
make test

# 3. Build and deploy
make build
make deploy-dev
```

### Configuration Changes

```bash
# 1. Update template.yaml
# 2. Deploy
sam deploy
```

### Dependency Changes

```bash
# 1. Update requirements.txt
# 2. Rebuild
sam build

# 3. Deploy
sam deploy
```

## Monitoring Deployment

### CloudWatch Logs

```bash
# Tail logs in real-time
sam logs -n VerifyFunction --stack-name alphaback-verify-dev --tail

# View specific time range
aws logs filter-log-events \
  --log-group-name /aws/lambda/alphaback-verify-dev \
  --start-time $(date -d '1 hour ago' +%s)000
```

### CloudWatch Metrics

```bash
# View invocation count
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=alphaback-verify-dev \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

## Troubleshooting

### Deployment Fails

**Issue:** CloudFormation stack creation fails

**Solutions:**
1. Check error in CloudFormation console
2. Verify IAM permissions
3. Check resource limits (Lambda concurrency, S3 bucket names)

```bash
# View stack events
aws cloudformation describe-stack-events \
  --stack-name alphaback-verify-dev \
  --max-items 10
```

### Lambda Not Triggered

**Issue:** S3 uploads don't trigger Lambda

**Solutions:**
1. Verify S3 event configuration
2. Check file path matches filter (prefix: `models/`, suffix: `.tar.gz`)
3. Verify Lambda has S3 permissions

```bash
# Check Lambda policy
aws lambda get-policy --function-name alphaback-verify-dev
```

### DynamoDB Write Errors

**Issue:** Lambda can't write to DynamoDB

**Solutions:**
1. Verify table names match environment variables
2. Check Lambda IAM role has DynamoDB permissions
3. Verify tables exist

```bash
# List tables
aws dynamodb list-tables

# Check table
aws dynamodb describe-table --table-name ModelRegistry
```

## Clean Up

### Delete Stack

```bash
# Delete entire stack
sam delete --stack-name alphaback-verify-dev

# Or manually
aws cloudformation delete-stack --stack-name alphaback-verify-dev
```

**Note:** This deletes:
- Lambda function
- S3 bucket (if empty)
- DynamoDB tables
- CloudWatch log groups
- IAM roles

### Keep Data, Delete Function

```bash
# Just delete the Lambda function
aws lambda delete-function --function-name alphaback-verify-dev
```

## Production Checklist

Before deploying to production:

- [ ] All tests pass
- [ ] Code review completed
- [ ] Tested in dev environment
- [ ] Tested in staging environment
- [ ] Monitoring dashboards configured
- [ ] Alarms set up
- [ ] Backup plan in place
- [ ] Rollback plan documented
- [ ] Team notified of deployment
- [ ] Deployment window scheduled

## Security Considerations

### IAM Permissions

Lambda function needs:
- ✅ S3 read access (GetObject)
- ✅ DynamoDB write access (PutItem, UpdateItem)
- ✅ CloudWatch Logs write access

### Network Security

- Lambda runs in AWS-managed VPC
- No public internet access required
- All communication within AWS

### Data Security

- Models encrypted at rest (S3 SSE)
- Logs encrypted (CloudWatch default encryption)
- Credentials managed via IAM roles (no hardcoded keys)

## Cost Estimation

### Lambda Costs

- **Requests:** $0.20 per 1M requests
- **Duration:** $0.0000166667 per GB-second
- **Example:** 10,000 validations/month, 2 sec avg, 512 MB = ~$0.50/month

### Storage Costs

- **S3:** $0.023 per GB/month
- **DynamoDB:** $0.25 per GB/month (on-demand)
- **CloudWatch Logs:** $0.50 per GB ingested

**Estimated Total:** ~$5-10/month for light usage

## Support

For deployment issues:
1. Check CloudWatch logs first
2. Review this guide
3. Contact DevOps team
4. Create GitHub issue

---

**Last Updated:** 2025-11-19
