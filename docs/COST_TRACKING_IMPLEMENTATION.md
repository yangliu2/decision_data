# Cost Tracking System Implementation

## Overview

A complete cost tracking system has been implemented to monitor API usage across all services and track user credit balances. The system calculates costs based on actual third-party API usage with transparent pricing.

## Architecture

### DynamoDB Tables

Three tables were created to support cost tracking:

#### 1. panzoto-usage-records
Stores individual usage events for cost calculation.

**Primary Key:** `usage_id` (UUID)

**Global Secondary Index:** `user-month-index`
- Partition Key: `user_id`
- Sort Key: `month` (YYYY-MM format)

**Fields:**
- `usage_id` - Unique identifier for the usage event
- `user_id` - User who incurred the cost
- `service` - Service name (whisper, s3, dynamodb, ses, secrets_manager, openai)
- `operation` - Type of operation (transcribe, upload, read_units, send_email, etc)
- `quantity` - Amount of resource used
- `unit` - Unit of measurement (minutes, GB, units, emails, etc)
- `cost_usd` - Calculated cost in USD
- `timestamp` - When the usage occurred (ISO format)
- `month` - Month of usage for easy querying (YYYY-MM)
- `metadata` - Optional additional details

#### 2. panzoto-user-credits
Tracks credit accounts and balance information for each user.

**Primary Key:** `user_id` (UUID)

**Fields:**
- `user_id` - User identifier
- `credit_balance` - Current available balance in USD
- `initial_credit` - Initial credit amount given to user
- `used_credit` - Total amount of credit used to date
- `refunded_credit` - Total amount of credit refunded
- `last_updated` - ISO timestamp of last balance update

#### 3. panzoto-cost-summaries
Cached cost summaries by month (for reporting efficiency).

**Primary Key:** `user_id` (Partition Key), `month` (Sort Key)

**Fields:**
- `user_id` - User identifier
- `month` - Month of summary (YYYY-MM)
- Cached cost breakdown by service

## Pricing Model

All prices are as of October 2025 and reflect actual third-party costs:

| Service | Metric | Price |
|---------|--------|-------|
| **OpenAI Whisper** | Per minute of audio | $0.006 |
| **AWS S3** | Per GB uploaded | $0.023 |
| **AWS S3** | Per GB stored/month | $0.023 |
| **DynamoDB** | Per 1M read units | $0.25 |
| **DynamoDB** | Per 1M write units | $1.25 |
| **SES Email** | Per 1000 emails | $0.10 |
| **Secrets Manager** | Per secret per month | $0.40 |
| **Secrets Manager** | Per secret retrieval | $0.05 |
| **OpenAI GPT-5** | Per 1K input tokens | $0.003 |
| **OpenAI GPT-5** | Per 1K output tokens | $0.006 |

## Usage API

### Cost Tracking Service

The `CostTrackingService` provides a clean API for recording usage and retrieving cost information:

```python
from decision_data.backend.services.cost_tracking_service import get_cost_tracking_service

cost_service = get_cost_tracking_service()
```

#### Recording Usage

**Record Whisper Transcription:**
```python
cost_service.record_whisper_usage(user_id, duration_minutes=10.0)
# Cost: 10 minutes × $0.006 = $0.06
```

**Record S3 Upload:**
```python
cost_service.record_s3_usage(user_id, operation="upload", size_mb=100.0)
# Cost: 0.098 GB × $0.023 = $0.002
```

**Record DynamoDB Operations:**
```python
cost_service.record_dynamodb_usage(user_id, operation="read_units", units=1000.0)
# Cost: (1000 / 1,000,000) × $0.25 = $0.00025
```

**Record SES Email:**
```python
cost_service.record_ses_usage(user_id, email_count=50)
# Cost: (50 / 1000) × $0.10 = $0.005
```

**Record Secrets Manager Retrieval:**
```python
cost_service.record_secrets_manager_retrieval(user_id)
# Cost: $0.05
```

**Record OpenAI Usage:**
```python
cost_service.record_openai_summarization(
    user_id,
    input_tokens=500,
    output_tokens=300
)
# Cost: (500/1000)*$0.003 + (300/1000)*$0.006 = $0.003
```

#### Querying Costs

**Get Current Month Costs:**
```python
costs = cost_service.get_current_month_usage(user_id)
# Returns: {
#     "whisper": 0.06,
#     "s3": 0.002,
#     "dynamodb": 0.00025,
#     "ses": 0.005,
#     "secrets_manager": 0.05,
#     "openai": 0.003,
#     "other": 0.0,
#     "total": 0.121
# }
```

**Get Cost History:**
```python
history = cost_service.get_cost_history(user_id, months=12)
# Returns: [
#     {
#         "month": "2024-11",
#         "costs": {"whisper": 0.0, "s3": 0.0, ..., "total": 0.0}
#     },
#     ...
# ]
```

#### User Credit Management

**Initialize User Credit:**
```python
cost_service.initialize_user_credit(user_id, initial_credit=1.00)
# New users get $1.00 in free credits
```

**Get User Credit:**
```python
credit_info = cost_service.get_user_credit(user_id)
# Returns: {
#     "balance": 0.88,
#     "initial": 1.00,
#     "used": 0.12,
#     "refunded": 0.0,
#     "last_updated": "2025-10-25T23:45:30"
# }
```

## API Endpoints

### GET /api/user/cost-summary

Returns complete cost summary and credit information for the current user.

**Response:**
```json
{
  "current_month": "2025-10",
  "current_month_cost": 0.121,
  "current_month_breakdown": {
    "whisper": 0.06,
    "s3": 0.002,
    "dynamodb": 0.00025,
    "ses": 0.005,
    "secrets_manager": 0.05,
    "openai": 0.003,
    "other": 0.0
  },
  "total_usage": {
    "whisper": 0.06,
    "s3": 0.002,
    "dynamodb": 0.00025,
    "ses": 0.005,
    "secrets_manager": 0.05,
    "openai": 0.003,
    "other": 0.0,
    "total": 0.121
  },
  "credit_balance": 0.88,
  "monthly_history": [
    {
      "month": "2024-11",
      "total": 0.0,
      "breakdown": { ... }
    },
    ...
  ]
}
```

### GET /api/user/credit

Returns detailed credit account information.

**Response:**
```json
{
  "balance": 0.88,
  "initial": 1.00,
  "used": 0.12,
  "refunded": 0.0,
  "last_updated": "2025-10-25T23:45:30"
}
```

## Integration Points

### Automatic Cost Recording

Costs are automatically recorded when API operations occur:

1. **Audio Upload** - S3 cost recorded in `audio_service.py:create_audio_file()`
2. **User Creation** - Credit initialized in `user_service.py:create_user()`
3. **Whisper Transcription** - Cost recorded in background processor (TBD)
4. **OpenAI Summarization** - Cost recorded in OpenAI integration (TBD)

### Android App Integration

The cost screen displays the `/api/user/cost-summary` endpoint data:

**CostScreen.kt Features:**
- Available credit balance with warning when < $1.00
- Current month cost breakdown by service
- Last 6 months historical trend
- Cost transparency information card explaining all pricing

## Testing

### Run Full Workflow Test

```bash
AWS_ACCESS_KEY_ID=xxx AWS_SECRET_ACCESS_KEY=yyy python3 test_cost_tracking_workflow.py
```

This test demonstrates:
1. Initializing user credit
2. Recording multiple service usages
3. Viewing current month costs
4. Checking user credit balance
5. Viewing historical cost data
6. Verifying all tables are accessible

### Expected Output

The test will show:
- Step 1: User credit initialized at $1.00
- Step 2: Multiple services recorded with individual costs
- Step 3: Current month breakdown totaling costs
- Step 4: Credit balance after all charges
- Step 5: 12-month cost history
- Step 6: All tables verified as accessible

## Administration

### Creating Tables

If tables need to be recreated:

```bash
AWS_ACCESS_KEY_ID=xxx AWS_SECRET_ACCESS_KEY=yyy python3 create_cost_tracking_tables.py
```

This script will:
1. Create all three DynamoDB tables with proper schema
2. Set up Global Secondary Indexes for efficient querying
3. Wait for tables to become ACTIVE
4. Print final status summary

### Monitoring Costs

Monitor real-time costs by querying DynamoDB directly:

```bash
# View all usage records for a user in current month
aws dynamodb query \
  --table-name panzoto-usage-records \
  --index-name user-month-index \
  --key-condition-expression "user_id = :uid AND #m = :month" \
  --expression-attribute-names '{"#m":"month"}' \
  --expression-attribute-values "{\":uid\":{\"S\":\"USER_ID\"},\":month\":{\"S\":\"2025-10\"}}"
```

## Future Enhancements

### Short-term (Next Release)
- [ ] Add email notifications when credit runs low
- [ ] Implement credit purchase flow
- [ ] Add cost alerts for high-usage days
- [ ] Generate monthly cost reports

### Medium-term
- [ ] Implement tiered pricing discounts for high volumes
- [ ] Add cost forecasting based on historical usage
- [ ] Create admin dashboard for all-user cost monitoring
- [ ] Implement refund management system

### Long-term
- [ ] Real-time cost tracking dashboard
- [ ] Usage optimization recommendations
- [ ] Cost analytics and trends
- [ ] Budget management with alerts

## Troubleshooting

### Tables Not Found

If you see "ResourceNotFoundException" errors:

1. **Check table existence:**
   ```bash
   aws dynamodb list-tables --region us-east-1
   ```

2. **Create tables if missing:**
   ```bash
   python3 create_cost_tracking_tables.py
   ```

3. **Verify table schema:**
   ```bash
   aws dynamodb describe-table --table-name panzoto-usage-records
   ```

### Cost Not Updating

1. Check the API logs for error messages
2. Verify AWS credentials are correct
3. Ensure user credit has been initialized
4. Check that the cost service is being called (see integration points)

### Credit Balance Issues

If a user has negative balance:
- Contact support for manual refund
- Implement credit purchase flow
- Add billing protection to prevent overdraft

## References

- **Cost Service:** `decision_data/backend/services/cost_tracking_service.py`
- **Table Creation:** `create_cost_tracking_tables.py`
- **Test Workflow:** `test_cost_tracking_workflow.py`
- **API Endpoint:** `decision_data/api/backend/api.py:get_cost_summary()`
- **Android UI:** `Panzoto/app/src/main/java/com/example/panzoto/ui/CostScreen.kt`

## Last Updated

October 25, 2025 - Initial implementation complete
