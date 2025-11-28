# AWS Authentication Guide for KG Forge

KG Forge provides flexible AWS authentication options to work with any AWS setup. Choose the method that works best for your environment.

## Authentication Methods (in order of recommendation)

### 1. AWS SSO (Recommended for Interactive Use)

**Best for:** Developers using AWS SSO in their organization

```bash
# Configure SSO (one-time setup)
aws configure sso
# Follow prompts to set up your SSO profile

# Login when session expires
aws sso login

# Use in KG Forge (.env file)
AWS_PROFILE=your-sso-profile-name
AWS_DEFAULT_REGION=us-east-1
```

### 2. AWS CLI Profiles (Recommended for Automation)

**Best for:** Multiple AWS accounts or CI/CD pipelines

```bash
# Configure named profile
aws configure --profile production
# Enter your access key, secret key, and region

# Use in KG Forge (.env file)
AWS_PROFILE=production
AWS_DEFAULT_REGION=us-east-1
```

### 3. Environment Variables (Most Flexible)

**Best for:** Docker containers, lambda functions, or when you need full control

```bash
# .env file
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
# Optional for temporary credentials:
# AWS_SESSION_TOKEN=your_session_token
```

### 4. IAM Roles (Best for Production)

**Best for:** EC2 instances, ECS tasks, Lambda functions

```bash
# No credentials needed in .env - just region
AWS_DEFAULT_REGION=us-east-1
# IAM role attached to your compute resource provides credentials automatically
```

## Configuration Examples

### Example 1: AWS SSO Setup

```env
# .env file
AWS_PROFILE=my-sso-profile
AWS_DEFAULT_REGION=us-east-1
BEDROCK_MODEL_NAME=anthropic.claude-3-haiku-20240307-v1:0
```

```bash
# Commands
aws sso login
kg-forge llm-test test_data/document.html
```

### Example 2: Multiple Profiles

```yaml
# kg_forge.yaml
aws:
  profile_name: production  # Use production profile
  default_region: us-west-2
  bedrock_model_name: anthropic.claude-3-haiku-20240307-v1:0
```

### Example 3: Explicit Credentials (Not Recommended for Production)

```env
# .env file
AWS_ACCESS_KEY_ID=AKIAI...
AWS_SECRET_ACCESS_KEY=wJalr...
AWS_DEFAULT_REGION=us-east-1
```

### Example 4: Temporary Credentials (Session Token)

```env
# .env file - for temporary credentials from assume-role or SSO
AWS_ACCESS_KEY_ID=ASIAZ...
AWS_SECRET_ACCESS_KEY=HTqf...
AWS_SESSION_TOKEN=IQoJb3JpZ2lu...
AWS_DEFAULT_REGION=us-east-1
```

## Troubleshooting

### Expired Token Error
```
ERROR: ExpiredTokenException: The security token included in the request is expired
```

**Solution:**
- For SSO: Run `aws sso login`
- For profiles with temporary credentials: Refresh your credentials
- For hardcoded credentials: Update them in your `.env` file

### Invalid Credentials Error
```
ERROR: InvalidClientTokenId: The security token included in the request is invalid
```

**Solution:**
- Check your credentials are correct
- Verify the profile name exists: `aws configure list-profiles`
- Test credentials: `aws sts get-caller-identity`

### Permission Denied Error
```
ERROR: AccessDeniedException: User is not authorized to perform: bedrock:InvokeModel
```

**Solution:**
- Ensure your IAM user/role has Bedrock permissions
- Check the model is available in your region
- Verify you have access to the specific model ID

## Best Practices

1. **Never commit credentials to git** - Use `.env` files (in `.gitignore`)
2. **Use IAM roles in production** - More secure than long-term keys
3. **Use least privilege** - Only grant necessary Bedrock permissions
4. **Rotate credentials regularly** - Especially for long-term access keys
5. **Use AWS SSO when available** - Better security and user experience
6. **Test credentials** - Run `aws sts get-caller-identity` to verify

## Required AWS Permissions

Your AWS user/role needs these permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            "Resource": [
                "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
                "arn:aws:bedrock:*::foundation-model/anthropic.claude-*"
            ]
        }
    ]
}
```

## Configuration Priority

KG Forge uses this priority order (highest to lowest):

1. **Command-line arguments** (if any)
2. **YAML configuration file** (`kg_forge.yaml`)
3. **Environment variables** (`AWS_PROFILE`, `AWS_ACCESS_KEY_ID`, etc.)
4. **`.env` file values**
5. **AWS default credential chain** (profiles, IAM roles, etc.)

This allows maximum flexibility - you can override any setting at any level.