import pytest
import smtplib
from unittest.mock import patch
from decision_data.ui.email.email import format_message, send_email
from decision_data.data_structure.models import DailySummary


def test_format_message():
    llm_response = DailySummary(
        family_info=["Family event 1", "Family event 2"],
        business_info=["Business meeting 1", "Business meeting 2"],
        misc_info=["Misc info 1", "Misc info 2"],
    )
    date = "2022-01-01"

    expected_message = """
    <h2>2022-01-01</h2>
    <h2>Family</h2>
    <ul>
        <li>Family event 1</li><li>Family event 2</li>
    </ul>

    <h2>Business</h2>
    <ul>
        <li>Business meeting 1</li><li>Business meeting 2</li>
    </ul>

    <h2>Misc</h2>
    <ul>
        <li>Misc info 1</li><li>Misc info 2</li>
    </ul>
    """

    formatted_message = format_message(llm_response, date)
    assert formatted_message.strip() == expected_message.strip()


@patch("smtplib.SMTP")
def test_send_email_failure(mock_smtp):
    mock_smtp.side_effect = smtplib.SMTPException("Failed to send email")

    recipient_email = "test@example.com"
    subject = "Test Subject"
    message_body = "This is a test email body."

    with pytest.raises(smtplib.SMTPException, match="Failed to send email"):
        send_email(
            recipient_email=recipient_email,
            subject=subject,
            message_body=message_body,
        )


if __name__ == "__main__":
    pytest.main()
