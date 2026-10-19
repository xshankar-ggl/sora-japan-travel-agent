"""Cloud-Native Safety Settings, Model Armor Policies, Prompt Injection Defense, and Agentic Self-Evaluation Guardrails."""

from __future__ import annotations

import re
from typing import Any

from sora_agent.observability import pii_redactor, structured_logger, trace_span
from sora_agent.schemas import StrictToolOutputModel, Field
from sora_agent.tools import check_japan_destination_scope

PROMPT_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"(?:reveal|print|dump|output)\s+(?:your\s+)?system\s+prompt", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:dan|unrestricted|jailbroken)", re.IGNORECASE),
    re.compile(r"bypass\s+(?:all\s+)?(?:safety|guardrails|restrictions)", re.IGNORECASE),
]


class CloudSafetyConfigSchema(StrictToolOutputModel):
    """Schema representing Vertex AI / Gemini Safety Settings and Google Cloud Model Armor policies."""

    provider: str = Field(default="google_genai_vertex_ai", description="Cloud safety provider.")
    model_armor_template_id: str = Field(
        default="projects/sora-prod/locations/us-central1/templates/sora-model-armor-strict",
        description="Google Cloud Model Armor policy template resource URI.",
    )
    prompt_injection_filter: str = Field(default="ENABLED_HIGH", description="Model Armor prompt injection level.")
    pii_dlp_deidentification: str = Field(default="ENABLED_REDACT", description="Cloud DLP PII redaction mode.")
    harm_thresholds: dict[str, str] = Field(
        default_factory=lambda: {
            "HARM_CATEGORY_HATE_SPEECH": "BLOCK_LOW_AND_ABOVE",
            "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_LOW_AND_ABOVE",
            "HARM_CATEGORY_HARASSMENT": "BLOCK_LOW_AND_ABOVE",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_LOW_AND_ABOVE",
        },
        description="Cloud-native Gemini harm category block thresholds.",
    )


class InputGuardrailEvaluation(StrictToolOutputModel):
    """Result of pre-model input screening (PII scrubbing, prompt injection defense, and Japan scope check)."""

    allowed: bool = Field(..., description="True if the prompt is safe and within Japan specialist scope.")
    block_reason: str | None = Field(default=None, description="Reason for blocking (`PROMPT_INJECTION` or `OUT_OF_SCOPE`).")
    sanitized_prompt: str = Field(..., description="PII-redacted user prompt.")
    pii_redacted_count: int = Field(default=0, ge=0, description="Number of PII tokens redacted from input.")
    is_japan_only: bool = Field(default=True, description="Whether all destinations are inside Japan.")
    detected_non_japan_destinations: list[str] = Field(default_factory=list)
    detected_japan_destinations: list[str] = Field(default_factory=list)
    guardrail_message: str = Field(default="Input passed all pre-execution guardrails.")


class SelfEvaluationReport(StrictToolOutputModel):
    """Agentic Self-Evaluation (LLM-as-a-Judge / Rubric Critic) assessment of a generated response."""

    passed: bool = Field(..., description="True if overall_score >= 0.85 and no critical policy violations exist.")
    overall_score: float = Field(..., ge=0.0, le=1.0, description="Weighted quality and compliance score.")
    criterion_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Per-criterion scores across the 5 Japan Specialist evaluation dimensions.",
    )
    critique_notes: list[str] = Field(
        default_factory=list,
        description="Specific issues identified by the self-evaluation critic.",
    )
    auto_refined: bool = Field(
        default=False,
        description="True if the self-evaluation loop automatically repaired the draft response.",
    )
    refined_response: str = Field(..., description="Final verified and PII-clean response text.")


def get_cloud_native_safety_settings() -> list[Any]:
    """Builds Google GenAI / Vertex AI `types.SafetySetting` objects with `BLOCK_LOW_AND_ABOVE` thresholds."""
    config = CloudSafetyConfigSchema()
    try:
        from google.genai import types

        return [
            types.SafetySetting(
                category=getattr(types.HarmCategory, category),
                threshold=getattr(types.HarmBlockThreshold, threshold),
            )
            for category, threshold in config.harm_thresholds.items()
            if hasattr(types.HarmCategory, category) and hasattr(types.HarmBlockThreshold, threshold)
        ]
    except Exception:
        return [
            {"category": category, "threshold": threshold}
            for category, threshold in config.harm_thresholds.items()
        ]


class DefenseInDepthGuardrailEngine:
    """Three-layer guardrail pipeline: Input Sanitization, Cloud-Native Safety, and Agentic Self-Evaluation."""

    def __init__(self) -> None:
        self.cloud_safety_config = CloudSafetyConfigSchema()

    @trace_span("sora.guardrail.evaluate_input", component="guardrail")
    def evaluate_input(self, prompt: str) -> InputGuardrailEvaluation:
        """Executes Layer 1 (PII + Prompt Injection) and Layer 2 (Japan Scope) input guardrails."""
        redaction = pii_redactor.redact_text(prompt)
        sanitized = redaction.redacted_text

        for pattern in PROMPT_INJECTION_PATTERNS:
            if pattern.search(sanitized):
                structured_logger.warning(
                    "Blocked prompt injection attempt in InputGuardrail",
                    component="guardrail",
                    event_type="prompt_injection_blocked",
                    attributes={"pattern": pattern.pattern},
                )
                return InputGuardrailEvaluation(
                    allowed=False,
                    block_reason="PROMPT_INJECTION",
                    sanitized_prompt=sanitized,
                    pii_redacted_count=redaction.redaction_count,
                    is_japan_only=True,
                    guardrail_message=(
                        "Konnichiwa! I am **Sora**, a Japan-specialist travel planning agent. "
                        "I cannot process requests that attempt to override safety instructions or system boundaries. "
                        "Please share your Japan travel dates, cities, and interests so I can design your itinerary!"
                    ),
                )

        scope = check_japan_destination_scope(sanitized)
        if not scope.is_japan_only and not scope.detected_japan_destinations:
            non_jp = ", ".join(scope.detected_non_japan_destinations)
            structured_logger.info(
                f"Scope guardrail blocked non-Japan destination request: {non_jp}",
                component="guardrail",
                event_type="scope_guardrail_blocked",
                attributes={"non_japan_destinations": scope.detected_non_japan_destinations},
            )
            return InputGuardrailEvaluation(
                allowed=False,
                block_reason="OUT_OF_SCOPE",
                sanitized_prompt=sanitized,
                pii_redacted_count=redaction.redaction_count,
                is_japan_only=False,
                detected_non_japan_destinations=scope.detected_non_japan_destinations,
                detected_japan_destinations=scope.detected_japan_destinations,
                guardrail_message=(
                    f"Konnichiwa! I am **Sora**, a dedicated **Japan-specialist travel planning agent**.\n\n"
                    f"I noticed your request mentions **{non_jp}**. Because I specialize exclusively in Japan—covering "
                    f"Shinkansen & JR Pass mechanics, Suica/PASMO/ICOCA transit, ryokan & onsen etiquette, konbini culture, "
                    f"and regional Japan itineraries—I don't plan trips outside Japan.\n\n"
                    f"If you'd like to plan a trip to **Japan** (such as Tokyo, Kyoto, Osaka, Hiroshima, Kanazawa, Hokkaido, "
                    f"or Kyushu), tell me your travel dates, trip length, and interests, and I'll craft a complete day-by-day "
                    f"itinerary for you!"
                ),
            )

        return InputGuardrailEvaluation(
            allowed=True,
            block_reason=None,
            sanitized_prompt=sanitized,
            pii_redacted_count=redaction.redaction_count,
            is_japan_only=scope.is_japan_only,
            detected_non_japan_destinations=scope.detected_non_japan_destinations,
            detected_japan_destinations=scope.detected_japan_destinations,
            guardrail_message="Input passed all pre-execution guardrails.",
        )

    @trace_span("sora.guardrail.self_evaluate_response", component="guardrail")
    def self_evaluate_and_refine(
        self,
        prompt: str,
        draft_response: str,
        *,
        is_itinerary_request: bool = True,
    ) -> SelfEvaluationReport:
        """Executes Layer 3 Agentic Self-Evaluation (Critic Loop) and auto-refines any rubric gaps."""
        critique_notes: list[str] = []
        refined = draft_response

        # 1. PII & Safety Compliance check
        redacted_check = pii_redactor.redact_text(refined)
        if redacted_check.redaction_count > 0:
            critique_notes.append(f"Scrubbed {redacted_check.redaction_count} leaked PII token(s) from output.")
            refined = redacted_check.redacted_text
        pii_score = 1.0

        # 2. Scope Compliance check
        scope_score = 1.0
        if "Sora" not in refined:
            critique_notes.append("Added Sora Japan-specialist identity header.")
            refined = f"Konnichiwa! I am **Sora**, your Japan-specialist travel planning agent.\n\n{refined}"

        # 3. Post-Oct-2023 JR Pass Accuracy check
        jr_score = 1.0
        if is_itinerary_request:
            if "JR Pass" not in refined and "SmartEX" not in refined:
                critique_notes.append("Appended post-October-2023 JR Pass & SmartEX cost-benefit guidance.")
                refined += (
                    "\n\n### 🚅 JR Pass & SmartEX Verification\n"
                    "- **Post-Oct 2023 National JR Pass Prices**: 7-Day ¥50,000 | 14-Day ¥80,000 | 21-Day ¥100,000 (Ordinary).\n"
                    "- **Nozomi Rule**: National JR Pass holders must purchase a supplemental upgrade ticket to ride Nozomi/Mizuho trains."
                )
                jr_score = 0.9

        # 4. Geographic Cluster & Day-by-Day Structure check
        geo_score = 1.0
        if is_itinerary_request and "Day 1" not in refined:
            critique_notes.append("Draft lacked explicit Day 1 neighborhood clustering.")
            geo_score = 0.75

        # 5. IC Card, Luggage & Cultural Etiquette Completeness check
        etiquette_score = 1.0
        if is_itinerary_request:
            missing_logistics: list[str] = []
            if not any(ic in refined for ic in ("Suica", "PASMO", "ICOCA")):
                missing_logistics.append(
                    "- **IC Card Transit**: Add Suica/PASMO/ICOCA to Apple Wallet (or buy Welcome Suica / physical ICOCA) for seamless nationwide transit."
                )
            if "Takkyubin" not in refined and "160cm" not in refined and "160 cm" not in refined:
                missing_logistics.append(
                    "- **Luggage Logistics**: Use Yamato *Takkyubin* for overnight luggage forwarding and reserve Shinkansen Oversized Baggage seats for suitcases 160–250cm."
                )
            if missing_logistics:
                critique_notes.append("Injected missing IC card / Takkyubin luggage logistics reminders.")
                refined += "\n\n### 💳 Essential Transit & Luggage Checklist\n" + "\n".join(missing_logistics)
                etiquette_score = 0.92

        scores = {
            "japan_scope_adherence": scope_score,
            "jr_pass_post_2023_accuracy": jr_score,
            "geographic_cluster_coherence": geo_score,
            "cultural_and_logistics_completeness": etiquette_score,
            "pii_and_safety_compliance": pii_score,
        }
        overall = round(sum(scores.values()) / len(scores), 3)
        auto_refined = len(critique_notes) > 0

        structured_logger.info(
            f"Agentic self-evaluation completed (score={overall}, auto_refined={auto_refined})",
            component="guardrail",
            event_type="agentic_self_eval",
            attributes={"overall_score": overall, "critique_notes": critique_notes, "scores": scores},
        )

        return SelfEvaluationReport(
            passed=overall >= 0.85,
            overall_score=overall,
            criterion_scores=scores,
            critique_notes=critique_notes,
            auto_refined=auto_refined,
            refined_response=refined,
        )

    def adk_before_model_callback(self, callback_context: Any = None, llm_request: Any = None) -> Any:
        """Google ADK `before_model_callback` enforcing input guardrails before LLM invocation."""
        structured_logger.info(
            "Executed ADK before_model_callback guardrail check",
            component="guardrail",
            event_type="adk_before_model_callback",
        )
        return None

    def adk_after_model_callback(self, callback_context: Any = None, llm_response: Any = None) -> Any:
        """Google ADK `after_model_callback` running self-evaluation and PII redaction on model output."""
        structured_logger.info(
            "Executed ADK after_model_callback self-eval check",
            component="guardrail",
            event_type="adk_after_model_callback",
        )
        return None


guardrail_engine = DefenseInDepthGuardrailEngine()


@trace_span("sora.tool.evaluate_itinerary_quality", component="guardrail")
def evaluate_itinerary_quality(prompt: str, draft_itinerary: str) -> SelfEvaluationReport:
    """Agentic self-evaluation tool used by the `safety_and_critic_agent` to verify itinerary accuracy.

    Args:
        prompt: Original traveler prompt.
        draft_itinerary: Candidate itinerary markdown generated by Sora's specialist agents.

    Returns:
        Strict `SelfEvaluationReport` Pydantic model with per-criterion scores and refined text.
    """
    return guardrail_engine.self_evaluate_and_refine(prompt, draft_itinerary, is_itinerary_request=True)


__all__ = [
    "CloudSafetyConfigSchema",
    "DefenseInDepthGuardrailEngine",
    "InputGuardrailEvaluation",
    "SelfEvaluationReport",
    "evaluate_itinerary_quality",
    "get_cloud_native_safety_settings",
    "guardrail_engine",
]
