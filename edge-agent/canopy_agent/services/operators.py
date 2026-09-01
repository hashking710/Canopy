import hashlib
import secrets

from fastapi import HTTPException
from sqlalchemy.orm import Session

from canopy_agent.compliance_models import Operator

PBKDF2_ITERATIONS = 210_000  # OWASP's current minimum recommendation for PBKDF2-HMAC-SHA256

# Not about keeping an untrusted party out (everyone already shares the one API
# token, see auth.py) — about a legitimate dashboard user picking "who I am" and
# the API refusing an action that role isn't allowed, same spirit as the PIN
# confirmation already required for plant destruction. "viewer" can look but not
# touch; "operator" is today's baseline — everyday facility work an operator could
# always do (compliance mutations, room/alert-rule configuration); "admin" is
# reserved for the facility's most sensitive category, credentials, plus
# operator/role management itself.
ROLE_RANK = {"viewer": 0, "operator": 1, "admin": 2}
KNOWN_ROLES = frozenset(ROLE_RANK)


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


def has_role_at_least(operator: Operator, min_role: str) -> bool:
    return ROLE_RANK.get(operator.role, 0) >= ROLE_RANK[min_role]


def require_role(operator: Operator, min_role: str) -> None:
    """Raises 403, not 401 — the operator is real and (for PIN-gated actions)
    already correctly authenticated; this is an authorization failure, a
    different thing than a missing/wrong credential."""
    if not has_role_at_least(operator, min_role):
        raise HTTPException(
            status_code=403,
            detail=f"operator '{operator.name}' has role '{operator.role}', this action requires at least '{min_role}'",
        )


def resolve_operator_with_role(db: Session, operator_id: str, min_role: str) -> Operator:
    """Resolves a real, active operator by id (404 if missing/inactive) and
    requires they hold at least min_role (403 if not) — the shared shape behind
    every "this write endpoint needs to know who's doing it, and refuse a
    viewer" check outside compliance.py (whose own _resolve_operator predates
    this and additionally handles witness attribution — not worth refactoring
    just for the sake of one shared helper)."""
    operator = get_active_operator(db, operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail=f"operator '{operator_id}' not found or inactive")
    require_role(operator, min_role)
    return operator
