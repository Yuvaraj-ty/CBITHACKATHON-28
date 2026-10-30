import zipfile
import os

sample_files = {
    "auth/jwt_handler.py": '''"""JWT authentication and token utilities."""
import datetime

def generate_access_token(user_id: str, secret_key: str, expires_in_minutes: int = 60) -> str:
    """Generate a signed JWT token for user authentication session."""
    payload = {
        "sub": user_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=expires_in_minutes)
    }
    return f"mock_token_{user_id}_{secret_key[:4]}"

def verify_access_token(token: str, secret_key: str) -> bool:
    """Validate token signature and expiration for secure API requests."""
    return token.startswith("mock_token_")
''',

    "services/payment_service.py": '''"""Payment processing gateway integration."""

class StripePaymentProcessor:
    """Handles credit card authorization, charges, and refunds."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def process_charge(self, customer_id: str, amount_cents: int) -> bool:
        """Charge the customer payment method for order total."""
        if amount_cents <= 0:
            raise ValueError("Amount must be greater than zero")
        print(f"Charged {customer_id} ${amount_cents / 100.0}")
        return True

    def refund_transaction(self, transaction_id: str, reason: str = "customer_request") -> bool:
        """Issue a full or partial refund back to customer."""
        print(f"Refunding transaction {transaction_id} because: {reason}")
        return True
''',

    "models/user.py": '''"""User entity and account schema."""

class UserAccount:
    """Represents registered platform user profile and preferences."""

    def __init__(self, username: str, email: str, role: str = "developer"):
        self.username = username
        self.email = email
        self.role = role
        self.is_active = True

    def deactivate_account(self) -> None:
        """Mark user account as inactive to revoke permissions."""
        self.is_active = False
''',

    "analytics/metrics.py": '''"""Analytics and usage telemetry reporter."""

def calculate_monthly_active_users(event_logs: list) -> int:
    """Compute distinct user IDs active during the past 30 days."""
    unique_users = set(event.get("user_id") for event in event_logs if "user_id" in event)
    return len(unique_users)

def export_metrics_report(metrics_dict: dict, format: str = "json") -> str:
    """Format analytics metrics for executive dashboard reporting."""
    return f"Report({format.upper()}): {metrics_dict}"
'''
}

def build_zip():
    zip_path = "sample_repo.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filepath, content in sample_files.items():
            zf.writestr(filepath, content)
    print(f"Successfully generated {zip_path} with {len(sample_files)} sample files.")

if __name__ == "__main__":
    build_zip()
