"""Send an email"""

import smtplib
from decision_data.backend.config.config import backend_config
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from decision_data.data_structure.models import DailySummary


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
    """Sending an email to a recipient using the smtplib library."""
    # Set your email credentials (Gmail example)
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = backend_config.GMAIL_ACCOUNT
    sender_password = backend_config.GOOGLE_APP_PASSWORD

    # Create the email message object
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject  # Subject line

    # Attach the message body (plain text)
    body = MIMEText(message_body, "html")
    msg.attach(body)

    # Send the email (which will be received as an SMS)
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())

    return "Message sent successfully"
