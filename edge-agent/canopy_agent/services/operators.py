import hashlib
import secrets

from sqlalchemy.orm import Session

from canopy_agent.compliance_models import Operator

PBKDF2_ITERATIONS = 210_000  # OWASP's current minimum recommendation for PBKDF2-HMAC-SHA256


def _hash_pin(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), PBKDF2_ITERATIONS).hex()


def set_pin(operator: Operator, pin: str) -> None:
    salt = secrets.token_hex(16)
    operator.pin_salt = salt
    operator.pin_hash = _hash_pin(pin, salt)


def verify_pin(operator: Operator, pin: str) -> bool:
    if not operator.pin_hash or not operator.pin_salt:
        return False
    return secrets.compare_digest(_hash_pin(pin, operator.pin_salt), operator.pin_hash)


def pin_check_failed(operator: Operator, provided_pin: str | None) -> bool:
    """True if this operator has a PIN configured and the provided one (missing or
    wrong) doesn't clear it. Operators without a PIN configured always pass — a PIN is
    an optional extra confirmation layer for high-stakes actions, not mandatory
    registration friction for every operator."""
    if not operator.pin_hash:
        return False
    return provided_pin is None or not verify_pin(operator, provided_pin)


def get_active_operator(db: Session, operator_id: str) -> Operator | None:
    operator = db.get(Operator, operator_id)
    if operator is None or not operator.active:
        return None
    return operator
