from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class PolicyConfig:
    """Server-side, env-driven guardrails. The LLM never sets these values — it can only
    request actions, which these numbers then cap, block, or gate regardless of the request."""

    max_discount_pct: float = 20.0
    approval_threshold_inr: float = 3000.0
    max_txn_value_inr: float = 5000.0
    max_session_spend_inr: float = 8000.0
    first_time_buyer_requires_approval: bool = True
    max_items_per_order: int = 5
    max_tool_calls_per_turn: int = 8
    max_consecutive_tool_errors: int = 3

    @classmethod
    def from_settings(cls) -> "PolicyConfig":
        return cls(
            max_discount_pct=settings.policy_max_discount_pct,
            approval_threshold_inr=settings.policy_approval_threshold_inr,
            max_txn_value_inr=settings.policy_max_txn_value_inr,
            max_session_spend_inr=settings.policy_max_session_spend_inr,
            max_items_per_order=settings.policy_max_items_per_order,
            max_tool_calls_per_turn=settings.policy_max_tool_calls_per_turn,
            max_consecutive_tool_errors=settings.policy_max_consecutive_tool_errors,
        )

    def as_snapshot(self) -> dict:
        """Serialized alongside every audit row so a later policy change never retroactively
        alters the recorded explanation for a past decision."""
        return {
            "max_discount_pct": self.max_discount_pct,
            "approval_threshold_inr": self.approval_threshold_inr,
            "max_txn_value_inr": self.max_txn_value_inr,
            "max_session_spend_inr": self.max_session_spend_inr,
            "first_time_buyer_requires_approval": self.first_time_buyer_requires_approval,
            "max_items_per_order": self.max_items_per_order,
            "max_tool_calls_per_turn": self.max_tool_calls_per_turn,
            "max_consecutive_tool_errors": self.max_consecutive_tool_errors,
        }
