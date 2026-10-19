"""Google ADK Agent definition and execution engine for Sora."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from sora_agent.prompt import SORA_ROLE_HEADER, SORA_SYSTEM_PROMPT
from sora_agent.tools import (
    ALL_SORA_TOOLS,
    calculate_jr_pass_value,
    check_japan_destination_scope,
    compare_rail_vs_air,
    generate_day_by_day_itinerary_template,
    get_cultural_etiquette_and_logistics,
    get_ic_card_and_transit_guide,
    get_seasonal_travel_guide,
)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

DEFAULT_MODEL = os.getenv("SORA_MODEL", "gemini-2.5-flash")

# Try importing Google ADK Agent; provide a compatible fallback class if google-adk is not installed
try:
    from google.adk.agents import Agent as AdkAgent  # type: ignore[import-untyped]

    HAS_GOOGLE_ADK = True
except ImportError:
    HAS_GOOGLE_ADK = False

    @dataclass
    class AdkAgent:  # type: ignore[no-redef]
        """Fallback Agent representation matching google.adk.agents.Agent interface."""

        name: str
        model: str
        description: str
        instruction: str
        tools: list[Callable[..., Any]] = field(default_factory=list)


def create_sora_agent(model: str = DEFAULT_MODEL) -> AdkAgent:
    """Creates and returns the Sora Google ADK root_agent instance."""
    return AdkAgent(
        name="sora_japan_travel_agent",
        model=model,
        description=(
            "Sora: A Japan-specialist travel planning agent that designs day-by-day Japan "
            "itineraries with JR Pass math, IC card guidance, ryokan etiquette, konbini culture, "
            "seasonal advice, and regional rail vs. domestic air comparisons."
        ),
        instruction=SORA_SYSTEM_PROMPT,
        tools=ALL_SORA_TOOLS,
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


def render_tool_assisted_response(prompt: str) -> str:
    """Synthesizes a comprehensive Japan-specialist response using Sora's tools.

    Used both as a reliable fallback when GEMINI_API_KEY is not configured and as a
    deterministic structured response generator.
    """
    scope = check_japan_destination_scope(prompt)
    detected_japan_cities = _extract_cities_from_prompt(prompt)

    if not scope["is_japan_only"] and not detected_japan_cities:
        non_jp = ", ".join(scope["detected_non_japan_destinations"])
        return (
            f"Konnichiwa! I am **Sora**, a dedicated **Japan-specialist travel planning agent**.\n\n"
            f"I noticed your request mentions **{non_jp}**. Because I specialize exclusively in Japan—covering "
            f"Shinkansen & JR Pass mechanics, Suica/PASMO/ICOCA transit, ryokan & onsen etiquette, konbini culture, "
            f"and regional Japan itineraries—I don't plan trips outside Japan.\n\n"
            f"If you'd like to plan a trip to **Japan** (such as Tokyo, Kyoto, Osaka, Hiroshima, Kanazawa, Hokkaido, "
            f"or Kyushu), tell me your travel dates, trip length, and interests, and I'll craft a complete day-by-day "
            f"itinerary for you!"
        )

    days = _extract_days_from_prompt(prompt)
    month = _extract_month_from_prompt(prompt)
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

    return "\n".join(sections)


def run_sora_query(prompt: str, model: str = DEFAULT_MODEL, prefer_live_api: bool = True) -> str:
    """Runs a user travel planning prompt through Sora.

    If `GEMINI_API_KEY` or `GOOGLE_API_KEY` is configured and `prefer_live_api=True`, uses the
    `google-genai` SDK with Sora's system instruction and automatic Python tool calling.
    Otherwise, falls back cleanly to Sora's deterministic tool-assisted synthesis engine.
    """
    # Always enforce Japan-only scope first for non-Japan requests
    scope = check_japan_destination_scope(prompt)
    detected_japan_cities = _extract_cities_from_prompt(prompt)
    if not scope["is_japan_only"] and not detected_japan_cities:
        return render_tool_assisted_response(prompt)

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if prefer_live_api and api_key and api_key != "your_gemini_api_key_here":
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SORA_SYSTEM_PROMPT,
                    tools=ALL_SORA_TOOLS,
                    temperature=0.4,
                ),
            )
            if response and response.text:
                return response.text
        except Exception:
            # Fall back to deterministic tool-assisted synthesis if network or key fails
            pass

    return render_tool_assisted_response(prompt)


__all__ = [
    "SORA_ROLE_HEADER",
    "SORA_SYSTEM_PROMPT",
    "create_sora_agent",
    "root_agent",
    "run_sora_query",
    "render_tool_assisted_response",
]
