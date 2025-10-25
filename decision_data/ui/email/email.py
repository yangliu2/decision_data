"""Send an email using AWS SES (Simple Email Service)"""

import boto3
from decision_data.backend.config.config import backend_config
from decision_data.data_structure.models import DailySummary
from loguru import logger


def format_message(
    llm_resopnse: DailySummary,
    date: str,
) -> str:
    """Format the LLM response into an HTML email message."""
    body = f"""
    <h2>{date}</h2>
    <h2>Family</h2>
    <ul>
        {''.join([f'<li>{item}</li>' for item in llm_resopnse.family_info])}
    </ul>

    <h2>Business</h2>
    <ul>
        {''.join([f'<li>{item}</li>' for item in llm_resopnse.business_info])}
    </ul>

    <h2>Misc</h2>
    <ul>
        {''.join([f'<li>{item}</li>' for item in llm_resopnse.misc_info])}
    </ul>
    """

    return body


def send_email(
    recipient_email: str,
    subject: str,
    message_body: str,
) -> str:
    """Send email using AWS SES (Simple Email Service).

    Args:
        recipient_email: Email address to send to
        subject: Email subject line
        message_body: HTML email body

    Returns:
        Success message with AWS SES Message ID

    Raises:
        Exception: If SES API call fails
    """
    try:
        client = boto3.client(
            "ses",
            region_name=backend_config.REGION_NAME,
            aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY,
        )

        sender_email = backend_config.EMAIL_SENDER

        response = client.send_email(
            Source=sender_email,
            Destination={
                "ToAddresses": [recipient_email],
            },
            Message={
                "Subject": {
                    "Data": subject,
                    "Charset": "UTF-8",
                },
                "Body": {
                    "Html": {
                        "Data": message_body,
                        "Charset": "UTF-8",
                    },
                },
            },
        )

        message_id = response.get("MessageId")
        logger.info(f"[AWS SES] Email sent to {recipient_email}. Message ID: {message_id}")
        return f"Message sent successfully (AWS SES Message ID: {message_id})"

    except Exception as e:
        logger.error(f"[AWS SES] Failed to send email to {recipient_email}: {e}")
        raise
