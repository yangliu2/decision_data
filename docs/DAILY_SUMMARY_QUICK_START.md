# Daily Summary - Quick Start Guide

## What Is Daily Summary?

Automatic email summaries of your daily interactions, sent the next day to your email address. The system:
- Collects all transcripts from your recordings
- Summarizes them into 3 categories: Family, Business, Misc
- Sends an HTML email with the summary
- Respects your preferences (time, email, enable/disable)

## User Flow

### 1. First Time Setup

Go to **Settings** in the Android app and ensure:
- ✅ Email address is set (Settings → Notification Email)
- ✅ Daily summary is enabled (Settings → Enable Daily Summary)
- ✅ Choose preferred time (Settings → Summary Time)

### 2. Request Daily Summary

In **Processing Status** screen, tap **Request Daily Summary** button.

This creates a job in the background processor. The job will:
- Generate within 30 seconds
- Summary is for **yesterday's** transcripts
- Email is sent to your notification email
- You can see job status as "Pending" → "Completed"

### 3. Check Your Email

Look for email from `sender@gmail.com` with subject: **PANZOTO: Daily Summary**

Example content:
```
2025-10-20

Family
- Had lunch with Mom at noon
- Kids soccer game at 4 PM

Business
- Discussed Q4 roadmap with team
- Client call about new features

Misc
- Weather looks good tomorrow
- Need to book hotel for trip
```

## API Endpoint

### Create Daily Summary Job

```
POST /api/user/request-daily-summary
Headers: Authorization: Bearer {jwt_token}
```

**Response:**
```json
{
    "message": "Daily summary job created",
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "pending"
}
```

## User Preferences

### Get Your Preferences

```
GET /api/user/preferences
Headers: Authorization: Bearer {jwt_token}
```

### Update Preferences

```
PUT /api/user/preferences
Headers: Authorization: Bearer {jwt_token}

{
    "notification_email": "yournewemail@example.com",
    "enable_daily_summary": true,
    "summary_time_utc": "09:00"
}
```

### Important Fields

| Field | Example | Notes |
|-------|---------|-------|
| `notification_email` | user@example.com | Email to receive summaries |
| `enable_daily_summary` | true/false | Toggle summaries on/off |
| `summary_time_utc` | "09:00" | Preferred time (future feature) |

## How It Works

1. **You tap:** "Request Daily Summary"
2. **Backend creates:** Processing job with `job_type='daily_summary'`
3. **Processor scans:** Every 30 seconds for pending jobs
4. **Processor generates:** Summary of yesterday's transcripts
5. **Email is sent:** To your notification email address
6. **Job completes:** Status changes to "completed"

## Troubleshooting

### I didn't receive the email

1. Check **Settings** → Notification Email is set correctly
2. Check spam/promotions folder
3. Verify Gmail credentials in server config:
   - `GMAIL_ACCOUNT` is set
   - `GOOGLE_APP_PASSWORD` is correct (not regular Gmail password!)
4. Check server logs: `ssh root@206.189.185.129 "grep SUMMARY /var/log/api.log"`

### Job is stuck in "pending"

1. Verify `enable_daily_summary = true` in preferences
2. Check if server background processor is running:
   ```bash
   ssh root@206.189.185.129 "ps aux | grep uvicorn"
   ```
3. Check logs for errors:
   ```bash
   ssh root@206.189.185.129 "grep ERROR /var/log/api.log"
   ```

### No transcripts in summary

This means:
- You had a quiet day (no voice recordings)
- Transcripts were too short (less than 10 characters)
- OR recordings were not transcribed yet

Check the **Processing Status** → **Transcripts** tab to see if any transcripts exist for that day.

### Wrong email received the summary

1. Verify your **notification email** in preferences
2. Update it if incorrect:
   ```json
   PUT /api/user/preferences
   { "notification_email": "correct@email.com" }
   ```

## Configuration

### Server-Side Setup

1. Gmail account with 2-factor authentication
2. Generate **Gmail app password** (not your regular password):
   - Go to: https://myaccount.google.com/apppasswords
   - Select "Mail" and "Windows Computer"
   - Copy the generated password
3. Set environment variables:
   ```bash
   GMAIL_ACCOUNT="your-email@gmail.com"
   GOOGLE_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx"
   ```

4. Verify OpenAI API key is set:
   ```bash
   OPENAI_API_KEY="sk-..."
   ```

5. Verify MongoDB is configured:
   ```bash
   MONGODB_URI="mongodb+srv://..."
   MONGODB_TRANSCRIPTS_COLLECTION_NAME="transcripts"
   ```

## Retries & Error Handling

If a daily summary job fails:
- **Attempt 1/3:** Fails → waits 10 minutes
- **Attempt 2/3:** Fails → waits 10 minutes
- **Attempt 3/3:** Fails → marked as failed permanently

Check job status in **Processing Status** screen to see error message.

## Future Features

- [ ] Automatic scheduled summaries (send at preferred time daily)
- [ ] Customizable summary categories
- [ ] Multiple email templates
- [ ] Telegram/Slack summary delivery
- [ ] Summary history in app
- [ ] Filter by date range

## Need Help?

See detailed documentation: `docs/DAILY_SUMMARY_IMPLEMENTATION.md`

---

**Status:** ✅ Deployed and Ready
**Last Updated:** October 20, 2025
