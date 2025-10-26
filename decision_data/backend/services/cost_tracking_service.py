"""
Cost tracking service for monitoring API usage and calculating costs.
Tracks usage of Whisper, S3, DynamoDB, SES, and other services.
"""

import boto3
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, List
import uuid

logger = logging.getLogger(__name__)

# Pricing as of October 2025 (Update these as prices change)
PRICING = {
    "whisper": {
        "per_minute": 0.006,  # $0.006 per minute of audio
    },
    "s3": {
        "per_gb_upload": 0.023,  # $0.023 per GB uploaded
        "per_gb_download": 0.0,  # No cost for downloads within AWS region
        "per_gb_storage": 0.023,  # $0.023 per GB stored per month
    },
    "dynamodb": {
        "per_1m_read_units": 0.25,  # $0.25 per 1M read units
        "per_1m_write_units": 1.25,  # $1.25 per 1M write units
    },
    "ses": {
        "per_1000_emails": 0.10,  # $0.10 per 1000 emails sent
    },
    "secrets_manager": {
        "per_secret_per_month": 0.40,  # $0.40 per secret per month
        "per_secret_retrieval": 0.05,  # $0.05 per secret retrieval (10k free per month per secret)
    },
    "openai": {
        "gpt5_per_1k_input_tokens": 0.003,  # $0.003 per 1K input tokens (gpt-5)
        "gpt5_per_1k_output_tokens": 0.006,  # $0.006 per 1K output tokens (gpt-5)
    },
}


class CostTrackingService:
    """Service for tracking and calculating API costs"""

    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        self.usage_table = self.dynamodb.Table("panzoto-usage-records")
        self.cost_summary_table = self.dynamodb.Table("panzoto-cost-summaries")
        self.user_credit_table = self.dynamodb.Table("panzoto-user-credits")

    def record_usage(
        self,
        user_id: str,
        service: str,
        operation: str,
        quantity: float,
        unit: str,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """
        Record a usage event for cost tracking.

        Args:
            user_id: User ID
            service: Service name (whisper, s3, dynamodb, ses, etc)
            operation: Operation type (transcribe, upload, query, send_email, etc)
            quantity: Amount of resource used
            unit: Unit of measurement (minutes, MB, requests, etc)
            metadata: Optional additional metadata

        Returns:
            True if recorded successfully
        """
        try:
            # Calculate cost based on service and quantity
            cost_usd = self._calculate_cost(service, operation, quantity)

            usage_id = str(uuid.uuid4())
            current_time = datetime.utcnow().isoformat()
            month = datetime.utcnow().strftime("%Y-%m")

            item = {
                "usage_id": usage_id,
                "user_id": user_id,
                "service": service,
                "operation": operation,
                "quantity": Decimal(str(quantity)),
                "unit": unit,
                "cost_usd": Decimal(str(cost_usd)),
                "timestamp": current_time,
                "month": month,
            }

            if metadata:
                item["metadata"] = metadata

            self.usage_table.put_item(Item=item)
            logger.info(
                f"[OK] Recorded usage: {user_id} | {service} | {operation} | "
                f"{quantity}{unit} | ${cost_usd:.4f}"
            )

            # Deduct from user credit
            self._deduct_credit(user_id, cost_usd)

            return True

        except Exception as e:
            logger.error(f"[ERROR] Failed to record usage: {e}")
            return False

    def record_whisper_usage(self, user_id: str, duration_minutes: float) -> bool:
        """Record Whisper transcription usage"""
        return self.record_usage(
            user_id=user_id,
            service="whisper",
            operation="transcribe",
            quantity=duration_minutes,
            unit="minutes",
            metadata={"model": "whisper-1"},
        )

    def record_s3_usage(
        self, user_id: str, operation: str, size_mb: float
    ) -> bool:
        """Record S3 storage/upload usage"""
        return self.record_usage(
            user_id=user_id,
            service="s3",
            operation=operation,  # "upload", "download", "storage"
            quantity=size_mb / 1024,  # Convert to GB
            unit="GB",
        )

    def record_dynamodb_usage(
        self, user_id: str, operation: str, units: float
    ) -> bool:
        """Record DynamoDB usage (read or write units)"""
        return self.record_usage(
            user_id=user_id,
            service="dynamodb",
            operation=operation,  # "read_units", "write_units"
            quantity=units,
            unit="units",
        )

    def record_ses_usage(self, user_id: str, email_count: int) -> bool:
        """Record SES email sending usage"""
        return self.record_usage(
            user_id=user_id,
            service="ses",
            operation="send_email",
            quantity=email_count,
            unit="emails",
        )

    def record_secrets_manager_retrieval(self, user_id: str) -> bool:
        """Record AWS Secrets Manager secret retrieval"""
        return self.record_usage(
            user_id=user_id,
            service="secrets_manager",
            operation="retrieval",
            quantity=1,
            unit="retrieval",
        )

    def record_openai_summarization(
        self,
        user_id: str,
        input_tokens: int,
        output_tokens: int
    ) -> bool:
        """Record OpenAI API usage for summarization (gpt-5)"""
        return self.record_usage(
            user_id=user_id,
            service="openai",
            operation="gpt5_summarization",
            quantity=input_tokens + output_tokens,  # Store combined tokens
            unit="tokens",
            metadata={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "model": "gpt-5"
            }
        )

    def get_monthly_cost(self, user_id: str, month: str) -> Dict:
        """
        Get cost breakdown for a specific month (YYYY-MM format)

        Returns:
            Dictionary with costs by service
        """
        try:
            response = self.usage_table.query(
                IndexName="user-month-index",
                KeyConditionExpression="user_id = :user_id AND #month = :month",
                ExpressionAttributeNames={"#month": "month"},
                ExpressionAttributeValues={
                    ":user_id": user_id,
                    ":month": month,
                },
            )

            costs = {
                "whisper": 0.0,
                "s3": 0.0,
                "dynamodb": 0.0,
                "ses": 0.0,
                "secrets_manager": 0.0,
                "openai": 0.0,
                "other": 0.0,
                "total": 0.0,
            }

            for item in response.get("Items", []):
                service = item.get("service", "other")
                cost = float(item.get("cost_usd", 0))

                if service in costs:
                    costs[service] += cost
                else:
                    costs["other"] += cost

            costs["total"] = sum(v for k, v in costs.items() if k != "total")

            return costs

        except Exception as e:
            logger.error(f"[ERROR] Failed to get monthly cost: {e}")
            return {
                "whisper": 0.0,
                "s3": 0.0,
                "dynamodb": 0.0,
                "ses": 0.0,
                "secrets_manager": 0.0,
                "openai": 0.0,
                "other": 0.0,
                "total": 0.0,
            }

    def get_current_month_usage(self, user_id: str) -> Dict:
        """Get usage summary for current month"""
        current_month = datetime.utcnow().strftime("%Y-%m")
        return self.get_monthly_cost(user_id, current_month)

    def get_cost_history(self, user_id: str, months: int = 12) -> List[Dict]:
        """Get cost history for past N months"""
        history = []
        now = datetime.utcnow()

        for i in range(months):
            month_date = now - timedelta(days=30 * i)
            month_str = month_date.strftime("%Y-%m")
            costs = self.get_monthly_cost(user_id, month_str)
            history.append({"month": month_str, "costs": costs})

        return sorted(history, key=lambda x: x["month"])

    def get_user_credit(self, user_id: str) -> Optional[Dict]:
        """Get user's credit account information"""
        try:
            response = self.user_credit_table.get_item(Key={"user_id": user_id})
            if "Item" in response:
                item = response["Item"]
                return {
                    "balance": float(item.get("credit_balance", 0)),
                    "initial": float(item.get("initial_credit", 0)),
                    "used": float(item.get("used_credit", 0)),
                    "refunded": float(item.get("refunded_credit", 0)),
                    "last_updated": item.get("last_updated", ""),
                }
            return None
        except Exception as e:
            logger.error(f"[ERROR] Failed to get user credit: {e}")
            return None

    def initialize_user_credit(self, user_id: str, initial_credit: float) -> bool:
        """Initialize credit account for a new user"""
        try:
            current_time = datetime.utcnow().isoformat()

            item = {
                "user_id": user_id,
                "credit_balance": Decimal(str(initial_credit)),
                "initial_credit": Decimal(str(initial_credit)),
                "used_credit": Decimal("0"),
                "refunded_credit": Decimal("0"),
                "last_updated": current_time,
            }

            self.user_credit_table.put_item(Item=item)
            logger.info(
                f"[OK] Initialized credit for {user_id}: ${initial_credit}"
            )
            return True

        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize credit: {e}")
            return False

    def _calculate_cost(self, service: str, operation: str, quantity: float) -> float:
        """Calculate cost based on service and operation"""
        try:
            if service == "whisper":
                return quantity * PRICING["whisper"]["per_minute"]

            elif service == "s3":
                if operation == "upload":
                    return quantity * PRICING["s3"]["per_gb_upload"]
                elif operation == "storage":
                    return quantity * PRICING["s3"]["per_gb_storage"]
                else:
                    return quantity * PRICING["s3"]["per_gb_download"]

            elif service == "dynamodb":
                if operation == "read_units":
                    return (quantity / 1_000_000) * PRICING["dynamodb"][
                        "per_1m_read_units"
                    ]
                elif operation == "write_units":
                    return (quantity / 1_000_000) * PRICING["dynamodb"][
                        "per_1m_write_units"
                    ]

            elif service == "ses":
                return (quantity / 1000) * PRICING["ses"]["per_1000_emails"]

            elif service == "secrets_manager":
                if operation == "retrieval":
                    return PRICING["secrets_manager"]["per_secret_retrieval"]
                else:
                    return PRICING["secrets_manager"]["per_secret_per_month"]

            elif service == "openai":
                if operation == "gpt5_summarization":
                    # quantity contains total tokens, calculate split from metadata
                    # Estimate: assume balanced split of input/output for cost calculation
                    input_tokens = quantity / 2
                    output_tokens = quantity / 2
                    input_cost = (input_tokens / 1000) * PRICING["openai"]["gpt5_per_1k_input_tokens"]
                    output_cost = (output_tokens / 1000) * PRICING["openai"]["gpt5_per_1k_output_tokens"]
                    return input_cost + output_cost
                return 0.0

            return 0.0

        except Exception as e:
            logger.error(f"[ERROR] Cost calculation failed: {e}")
            return 0.0

    def _deduct_credit(self, user_id: str, amount: float) -> bool:
        """Deduct cost from user's credit balance"""
        try:
            credit_info = self.get_user_credit(user_id)
            if not credit_info:
                return False

            new_balance = credit_info["balance"] - amount
            used_credit = credit_info["used"] + amount

            self.user_credit_table.update_item(
                Key={"user_id": user_id},
                UpdateExpression="SET credit_balance = :balance, used_credit = :used, "
                "last_updated = :timestamp",
                ExpressionAttributeValues={
                    ":balance": Decimal(str(max(0, new_balance))),
                    ":used": Decimal(str(used_credit)),
                    ":timestamp": datetime.utcnow().isoformat(),
                },
            )

            if new_balance < 0:
                logger.warning(
                    f"[WARN] User {user_id} credit balance negative: ${new_balance}"
                )

            return True

        except Exception as e:
            logger.error(f"[ERROR] Failed to deduct credit: {e}")
            return False


# Singleton instance
_cost_tracking_service = None


def get_cost_tracking_service() -> CostTrackingService:
    """Get or create singleton instance"""
    global _cost_tracking_service
    if _cost_tracking_service is None:
        _cost_tracking_service = CostTrackingService()
    return _cost_tracking_service
