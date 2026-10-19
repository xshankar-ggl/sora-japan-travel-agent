"""Multi-Agent Hierarchy (Coordinator + Specialist Sub-Agents) and Strategic Model Routing for Sora."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from sora_agent.guardrails import evaluate_itinerary_quality, guardrail_engine
from sora_agent.hitl import hitl_manager
from sora_agent.observability import structured_logger, trace_span
from sora_agent.schemas import StrictToolOutputModel, Field
from sora_agent.tools import (
    calculate_jr_pass_value,
    check_japan_destination_scope,
    compare_rail_vs_air,
    generate_day_by_day_itinerary_template,
    get_cultural_etiquette_and_logistics,
    get_ic_card_and_transit_guide,
    get_seasonal_travel_guide,
    request_high_stakes_booking_confirmation,
    resolve_booking_confirmation,
)

try:
    from google.adk.agents import Agent as AdkAgent  # type: ignore[import-untyped]

    HAS_GOOGLE_ADK = True
except ImportError:
    HAS_GOOGLE_ADK = False

    @dataclass
    class AdkAgent:  # type: ignore[no-redef]
        """Fallback Agent representation matching google.adk.agents.Agent interface with sub_agents and callbacks."""

        name: str
        model: str
        description: str
        instruction: str
        tools: list[Callable[..., Any]] = field(default_factory=list)
        sub_agents: list[Any] = field(default_factory=list)
        before_model_callback: Callable[..., Any] | None = None
        after_model_callback: Callable[..., Any] | None = None
        before_tool_callback: Callable[..., Any] | None = None


# ============================================================================
# 1. Strategic Model Router (Flash-Lite vs. Flash vs. Pro)
# ============================================================================

MODEL_TIER_FAST = "gemini-2.5-flash-lite"
MODEL_TIER_STANDARD = "gemini-2.5-flash"
MODEL_TIER_REASONING = "gemini-2.5-pro"


class ModelRoutingDecision(StrictToolOutputModel):
    """Structured output of the Strategic Model Router."""

    selected_model: str = Field(..., description="Selected Gemini model identifier.")
    tier: Literal["fast", "standard", "reasoning"] = Field(
        ..., description="Routing tier ('fast', 'standard', or 'reasoning')."
    )
    complexity_score: float = Field(..., ge=0.0, le=1.0, description="Normalized query complexity score.")
    routing_reason: str = Field(..., description="Explanation of why this model tier was chosen.")
    fallback_models: list[str] = Field(
        default_factory=list,
        description="Ordered fallback models if the primary model experiences quota or latency issues.",
    )


class StrategicModelRouter:
    """Routes queries dynamically across Gemini model tiers based on task complexity and cost/latency targets."""

    def __init__(
        self,
        fast_model: str = MODEL_TIER_FAST,
        standard_model: str = MODEL_TIER_STANDARD,
        reasoning_model: str = MODEL_TIER_REASONING,
    ) -> None:
        self.fast_model = fast_model
        self.standard_model = standard_model
        self.reasoning_model = reasoning_model

    @trace_span("sora.router.route_query", component="router")
    def route_query(
        self,
        prompt: str,
        *,
        task_type: str | None = None,
        detected_city_count: int = 0,
        requested_days: int = 0,
    ) -> ModelRoutingDecision:
        """Selects the optimal Gemini model tier for a given prompt and task category."""
        lowered = prompt.lower()

        # Explicit fast-tier tasks: scope checks, compaction, single-topic etiquette/IC lookups
        if task_type in {"scope_check", "compaction", "etiquette_lookup", "ic_guide"}:
            return ModelRoutingDecision(
                selected_model=self.fast_model,
                tier="fast",
                complexity_score=0.2,
                routing_reason=f"Task '{task_type}' is a bounded low-latency lookup suited for {self.fast_model}.",
                fallback_models=[self.standard_model],
            )

        # Compute complexity signals from prompt
        score = 0.25
        if detected_city_count >= 3:
            score += 0.35
        elif detected_city_count == 2:
            score += 0.20

        if requested_days >= 7:
            score += 0.25
        elif requested_days >= 4:
            score += 0.15

        complex_keywords = (
            "itinerary", "day-by-day", "day by day", "compare", "optimize",
            "jr pass", "regional pass", "luggage", "takkyubin", "foliage", "cherry blossom",
        )
        matched_kw = sum(1 for kw in complex_keywords if kw in lowered)
        score += min(0.30, matched_kw * 0.08)
        score = round(min(1.0, score), 2)

        if score >= 0.65 or (detected_city_count >= 3 and "plan" in lowered):
            decision = ModelRoutingDecision(
                selected_model=self.reasoning_model,
                tier="reasoning",
                complexity_score=score,
                routing_reason=(
                    f"High-complexity multi-city itinerary synthesis (cities={detected_city_count}, "
                    f"days={requested_days}, score={score}) routed to deep-reasoning model {self.reasoning_model}."
                ),
                fallback_models=[self.standard_model, self.fast_model],
            )
        elif score >= 0.35 or any(w in lowered for w in ("jr pass", "fly", "flight", "shinkansen", "plan")):
            decision = ModelRoutingDecision(
                selected_model=self.standard_model,
                tier="standard",
                complexity_score=score,
                routing_reason=(
                    f"Moderate-complexity tool-calling query (score={score}) routed to balanced model {self.standard_model}."
                ),
                fallback_models=[self.fast_model, self.reasoning_model],
            )
        else:
            decision = ModelRoutingDecision(
                selected_model=self.fast_model,
                tier="fast",
                complexity_score=score,
                routing_reason=f"Single-domain quick lookup (score={score}) routed to fast tier {self.fast_model}.",
                fallback_models=[self.standard_model],
            )

        structured_logger.info(
            f"Strategic router selected {decision.selected_model} (tier={decision.tier}, score={decision.complexity_score})",
            component="router",
            event_type="model_routed",
            attributes=decision.model_dump(),
        )
        return decision


model_router = StrategicModelRouter()


# ============================================================================
# 2. Multi-Agent Specialist Sub-Agents Definition (Google ADK Hierarchy)
# ============================================================================


def _instantiate_adk_agent(
    *,
    name: str,
    model: str,
    description: str,
    instruction: str,
    tools: list[Callable[..., Any]],
    sub_agents: list[Any] | None = None,
    before_model_callback: Callable[..., Any] | None = None,
    after_model_callback: Callable[..., Any] | None = None,
    before_tool_callback: Callable[..., Any] | None = None,
) -> AdkAgent:
    """Safely constructs a Google ADK Agent with sub_agents and lifecycle callbacks."""
    kwargs: dict[str, Any] = {
        "name": name,
        "model": model,
        "description": description,
        "instruction": instruction,
        "tools": tools,
    }
    if sub_agents:
        kwargs["sub_agents"] = sub_agents
    if before_model_callback is not None:
        kwargs["before_model_callback"] = before_model_callback
    if after_model_callback is not None:
        kwargs["after_model_callback"] = after_model_callback
    if before_tool_callback is not None:
        kwargs["before_tool_callback"] = before_tool_callback

    try:
        return AdkAgent(**kwargs)
    except TypeError:
        # If an older version of google-adk Agent accepts a subset of kwargs, attach attributes post-init
        agent = AdkAgent(
            name=name,
            model=model,
            description=description,
            instruction=instruction,
            tools=tools,
        )
        if sub_agents is not None:
            setattr(agent, "sub_agents", sub_agents)
        if before_model_callback is not None:
            setattr(agent, "before_model_callback", before_model_callback)
        if after_model_callback is not None:
            setattr(agent, "after_model_callback", after_model_callback)
        if before_tool_callback is not None:
            setattr(agent, "before_tool_callback", before_tool_callback)
        return agent


def create_specialist_sub_agents() -> dict[str, AdkAgent]:
    """Creates the 4 specialized sub-agents for Sora's multi-agent architecture."""
    rail_and_transit_agent = _instantiate_adk_agent(
        name="rail_and_transit_specialist",
        model=MODEL_TIER_STANDARD,
        description=(
            "Specialist sub-agent for post-October-2023 JR Pass cost-benefit calculations, Regional JR Passes "
            "(Kansai-Hiroshima, Hokuriku Arch), Shinkansen vs. domestic air door-to-door comparisons, and "
            "Suica/PASMO/ICOCA + SmartEX transit mechanics."
        ),
        instruction=(
            "You are Sora's Rail & Transit Specialist Sub-Agent. Always invoke `calculate_jr_pass_value`, "
            "`compare_rail_vs_air`, and `get_ic_card_and_transit_guide`. If any tool returns `status='error'`, "
            "follow its `error_recovery.llm_recovery_instruction` to self-correct parameters."
        ),
        tools=[calculate_jr_pass_value, compare_rail_vs_air, get_ic_card_and_transit_guide],
        before_tool_callback=hitl_manager.adk_before_tool_callback,
    )

    cultural_and_seasonal_agent = _instantiate_adk_agent(
        name="cultural_and_seasonal_specialist",
        model=MODEL_TIER_FAST,
        description=(
            "Specialist sub-agent for Japan's 12-month seasonal calendar (sakura, koyo, tsuyu, Golden Week, Obon), "
            "ryokan & onsen etiquette (including tattoo-friendly onsen & kashikiri), konbini culture, and "
            "Yamato Takkyubin luggage forwarding."
        ),
        instruction=(
            "You are Sora's Cultural Etiquette & Seasonal Specialist Sub-Agent. Use `get_seasonal_travel_guide` "
            "and `get_cultural_etiquette_and_logistics` to provide accurate Japan cultural and seasonal advice."
        ),
        tools=[get_seasonal_travel_guide, get_cultural_etiquette_and_logistics],
    )

    itinerary_architect_agent = _instantiate_adk_agent(
        name="itinerary_architect_specialist",
        model=MODEL_TIER_REASONING,
        description=(
            "Specialist sub-agent that synthesizes geographically clustered day-by-day Japan itineraries "
            "and stages high-stakes bookings behind Human-in-the-Loop confirmation gates."
        ),
        instruction=(
            "You are Sora's Day-by-Day Itinerary Architect Sub-Agent. Use `generate_day_by_day_itinerary_template` "
            "to group sights into walkable neighborhood clusters without city zigzagging. For any financial or "
            "non-refundable reservation commitment, ALWAYS invoke `request_high_stakes_booking_confirmation` "
            "and wait for human approval."
        ),
        tools=[
            generate_day_by_day_itinerary_template,
            request_high_stakes_booking_confirmation,
            resolve_booking_confirmation,
        ],
        before_tool_callback=hitl_manager.adk_before_tool_callback,
    )

    safety_and_critic_agent = _instantiate_adk_agent(
        name="safety_and_critic_specialist",
        model=MODEL_TIER_FAST,
        description=(
            "Guardrail and self-evaluation critic sub-agent that enforces strict Japan-only scope and verifies "
            "itinerary accuracy against Sora's 5-point rubric."
        ),
        instruction=(
            "You are Sora's Safety & Self-Evaluation Critic Sub-Agent. Use `check_japan_destination_scope` "
            "to block out-of-scope destinations and `evaluate_itinerary_quality` to audit draft itineraries."
        ),
        tools=[check_japan_destination_scope, evaluate_itinerary_quality],
    )

    return {
        "rail_and_transit_specialist": rail_and_transit_agent,
        "cultural_and_seasonal_specialist": cultural_and_seasonal_agent,
        "itinerary_architect_specialist": itinerary_architect_agent,
        "safety_and_critic_specialist": safety_and_critic_agent,
    }


class MultiAgentExecutionResult(StrictToolOutputModel):
    """Structured result from the Multi-Agent Coordinator workflow."""

    response_text: str = Field(..., description="Final synthesized and self-evaluated markdown response.")
    routing_decision: ModelRoutingDecision = Field(..., description="Strategic model routing decision.")
    sub_agents_invoked: list[str] = Field(default_factory=list, description="Specialist sub-agents dispatched.")
    tools_invoked: list[str] = Field(default_factory=list, description="Tools executed across sub-agents.")
    self_eval_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Critic self-evaluation score.")
    hitl_confirmation_id: str | None = Field(
        default=None, description="Populated if execution paused for a Human-in-the-Loop booking confirmation."
    )


__all__ = [
    "AdkAgent",
    "HAS_GOOGLE_ADK",
    "MODEL_TIER_FAST",
    "MODEL_TIER_REASONING",
    "MODEL_TIER_STANDARD",
    "ModelRoutingDecision",
    "MultiAgentExecutionResult",
    "StrategicModelRouter",
    "_instantiate_adk_agent",
    "create_specialist_sub_agents",
    "model_router",
]
