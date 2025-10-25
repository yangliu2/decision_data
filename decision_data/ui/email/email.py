"""Send an email using AWS SES or Gmail SMTP"""

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


def send_email_aws_ses(
    recipient_email: str,
    subject: str,
    message_body: str,
) -> str:
    """Send email using AWS SES (Simple Email Service)."""
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
        logger.info(f"[AWS SES] Email sent successfully. Message ID: {message_id}")
        return f"Message sent successfully (AWS SES Message ID: {message_id})"

    except Exception as e:
        logger.error(f"[AWS SES] Failed to send email: {e}")
        raise


def send_email_gmail(
    recipient_email: str,
    subject: str,
    message_body: str,
) -> str:
    """Send email using Gmail SMTP (legacy, for backward compatibility)."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = backend_config.GMAIL_ACCOUNT
    sender_password = backend_config.GOOGLE_APP_PASSWORD

    # Create the email message object
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject

    # Attach the message body
    body = MIMEText(message_body, "html")
    msg.attach(body)

    # Send the email
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())

    logger.info(f"[Gmail SMTP] Email sent to {recipient_email}")
    return "Message sent successfully (Gmail SMTP)"


def send_email(
    recipient_email: str,
    subject: str,
    message_body: str,
) -> str:
    """Send email using configured provider (AWS SES or Gmail SMTP)."""
    provider = backend_config.EMAIL_PROVIDER.lower()

    if provider == "aws_ses":
        return send_email_aws_ses(recipient_email, subject, message_body)
    elif provider == "gmail":
        return send_email_gmail(recipient_email, subject, message_body)
    else:
        raise ValueError(
            f"Unknown email provider: {provider}. "
            f"Supported: 'aws_ses', 'gmail'"
        )
