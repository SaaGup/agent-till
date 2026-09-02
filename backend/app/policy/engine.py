from dataclasses import dataclass

from app.policy.rules import PolicyConfig


@dataclass(frozen=True)
class DiscountDecision:
    requested_pct: float
    capped_pct: float
    was_capped: bool
    explanation: str


@dataclass(frozen=True)
class TxnDecision:
    allowed: bool
    blocked: bool
    requires_approval: bool
    explanation: str
    decision: str  # allowed | blocked | pending_approval


def evaluate_discount(requested_pct: float, cfg: PolicyConfig) -> DiscountDecision:
    requested = max(0.0, requested_pct)
    capped = min(requested, cfg.max_discount_pct)
    was_capped = capped < requested
    if was_capped:
        explanation = (
            f"Requested {requested:g}% discount exceeds the {cfg.max_discount_pct:g}% "
            f"policy cap; capped to {capped:g}%."
        )
    else:
        explanation = (
            f"Requested {requested:g}% discount is within the {cfg.max_discount_pct:g}% policy cap."
        )
    return DiscountDecision(requested, capped, was_capped, explanation)


def evaluate_transaction(
    total_inr: float,
    session_spend_to_date_inr: float,
    is_first_time_buyer: bool,
    cfg: PolicyConfig,
) -> TxnDecision:
    if total_inr > cfg.max_txn_value_inr:
        return TxnDecision(
            allowed=False,
            blocked=True,
            requires_approval=False,
            decision="blocked",
            explanation=(
                f"Order total ₹{total_inr:g} exceeds the per-transaction hard cap of "
                f"₹{cfg.max_txn_value_inr:g}; blocked outright, not merely gated."
            ),
        )

    projected_session_spend = session_spend_to_date_inr + total_inr
    if projected_session_spend > cfg.max_session_spend_inr:
        return TxnDecision(
            allowed=False,
            blocked=True,
            requires_approval=False,
            decision="blocked",
            explanation=(
                f"This order would bring session spend to ₹{projected_session_spend:g}, "
                f"above the ₹{cfg.max_session_spend_inr:g} cumulative session cap "
                f"(₹{session_spend_to_date_inr:g} already spent); blocked to bound the "
                f"agent's total blast radius."
            ),
        )

    reasons = []
    if total_inr > cfg.approval_threshold_inr:
        reasons.append(
            f"total ₹{total_inr:g} exceeds the ₹{cfg.approval_threshold_inr:g} approval threshold"
        )
    if is_first_time_buyer and cfg.first_time_buyer_requires_approval:
        reasons.append("this is the session's first transaction")

    if reasons:
        return TxnDecision(
            allowed=True,
            blocked=False,
            requires_approval=True,
            decision="pending_approval",
            explanation="Merchant approval required: " + "; ".join(reasons) + ".",
        )

    return TxnDecision(
        allowed=True,
        blocked=False,
        requires_approval=False,
        decision="allowed",
        explanation=(
            f"Order total ₹{total_inr:g} is within all policy limits "
            f"(per-transaction ₹{cfg.max_txn_value_inr:g}, session ₹{cfg.max_session_spend_inr:g}, "
            f"approval threshold ₹{cfg.approval_threshold_inr:g}); approved without merchant review."
        ),
    )


class CircuitOpenError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class CircuitBreaker:
    """Bounds one agent turn: caps total tool calls and trips on repeated tool failures,
    so a confused or looping agent stops rather than burning budget or hammering the payment API."""

    def __init__(self, cfg: PolicyConfig):
        self.cfg = cfg
        self.tool_calls_this_turn = 0
        self.consecutive_errors = 0
        self.tripped_reason: str | None = None

    def reset_turn(self) -> None:
        self.tool_calls_this_turn = 0

    def record_call(self) -> None:
        self.tool_calls_this_turn += 1
        if self.tool_calls_this_turn > self.cfg.max_tool_calls_per_turn:
            self.tripped_reason = (
                f"Agent exceeded {self.cfg.max_tool_calls_per_turn} tool calls in a single turn."
            )
            raise CircuitOpenError(self.tripped_reason)

    def record_result(self, is_error: bool) -> None:
        if is_error:
            self.consecutive_errors += 1
            if self.consecutive_errors >= self.cfg.max_consecutive_tool_errors:
                self.tripped_reason = (
                    f"Agent hit {self.consecutive_errors} consecutive tool errors."
                )
                raise CircuitOpenError(self.tripped_reason)
        else:
            self.consecutive_errors = 0

    @property
    def is_tripped(self) -> bool:
        return self.tripped_reason is not None
