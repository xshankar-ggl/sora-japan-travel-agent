"""Google ADK Multi-Agent Coordinator, Async Execution Engine, Strategic Router, and Guardrail Pipeline for Sora."""

from __future__ import annotations

import asyncio
import os
import re
import time
from typing import Any

from sora_agent.guardrails import (
    get_cloud_native_safety_settings,
    guardrail_engine,
)
from sora_agent.hitl import hitl_manager
from sora_agent.memory import (
    PersistentSessionMemoryManager,
    session_memory_manager,
)
from sora_agent.observability import (
    intent_tracker,
    structured_logger,
    trace_span,
    tracer,
)
from sora_agent.orchestration import (
    AdkAgent,
    MODEL_TIER_STANDARD,
    _instantiate_adk_agent,
    create_specialist_sub_agents,
    model_router,
)
from sora_agent.prompt import SORA_ROLE_HEADER, SORA_SYSTEM_PROMPT
from sora_agent.secrets import secret_manager_service
from sora_agent.tools import (
    ALL_SORA_TOOLS,
    check_japan_destination_scope,
    compare_rail_vs_air,
    generate_day_by_day_itinerary_template,
    get_cultural_etiquette_and_logistics,
    get_ic_card_and_transit_guide,
    request_high_stakes_booking_confirmation,
)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

DEFAULT_MODEL = os.getenv("SORA_MODEL", MODEL_TIER_STANDARD)


def create_sora_agent(model: str = DEFAULT_MODEL) -> AdkAgent:
    """Creates and returns the hierarchical Sora Google ADK `root_agent` Coordinator with 4 specialist sub-agents."""
    sub_agents_map = create_specialist_sub_agents()
    return _instantiate_adk_agent(
        name="sora_japan_travel_agent",
        model=model,
        description=(
            "Sora: A multi-agent Japan-specialist travel planning coordinator that orchestrates "
            "specialist sub-agents for post-2023 JR Pass math, IC card guidance, ryokan etiquette, "
            "konbini culture, seasonal advice, rail vs. domestic air comparisons, and HITL bookings."
        ),
        instruction=SORA_SYSTEM_PROMPT,
        tools=ALL_SORA_TOOLS,
        sub_agents=list(sub_agents_map.values()),
        before_model_callback=guardrail_engine.adk_before_model_callback,
        after_model_callback=guardrail_engine.adk_after_model_callback,
        before_tool_callback=hitl_manager.adk_before_tool_callback,
    )


# Standard Google ADK entrypoint symbol (`adk run sora_agent` / `adk web`)
root_agent = create_sora_agent()


def _extract_cities_from_prompt(prompt: str) -> list[str]:
    known_cities = [
        "tokyo", "hakone", "kawaguchiko", "nikko", "kamakura", "kanazawa",
        "takayama", "shirakawa-go", "kyoto", "nara", "osaka", "himeji",
        "kobe", "hiroshima", "miyajima", "fukuoka", "hakata", "sapporo",
        "hakodate", "sendai", "okinawa",
    ]
    lowered = prompt.lower()
    found: list[tuple[int, str]] = []
    for city in known_cities:
        match = re.search(rf"\b{re.escape(city)}\b", lowered)
        if match:
            found.append((match.start(), city))
    found.sort(key=lambda item: item[0])
    return [city for _, city in found]


def _extract_days_from_prompt(prompt: str) -> int:
    match = re.search(r"\b(\d{1,2})\s*(?:-|\s)?\s*(?:day|days|night|nights)\b", prompt.lower())
    if match:
        return max(1, min(21, int(match.group(1))))
    if "week" in prompt.lower():
        if "two week" in prompt.lower() or "2 week" in prompt.lower():
            return 14
        return 7
    return 7


def _extract_month_from_prompt(prompt: str) -> int:
    months = {
        "january": 1, "jan": 1,
        "february": 2, "feb": 2,
        "march": 3, "mar": 3,
        "april": 4, "apr": 4,
        "may": 5,
        "june": 6, "jun": 6,
        "july": 7, "jul": 7,
        "august": 8, "aug": 8,
        "september": 9, "sep": 9, "sept": 9,
        "october": 10, "oct": 10,
        "november": 11, "nov": 11,
        "december": 12, "dec": 12,
    }
    lowered = prompt.lower()
    for name, num in months.items():
        if re.search(rf"\b{name}\b", lowered):
            return num
    if "sakura" in lowered or "cherry blossom" in lowered or "spring" in lowered:
        return 4
    if "koyo" in lowered or "autumn" in lowered or "fall" in lowered or "foliage" in lowered:
        return 11
    if "winter" in lowered or "snow" in lowered or "ski" in lowered:
        return 1
    if "summer" in lowered or "festival" in lowered:
        return 7
    return 4


@trace_span("sora.agent.render_tool_assisted_response", component="agent")
def render_tool_assisted_response(
    prompt: str,
    *,
    memory_context_summary: str = "",
) -> str:
    """Synthesizes a comprehensive Japan-specialist response by coordinating Sora's specialist tools."""
    input_eval = guardrail_engine.evaluate_input(prompt)
    if not input_eval.allowed:
        return input_eval.guardrail_message

    sanitized_prompt = input_eval.sanitized_prompt
    lowered = sanitized_prompt.lower()

    # Check if the traveler is requesting a high-stakes booking commitment (HITL Gate)
    if any(
        kw in lowered
        for kw in ("book now", "confirm booking", "purchase jr pass", "reserve ryokan", "commit reservation")
    ):
        action_type = "PURCHASE_JR_PASS" if "jr pass" in lowered else "BOOK_RYOKAN_KAISEKI"
        cost_jpy = 50000 if action_type == "PURCHASE_JR_PASS" else 68000
        hitl_res = request_high_stakes_booking_confirmation(
            action_type=action_type,
            item_description=f"Traveler requested commitment: {sanitized_prompt[:120]}",
            estimated_total_jpy=cost_jpy,
            traveler_count=1,
            non_refundable=True,
        )
        return (
            f"# 🛑 Human-in-the-Loop Confirmation Required (`{hitl_res.confirmation_id}`)\n\n"
            f"Konnichiwa! I am **Sora**, your Japan-specialist travel planning agent.\n\n"
            f"- **Action Staged**: `{hitl_res.action_type}`\n"
            f"- **Item**: {hitl_res.item_description}\n"
            f"- **Estimated Cost**: **¥{hitl_res.estimated_total_jpy:,}**\n"
            f"- **Policy Warning**: {hitl_res.cancellation_policy_warning}\n\n"
            f"> **Next Step**: {hitl_res.approval_instructions}"
        )

    scope = check_japan_destination_scope(sanitized_prompt)
    detected_japan_cities = _extract_cities_from_prompt(sanitized_prompt)

    days = _extract_days_from_prompt(sanitized_prompt)
    month = _extract_month_from_prompt(sanitized_prompt)
    cities = detected_japan_cities or (["tokyo", "hakone", "kyoto", "osaka"] if days >= 7 else ["tokyo", "kyoto"])

    template = generate_day_by_day_itinerary_template(days=days, cities=cities, month=month)
    ic_guide = get_ic_card_and_transit_guide(arrival_airport="HND", regions=template["cities_in_order"])
    jr = template["jr_pass_recommendation"]
    season = template["seasonal_context"]

    sections: list[str] = [
        f"# 🇯🇵 Sora's {template['trip_days']}-Day Japan Itinerary ({' → '.join(template['cities_in_order'])})",
        "",
        "Konnichiwa! I'm **Sora**, your Japan-specialist travel planning agent. Below is your custom day-by-day "
        "itinerary with post-2023 JR Pass math, IC card setup, luggage forwarding checkpoints, konbini picks, and "
        "cultural etiquette built right in.",
    ]

    if memory_context_summary:
        sections.extend(
            [
                "",
                "> **Session Memory Active**: Personalized using your stored session profile and semantic travel preferences.",
            ]
        )

    if not scope["is_japan_only"]:
        non_jp = ", ".join(scope["detected_non_japan_destinations"])
        sections.extend(
            [
                "",
                f"> **Scope Note**: I saw you also mentioned **{non_jp}**. As a Japan-only specialist, I have focused "
                "this plan exclusively on the **Japan** portion of your journey.",
            ]
        )

    # Seasonal section
    sections.extend(
        [
            "",
            f"## 🌸 Seasonal Context: Month {season['month']} — {season['season']}",
            f"- **Weather**: {season['weather_summary']}",
            f"- **Crowd & Holiday Alert**: {season['crowd_alerts']}",
            f"- **Seasonal Highlights**: {'; '.join(season['highlights'][:3])}",
            f"- **Seasonal Foods (*Shun*)**: {', '.join(season['seasonal_foods'])}",
            f"- **Packing Essentials**: {', '.join(season['packing_tips'])}",
        ]
    )

    # JR Pass & Transit Mechanics section
    sections.extend(
        [
            "",
            "## 🚅 Shinkansen & JR Pass Cost-Benefit Analysis",
            f"- **Verdict (`{jr['verdict']}`)**: {jr['summary']}",
            f"- **Pass Evaluated**: {jr['pass_evaluated']} — **¥{jr['national_pass_cost_jpy']:,}**",
            f"- **Point-to-Point Tickets Total**: **¥{jr['individual_tickets_total_jpy']:,}**",
        ]
    )
    if jr["itemized_legs"]:
        sections.append("- **Itemized Intercity Legs**:")
        for leg in jr["itemized_legs"]:
            sections.append(
                f"  - `{leg['leg']}`: **¥{leg['fare_jpy']:,}** (~{leg['duration_mins']} mins via *{leg['train_name']}*) — {leg['scenic_tip']}"
            )
    if jr["regional_pass_recommendations"]:
        for reg in jr["regional_pass_recommendations"]:
            sections.append(
                f"- 💡 **Regional Pass Pro-Tip ({reg['pass_name']} — ¥{reg['price_jpy']:,} / {reg['duration_days']} days)**: {reg['why_it_wins']}"
            )
    sections.append(f"- ⚠️ **Nozomi / Mizuho Rule**: {jr['nozomi_supplement_warning']}")

    # Check if any long corridor merits a Rail vs Air callout
    for candidate in ("sapporo", "fukuoka", "hiroshima", "okinawa"):
        if candidate in [c.lower() for c in template["cities_in_order"]]:
            rva = compare_rail_vs_air("tokyo", candidate)
            sections.extend(
                [
                    "",
                    f"## ✈️ vs. 🚅 Regional Rail vs. Domestic Air: {rva['corridor']}",
                    f"- **Recommendation**: **{rva['headline']}**",
                    f"- **Rail**: {rva['rail_details']['mode']} (~{rva['rail_details']['door_to_door_mins']} mins door-to-door, {rva['rail_details']['cost_jpy_range']})",
                    f"- **Domestic Air**: {rva['air_details']['mode']} (~{rva['air_details']['door_to_door_mins']} mins door-to-door, {rva['air_details']['cost_jpy_range']})",
                ]
            )

    # IC Card section
    sections.extend(
        [
            "",
            "## 💳 IC Cards (Suica / PASMO / ICOCA) & SmartEX Setup",
            f"- **Setup**: {ic_guide['primary_ic_card_recommendation']}",
            f"- **Interoperability**: {ic_guide['nationwide_interoperability']}",
            f"- **Shinkansen Integration**: {ic_guide['smartex_shinkansen_tip']}",
        ]
    )

    # Day-by-Day Itinerary section
    sections.extend(["", "## 🗓️ Day-by-Day Japan Itinerary"])
    for day in template["day_by_day_plan"]:
        sections.extend(
            [
                "",
                f"### Day {day['day']}: {day['base_city']} — *{day['theme']}*",
            ]
        )
        if day["intercity_transition"]:
            sections.append(f"- 🚅 **Intercity Transit**: {day['intercity_transition']}")
        if day["luggage_strategy"]:
            sections.append(f"- 🧳 **Luggage Strategy (Takkyubin)**: {day['luggage_strategy']}")
        sections.extend(
            [
                f"- 🌅 **Morning**: {day['morning']}",
                f"- ☀️ **Afternoon**: {day['afternoon']}",
                f"- 🏮 **Evening**: {day['evening']}",
                f"- 🚇 **Local Transit Tip**: {day['local_transit_tip']}",
                f"- 🙇 **Etiquette & Konbini Tip**: {day['cultural_etiquette_tip']}",
            ]
        )

    # Cultural & Konbini Quick-Reference
    etiquette = get_cultural_etiquette_and_logistics("all")
    sections.extend(
        [
            "",
            "## ♨️ Ryokan, Onsen & Konbini Essentials",
            f"- **Ryokan & Onsen**: {etiquette['ryokan_onsen']['golden_rules'][0]} {etiquette['ryokan_onsen']['golden_rules'][3]}",
            f"- **Tattoo Guidance**: {etiquette['ryokan_onsen']['golden_rules'][6]}",
            f"- **Konbini Must-Tries**: {etiquette['konbini']['golden_rules'][1]}",
            f"- **ATMs & Cash**: {etiquette['konbini']['golden_rules'][4]}",
        ]
    )

    draft_text = "\n".join(sections)
    self_eval = guardrail_engine.self_evaluate_and_refine(
        sanitized_prompt,
        draft_text,
        is_itinerary_request=True,
    )
    return self_eval.refined_response


async def arun_sora_query(
    prompt: str,
    *,
    session_id: str = "default",
    model: str | None = None,
    prefer_live_api: bool = True,
    memory_manager: PersistentSessionMemoryManager | None = None,
) -> str:
    """Asynchronously executes a traveler query with multi-agent routing, persistent memory, guardrails, and tracing."""
    start_perf = time.perf_counter()
    mem = memory_manager or session_memory_manager

    with tracer.start_as_current_span(
        "sora.request.arun_sora_query",
        component="orchestrator",
        attributes={"session_id": session_id, "prefer_live_api": prefer_live_api},
    ) as root_span:
        # 1. Input Guardrail & PII Scrubbing
        input_eval = guardrail_engine.evaluate_input(prompt)
        sanitized_prompt = input_eval.sanitized_prompt
        detected_cities = _extract_cities_from_prompt(sanitized_prompt)
        extracted_days = _extract_days_from_prompt(sanitized_prompt)
        extracted_month = _extract_month_from_prompt(sanitized_prompt)

        intent = intent_tracker.classify_intent(
            sanitized_prompt,
            session_id=session_id,
            detected_japan_cities=detected_cities,
            is_japan_only=input_eval.is_japan_only,
            extracted_days=extracted_days,
            extracted_month=extracted_month,
        )

        # 2. Strategic Model Routing
        routing = model_router.route_query(
            sanitized_prompt,
            detected_city_count=len(detected_cities),
            requested_days=extracted_days,
        )
        selected_model = model or routing.selected_model
        root_span.set_attribute("sora.selected_model", selected_model)
        root_span.set_attribute("sora.intent_category", intent.intent_category)

        # 3. Async Memory Context Retrieval + User Turn Persistence
        context_window = await mem.abuild_context_window(session_id=session_id, current_query=sanitized_prompt)
        await mem.aadd_turn(session_id=session_id, role="user", content=sanitized_prompt)

        if not input_eval.allowed:
            latency_ms = (time.perf_counter() - start_perf) * 1000.0
            outcome_status = (
                "GUARDRAIL_BLOCKED_SAFETY"
                if input_eval.block_reason == "PROMPT_INJECTION"
                else "GUARDRAIL_BLOCKED_SCOPE"
            )
            await mem.aadd_turn(session_id=session_id, role="assistant", content=input_eval.guardrail_message)
            intent_tracker.record_outcome(
                intent,
                actual_tools_invoked=["check_japan_destination_scope"],
                sub_agents_dispatched=["safety_and_critic_specialist"],
                selected_model=selected_model,
                outcome_status=outcome_status,
                self_eval_score=1.0,
                latency_ms=latency_ms,
            )
            return input_eval.guardrail_message

        # 4. Resolve API Key from Google Cloud Secret Manager (with local fallback)
        api_key, secret_meta = secret_manager_service.get_gemini_api_key()
        root_span.set_attribute("sora.secret_source", secret_meta.source)

        response_text: str | None = None
        if prefer_live_api and api_key and not intent.requires_hitl_confirmation:
            try:
                from google import genai
                from google.genai import types

                augmented_prompt = (
                    f"{context_window.formatted_context_prompt}\n\n### Current Traveler Request\n{sanitized_prompt}"
                    if context_window.formatted_context_prompt
                    else sanitized_prompt
                )

                def _call_gemini(target_model: str) -> str | None:
                    client = genai.Client(api_key=api_key)
                    resp = client.models.generate_content(
                        model=target_model,
                        contents=augmented_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=SORA_SYSTEM_PROMPT,
                            tools=ALL_SORA_TOOLS,
                            safety_settings=get_cloud_native_safety_settings(),
                            temperature=0.4,
                        ),
                    )
                    return resp.text if resp and resp.text else None

                for candidate_model in [selected_model, *routing.fallback_models]:
                    try:
                        response_text = await asyncio.to_thread(_call_gemini, candidate_model)
                        if response_text:
                            selected_model = candidate_model
                            break
                    except Exception as model_exc:
                        structured_logger.warning(
                            f"Model {candidate_model} invocation failed, trying next fallback: {model_exc}",
                            component="orchestrator",
                            event_type="model_fallback",
                            session_id=session_id,
                        )
            except Exception:
                response_text = None

        if not response_text:
            response_text = await asyncio.to_thread(
                render_tool_assisted_response,
                sanitized_prompt,
                memory_context_summary=context_window.formatted_context_prompt,
            )

        # 5. Agentic Self-Evaluation & Auto-Refinement Critic Pass
        self_eval = guardrail_engine.self_evaluate_and_refine(
            sanitized_prompt,
            response_text,
            is_itinerary_request=(intent.intent_category == "ITINERARY_PLANNING"),
        )
        final_response = self_eval.refined_response

        # 6. Persist Assistant Turn & Record Intent-vs-Outcome Telemetry
        await mem.aadd_turn(session_id=session_id, role="assistant", content=final_response)
        latency_ms = (time.perf_counter() - start_perf) * 1000.0
        final_status = (
            "AWAITING_HITL_CONFIRMATION"
            if intent.requires_hitl_confirmation or "Human-in-the-Loop Confirmation Required" in final_response
            else "FULFILLED"
        )
        intent_tracker.record_outcome(
            intent,
            actual_tools_invoked=intent.expected_tools,
            sub_agents_dispatched=[
                "rail_and_transit_specialist",
                "cultural_and_seasonal_specialist",
                "itinerary_architect_specialist",
                "safety_and_critic_specialist",
            ],
            selected_model=selected_model,
            outcome_status=final_status,
            self_eval_score=self_eval.overall_score,
            latency_ms=latency_ms,
        )
        return final_response


def run_sora_query(
    prompt: str,
    model: str | None = None,
    prefer_live_api: bool = True,
    session_id: str = "default",
) -> str:
    """Synchronous entrypoint wrapping `arun_sora_query` for CLI and standard script compatibility."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Executed inside an existing async event loop (e.g., FastAPI sync handler or async test)
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                asyncio.run,
                arun_sora_query(
                    prompt,
                    session_id=session_id,
                    model=model,
                    prefer_live_api=prefer_live_api,
                ),
            )
            return future.result()

    return asyncio.run(
        arun_sora_query(
            prompt,
            session_id=session_id,
            model=model,
            prefer_live_api=prefer_live_api,
        )
    )


__all__ = [
    "SORA_ROLE_HEADER",
    "SORA_SYSTEM_PROMPT",
    "arun_sora_query",
    "create_sora_agent",
    "render_tool_assisted_response",
    "root_agent",
    "run_sora_query",
]
