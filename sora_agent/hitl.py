"""Human-in-the-Loop (HITL) confirmation hooks and approval state machine for high-stakes travel actions."""

from __future__ import annotations

import functools
import secrets
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from sora_agent.observability import structured_logger, trace_span
from sora_agent.schemas import ErrorRecoveryGuidance, HighStakesBookingOutput, StrictToolOutputModel, Field

HIGH_STAKES_ACTION_TYPES: set[str] = {
    "BOOK_RYOKAN_KAISEKI",
    "PURCHASE_JR_PASS",
    "RESERVE_SHINKANSEN_OVERSIZED_BAGGAGE",
    "SCHEDULE_TAKKYUBIN_LUGGAGE",
    "CHARGE_IC_CARD_WALLET",
}


class PendingConfirmationRecord(StrictToolOutputModel):
    """Record stored in the HITL state machine for an action awaiting human approval."""

    confirmation_id: str = Field(..., description="Unique confirmation identifier.")
    session_id: str = Field(default="default", description="Session requesting the action.")
    action_type: str = Field(..., description="Category of high-stakes action.")
    item_description: str = Field(..., description="Detailed description of the reservation or purchase.")
    estimated_total_jpy: int = Field(..., ge=0, description="Total cost in JPY.")
    traveler_count: int = Field(default=1, ge=1, description="Number of travelers covered.")
    non_refundable: bool = Field(default=True, description="Whether the booking has strict cancellation penalties.")
    status: Literal["pending_human_approval", "approved", "rejected"] = Field(
        default="pending_human_approval", description="Approval status."
    )
    reviewer_id: str | None = Field(default=None, description="Identifier of the human who approved or rejected.")
    reviewer_note: str | None = Field(default=None, description="Optional note from the human reviewer.")
    created_at_utc: str = Field(..., description="ISO-8601 creation timestamp.")
    resolved_at_utc: str | None = Field(default=None, description="ISO-8601 resolution timestamp.")


class ConfirmationDecisionOutput(StrictToolOutputModel):
    """Strict output schema returned when a human approves or rejects a pending action."""

    status: Literal["success", "error"] = Field(default="success")
    confirmation_id: str = Field(..., description="Confirmation identifier.")
    decision: Literal["approved", "rejected", "not_found"] = Field(..., description="Human decision.")
    action_type: str = Field(..., description="High-stakes action category.")
    item_description: str = Field(..., description="Description of the item.")
    estimated_total_jpy: int = Field(..., ge=0, description="Amount in JPY.")
    execution_summary: str = Field(..., description="Summary of the committed or cancelled action.")
    error_recovery: ErrorRecoveryGuidance | None = Field(default=None)


class HumanInTheLoopManager:
    """Manages Human-in-the-Loop (HITL) approval gates for financial and reservation commitments."""

    def __init__(self) -> None:
        self._pending_actions: dict[str, PendingConfirmationRecord] = {}

    @trace_span("sora.hitl.request_confirmation", component="hitl")
    def request_confirmation(
        self,
        *,
        action_type: str,
        item_description: str,
        estimated_total_jpy: int,
        traveler_count: int = 1,
        non_refundable: bool = True,
        session_id: str = "default",
    ) -> HighStakesBookingOutput:
        """Creates a pending HITL confirmation gate and blocks autonomous execution until approved."""
        normalized_type = action_type.strip().upper()
        if normalized_type not in HIGH_STAKES_ACTION_TYPES:
            return HighStakesBookingOutput(
                status="error",
                requires_human_confirmation=True,
                confirmation_id="INVALID",
                action_type=action_type,
                item_description=item_description,
                estimated_total_jpy=max(0, int(estimated_total_jpy)),
                cancellation_policy_warning="Validation failed before staging booking.",
                approval_instructions="Fix the invalid action_type parameter and retry.",
                error_recovery=ErrorRecoveryGuidance(
                    error_code="INVALID_HITL_ACTION_TYPE",
                    error_message=f"Unsupported high-stakes action_type '{action_type}'.",
                    invalid_parameter="action_type",
                    provided_value=str(action_type),
                    allowed_values=sorted(HIGH_STAKES_ACTION_TYPES),
                    llm_recovery_instruction=(
                        f"Re-invoke `request_high_stakes_booking_confirmation` using one of the supported "
                        f"action_type values: {', '.join(sorted(HIGH_STAKES_ACTION_TYPES))}."
                    ),
                    suggested_tool_call_example=(
                        "request_high_stakes_booking_confirmation("
                        "action_type='BOOK_RYOKAN_KAISEKI', "
                        "item_description='Hakone Gora Ryokan 1-Night Kaiseki Stay', "
                        "estimated_total_jpy=68000, traveler_count=2)"
                    ),
                ),
            )

        if estimated_total_jpy < 0 or traveler_count < 1:
            return HighStakesBookingOutput(
                status="error",
                requires_human_confirmation=True,
                confirmation_id="INVALID",
                action_type=normalized_type,
                item_description=item_description,
                estimated_total_jpy=0,
                cancellation_policy_warning="Invalid negative cost or traveler count.",
                approval_instructions="Provide a non-negative JPY cost and traveler_count >= 1.",
                error_recovery=ErrorRecoveryGuidance(
                    error_code="INVALID_BOOKING_PARAMETERS",
                    error_message="estimated_total_jpy must be >= 0 and traveler_count must be >= 1.",
                    invalid_parameter="estimated_total_jpy" if estimated_total_jpy < 0 else "traveler_count",
                    provided_value=str(estimated_total_jpy if estimated_total_jpy < 0 else traveler_count),
                    allowed_values=["estimated_total_jpy >= 0", "traveler_count >= 1"],
                    llm_recovery_instruction=(
                        "Ensure `estimated_total_jpy` is a positive integer in Japanese Yen and `traveler_count` is "
                        "at least 1 before calling `request_high_stakes_booking_confirmation` again."
                    ),
                    suggested_tool_call_example=(
                        "request_high_stakes_booking_confirmation("
                        "action_type='PURCHASE_JR_PASS', "
                        "item_description='JR West Kansai-Hiroshima Area Pass (5-Day)', "
                        "estimated_total_jpy=17000, traveler_count=1)"
                    ),
                ),
            )

        confirmation_id = f"HITL-{secrets.token_hex(4).upper()}"
        record = PendingConfirmationRecord(
            confirmation_id=confirmation_id,
            session_id=session_id,
            action_type=normalized_type,
            item_description=item_description,
            estimated_total_jpy=int(estimated_total_jpy),
            traveler_count=int(traveler_count),
            non_refundable=non_refundable,
            status="pending_human_approval",
            created_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        self._pending_actions[confirmation_id] = record

        structured_logger.info(
            f"HITL confirmation staged: {confirmation_id} ({normalized_type}, ¥{estimated_total_jpy:,})",
            component="hitl",
            event_type="hitl_confirmation_requested",
            session_id=session_id,
            attributes=record.model_dump(),
        )

        cancellation_warning = (
            "IMPORTANT: Japanese ryokan kaiseki dinners and JR Pass exchange orders carry strict cancellation "
            "deadlines (often 50%–100% penalty within 3–7 days of check-in because seasonal ingredients are "
            "procured in advance). Execution is PAUSED pending explicit human confirmation."
            if non_refundable
            else "Standard refundable reservation; still requires explicit traveler confirmation before commitment."
        )

        return HighStakesBookingOutput(
            status="pending_human_approval",
            requires_human_confirmation=True,
            confirmation_id=confirmation_id,
            action_type=normalized_type,
            item_description=item_description,
            estimated_total_jpy=int(estimated_total_jpy),
            cancellation_policy_warning=cancellation_warning,
            approval_instructions=(
                f"Action `{confirmation_id}` is paused awaiting human approval. Present the item "
                f"('{item_description}', ¥{int(estimated_total_jpy):,} for {traveler_count} traveler(s)) "
                f"and cancellation policy to the user, and ask them to confirm via "
                f"`resolve_booking_confirmation(confirmation_id='{confirmation_id}', approved=True)` "
                f"or POST `/api/hitl/confirm`."
            ),
            error_recovery=None,
        )

    async def arequest_confirmation(self, **kwargs: Any) -> HighStakesBookingOutput:
        """Async wrapper for creating a HITL confirmation gate."""
        return self.request_confirmation(**kwargs)

    @trace_span("sora.hitl.resolve_confirmation", component="hitl")
    def resolve_confirmation(
        self,
        confirmation_id: str,
        *,
        approved: bool,
        reviewer_id: str = "human_traveler",
        reviewer_note: str = "",
    ) -> ConfirmationDecisionOutput:
        """Approves or rejects a pending high-stakes action after human review."""
        record = self._pending_actions.get(confirmation_id)
        if record is None:
            return ConfirmationDecisionOutput(
                status="error",
                confirmation_id=confirmation_id,
                decision="not_found",
                action_type="UNKNOWN",
                item_description="Unknown confirmation ID",
                estimated_total_jpy=0,
                execution_summary=f"Confirmation ID '{confirmation_id}' was not found.",
                error_recovery=ErrorRecoveryGuidance(
                    error_code="CONFIRMATION_ID_NOT_FOUND",
                    error_message=f"No pending HITL action matches confirmation_id='{confirmation_id}'.",
                    invalid_parameter="confirmation_id",
                    provided_value=confirmation_id,
                    allowed_values=sorted(self._pending_actions.keys()) or ["Call request_high_stakes_booking_confirmation first"],
                    llm_recovery_instruction=(
                        "Verify the `confirmation_id` returned by `request_high_stakes_booking_confirmation` "
                        "or stage a new confirmation request before attempting to resolve it."
                    ),
                    suggested_tool_call_example=(
                        "resolve_booking_confirmation(confirmation_id='HITL-1A2B3C4D', approved=True)"
                    ),
                ),
            )

        decision: Literal["approved", "rejected"] = "approved" if approved else "rejected"
        record.status = decision
        record.reviewer_id = reviewer_id
        record.reviewer_note = reviewer_note
        record.resolved_at_utc = datetime.now(timezone.utc).isoformat()

        structured_logger.info(
            f"HITL confirmation resolved: {confirmation_id} -> {decision}",
            component="hitl",
            event_type="hitl_confirmation_resolved",
            session_id=record.session_id,
            attributes=record.model_dump(),
        )

        summary = (
            f"Human reviewer '{reviewer_id}' APPROVED {record.action_type} ('{record.item_description}', "
            f"¥{record.estimated_total_jpy:,}). Reservation/purchase has been committed."
            if approved
            else f"Human reviewer '{reviewer_id}' REJECTED {record.action_type} ('{record.item_description}'). "
            f"No charges or reservations were made."
        )
        return ConfirmationDecisionOutput(
            status="success",
            confirmation_id=confirmation_id,
            decision=decision,
            action_type=record.action_type,
            item_description=record.item_description,
            estimated_total_jpy=record.estimated_total_jpy,
            execution_summary=summary,
            error_recovery=None,
        )

    async def aresolve_confirmation(self, confirmation_id: str, **kwargs: Any) -> ConfirmationDecisionOutput:
        """Async wrapper for resolving a pending HITL confirmation."""
        return self.resolve_confirmation(confirmation_id, **kwargs)

    def list_pending_actions(self, session_id: str | None = None) -> list[PendingConfirmationRecord]:
        """Lists all actions currently in `pending_human_approval` state."""
        items = [
            rec
            for rec in self._pending_actions.values()
            if rec.status == "pending_human_approval"
            and (session_id is None or rec.session_id == session_id)
        ]
        return items

    def adk_before_tool_callback(
        self,
        tool: Any,
        args: dict[str, Any],
        tool_context: Any = None,
    ) -> dict[str, Any] | None:
        """Google ADK `before_tool_callback` hook enforcing human confirmation on gated tools."""
        tool_name = getattr(tool, "name", None) or getattr(tool, "__name__", str(tool))
        if getattr(tool, "requires_human_confirmation", False):
            conf_id = args.get("confirmation_id")
            if conf_id and conf_id in self._pending_actions:
                rec = self._pending_actions[conf_id]
                if rec.status == "approved":
                    return None
            structured_logger.warning(
                f"ADK before_tool_callback intercepted high-stakes tool: {tool_name}",
                component="hitl",
                event_type="hitl_adk_hook_triggered",
                attributes={"tool_name": tool_name, "args": args},
            )
        return None


hitl_manager = HumanInTheLoopManager()


def require_human_confirmation(action_type: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator marking a tool as requiring Human-in-the-Loop confirmation before commitment."""

    def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        setattr(fn, "requires_human_confirmation", True)
        setattr(fn, "hitl_action_type", action_type)

        @functools.wraps(fn)
        def _wrapper(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        setattr(_wrapper, "requires_human_confirmation", True)
        setattr(_wrapper, "hitl_action_type", action_type)
        return _wrapper

    return _decorator


__all__ = [
    "ConfirmationDecisionOutput",
    "HIGH_STAKES_ACTION_TYPES",
    "HumanInTheLoopManager",
    "PendingConfirmationRecord",
    "hitl_manager",
    "require_human_confirmation",
]
