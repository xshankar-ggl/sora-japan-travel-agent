"""Japan-specific tools for the Sora Travel Planning Agent with strict Pydantic schemas and guided LLM error recovery."""

from __future__ import annotations

import re
from typing import Literal

from sora_agent.hitl import (
    ConfirmationDecisionOutput,
    hitl_manager,
    require_human_confirmation,
)
from sora_agent.knowledge import (
    CITY_CLUSTERS,
    CULTURAL_TOPICS,
    NATIONAL_JR_PASS_PRICES,
    RAIL_ROUTES,
    RAIL_VS_AIR_CORRIDORS,
    REGIONAL_JR_PASSES,
    SEASONAL_GUIDE,
)
from sora_agent.observability import structured_logger, trace_span
from sora_agent.schemas import (
    AnalyzedRailLegSchema,
    CulturalEtiquetteOutput,
    CulturalTopicSectionSchema,
    DailyPlanBlockSchema,
    DestinationScopeOutput,
    ErrorRecoveryGuidance,
    HighStakesBookingOutput,
    ICCardTransitGuideOutput,
    ItineraryTemplateOutput,
    JRPassCalculationOutput,
    RailVsAirComparisonOutput,
    RegionalPassRecommendationSchema,
    SeasonalTravelGuideOutput,
    TransitModeDetailsSchema,
)

# Known city aliases for canonical normalization
CITY_ALIASES: dict[str, str] = {
    "shin-osaka": "osaka",
    "shinosaka": "osaka",
    "umeda": "osaka",
    "namba": "osaka",
    "hakata": "fukuoka",
    "shin-hakodate-hokuto": "hakodate",
    "new chitose": "sapporo",
    "chitose": "sapporo",
    "naha": "okinawa",
    "haneda": "tokyo",
    "narita": "tokyo",
    "shinagawa": "tokyo",
    "shinjuku": "tokyo",
    "miyajima": "hiroshima",
    "odawara": "hakone",
    "hakone-yumoto": "hakone",
    "kawaguchiko": "hakone",
    "fujikawaguchiko": "hakone",
    "mt fuji": "hakone",
    "mount fuji": "hakone",
    "shirakawa-go": "takayama",
    "shirakawago": "takayama",
}

KNOWN_JAPAN_CITIES: set[str] = {
    "tokyo",
    "hakone",
    "kawaguchiko",
    "nikko",
    "kamakura",
    "yokohama",
    "atami",
    "ito",
    "kanazawa",
    "takayama",
    "shirakawa-go",
    "nagoya",
    "kyoto",
    "nara",
    "osaka",
    "kobe",
    "himeji",
    "kinosaki",
    "okayama",
    "naoshima",
    "hiroshima",
    "miyajima",
    "fukuoka",
    "hakata",
    "beppu",
    "kumamoto",
    "kagoshima",
    "nagasaki",
    "sendai",
    "aomori",
    "hakodate",
    "sapporo",
    "otaru",
    "furano",
    "niseko",
    "okinawa",
    "naha",
    "ishigaki",
    "matsuyama",
    "takamatsu",
}

SUPPORTED_JAPAN_AIRPORTS: dict[str, str] = {
    "HND": (
        "Haneda Airport (HND): Only 15–30 mins to central Tokyo! Take the **Tokyo Monorail** to Hamamatsucho "
        "(connects to JR Yamanote Line) or **Keikyu Airport Line** direct to Shinagawa / Asakusa. Both accept IC cards."
    ),
    "NRT": (
        "Narita Airport (NRT): ~55–60 mins from Tokyo. Take the **JR Narita Express (N'EX)** direct to Tokyo, "
        "Shinagawa, Shibuya, or Shinjuku (all-reserved), OR the **Keisei Skyliner** (36 mins to Ueno/Nippori)."
    ),
    "KIX": (
        "Kansai International Airport (KIX): Take the **JR Haruka Limited Express** (75 mins direct to Kyoto Station, "
        "50 mins to Shin-Osaka/Tennoji) or **Nankai Rapi:t** (38 mins to Namba in Osaka)."
    ),
    "ITM": (
        "Osaka Itami Airport (ITM): Take the **Osaka Monorail** + Hankyu Line (~30 mins to Umeda) or Airport Limousine "
        "Bus direct to Osaka/Umeda (30 mins) or Kyoto Station (50 mins). Accepts IC cards."
    ),
    "FUK": (
        "Fukuoka Airport (FUK): Take the free shuttle to the Domestic Terminal, then the **Fukuoka City Subway** "
        "(just 5 minutes / 2 stops to Hakata Station, or 11 minutes to Tenjin!)."
    ),
    "CTS": (
        "New Chitose Airport (CTS - Sapporo): Take the **JR Rapid Airport** train direct to Sapporo Station "
        "(37 minutes, runs every 12 minutes). Accepts Suica/Kitaca/ICOCA."
    ),
    "NGO": (
        "Chubu Centrair International Airport (NGO - Nagoya): Take the **Meitetsu μ-SKY Limited Express** "
        "(28 minutes to Meitetsu Nagoya Station)."
    ),
    "OKA": (
        "Naha Airport (OKA - Okinawa): Take the **Yui Rail (Okinawa Urban Monorail)** direct into central Naha "
        "(Kokusai-dori / Prefectural Office in 12 mins; Shuri Castle in 27 mins). Accepts Suica/PASMO/ICOCA."
    ),
}

AIRPORT_CITY_ALIASES: dict[str, str] = {
    "HANEDA": "HND",
    "TOKYO": "HND",
    "NARITA": "NRT",
    "KANSAI": "KIX",
    "OSAKA": "KIX",
    "KYOTO": "KIX",
    "ITAMI": "ITM",
    "FUKUOKA": "FUK",
    "HAKATA": "FUK",
    "SAPPORO": "CTS",
    "CHITOSE": "CTS",
    "NAGOYA": "NGO",
    "NAHA": "OKA",
    "OKINAWA": "OKA",
}

NON_JAPAN_DESTINATIONS: set[str] = {
    "seoul",
    "busan",
    "korea",
    "south korea",
    "taipei",
    "taiwan",
    "bangkok",
    "thailand",
    "singapore",
    "vietnam",
    "hanoi",
    "bali",
    "indonesia",
    "beijing",
    "shanghai",
    "china",
    "hong kong",
    "paris",
    "france",
    "london",
    "uk",
    "rome",
    "italy",
    "madrid",
    "spain",
    "berlin",
    "germany",
    "new york",
    "los angeles",
    "hawaii",
    "australia",
    "sydney",
    "cancun",
    "mexico",
    "dubai",
    "india",
    "switzerland",
}


def _normalize_city(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z\s\-]", "", name).strip().lower()
    return CITY_ALIASES.get(cleaned, cleaned)


def _is_valid_japan_city(raw_name: str) -> bool:
    norm = _normalize_city(raw_name)
    return bool(norm) and norm not in NON_JAPAN_DESTINATIONS and norm in KNOWN_JAPAN_CITIES


def _lookup_rail_leg(origin: str, destination: str) -> AnalyzedRailLegSchema:
    o = _normalize_city(origin)
    d = _normalize_city(destination)
    if o == d:
        return AnalyzedRailLegSchema(
            leg=f"{o.title()} -> {d.title()}",
            fare_jpy=0,
            duration_mins=0,
            train_name="Local intra-city transit",
            nozomi_supplement_jpy=0,
            scenic_tip="Use IC card (Suica/PASMO/ICOCA) for local metro and JR lines.",
        )

    if (o, d) in RAIL_ROUTES:
        route = RAIL_ROUTES[(o, d)]
        return AnalyzedRailLegSchema(
            leg=f"{o.title()} -> {d.title()}",
            fare_jpy=int(route["fare_jpy"]),
            duration_mins=int(route["duration_mins"]),
            train_name=str(route["train_name"]),
            nozomi_supplement_jpy=int(route["nozomi_supplement_jpy"]),
            scenic_tip=str(route["scenic_tip"]),
        )
    if (d, o) in RAIL_ROUTES:
        route = RAIL_ROUTES[(d, o)]
        return AnalyzedRailLegSchema(
            leg=f"{o.title()} -> {d.title()}",
            fare_jpy=int(route["fare_jpy"]),
            duration_mins=int(route["duration_mins"]),
            train_name=str(route["train_name"]),
            nozomi_supplement_jpy=int(route["nozomi_supplement_jpy"]),
            scenic_tip=str(route["scenic_tip"]),
        )

    # Try two-hop composition via major Shinkansen hubs
    for hub in ("osaka", "kyoto", "tokyo", "hiroshima", "kanazawa"):
        leg1 = RAIL_ROUTES.get((o, hub)) or RAIL_ROUTES.get((hub, o))
        leg2 = RAIL_ROUTES.get((hub, d)) or RAIL_ROUTES.get((d, hub))
        if leg1 and leg2:
            return AnalyzedRailLegSchema(
                leg=f"{o.title()} -> {d.title()}",
                fare_jpy=int((leg1["fare_jpy"] + leg2["fare_jpy"]) * 0.92),
                duration_mins=int(leg1["duration_mins"] + leg2["duration_mins"] + 20),
                train_name=f"{leg1['train_name']} + {leg2['train_name']} (via {hub.title()})",
                nozomi_supplement_jpy=int(leg1["nozomi_supplement_jpy"] + leg2["nozomi_supplement_jpy"]),
                scenic_tip=f"Transfer at {hub.title()} Station.",
            )

    return AnalyzedRailLegSchema(
        leg=f"{o.title()} -> {d.title()}",
        fare_jpy=8500,
        duration_mins=120,
        train_name="JR Limited Express / Regional Shinkansen",
        nozomi_supplement_jpy=0,
        scenic_tip="Verify exact timetable on Navitime or SmartEX.",
    )


def _lookup_green_fare(origin: str, destination: str, ordinary_fare: int) -> int:
    o = _normalize_city(origin)
    d = _normalize_city(destination)
    route = RAIL_ROUTES.get((o, d)) or RAIL_ROUTES.get((d, o))
    if route and "green_fare_jpy" in route:
        return int(route["green_fare_jpy"])
    for hub in ("osaka", "kyoto", "tokyo", "hiroshima", "kanazawa"):
        leg1 = RAIL_ROUTES.get((o, hub)) or RAIL_ROUTES.get((hub, o))
        leg2 = RAIL_ROUTES.get((hub, d)) or RAIL_ROUTES.get((d, hub))
        if leg1 and leg2:
            return int((leg1["green_fare_jpy"] + leg2["green_fare_jpy"]) * 0.92)
    return int(ordinary_fare * 1.35)


def _parse_leg_string(leg_str: str) -> tuple[str, str] | None:
    parts = re.split(r"\s*(?:->|→|\bto\b|--|/|\s-\s)\s*", leg_str.strip(), maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
        return parts[0].strip(), parts[1].strip()
    return None


@trace_span("sora.tool.calculate_jr_pass_value", component="tools")
def calculate_jr_pass_value(
    legs: list[str],
    duration_days: int = 7,
    pass_class: str = "ordinary",
) -> JRPassCalculationOutput:
    """Calculates whether a post-Oct-2023 National JR Pass, Regional JR Pass, or point-to-point tickets are best.

    Args:
        legs: Non-empty ordered list of intercity rail legs formatted as 'Origin -> Destination',
            e.g. ['Tokyo -> Kyoto', 'Kyoto -> Hiroshima', 'Hiroshima -> Tokyo'].
        duration_days: Official National JR Pass validity window in days. Must be 7, 14, or 21.
        pass_class: Car class to evaluate: 'ordinary' or 'green'.

    Returns:
        Strict `JRPassCalculationOutput` Pydantic model containing itemized leg fares, National JR Pass
        comparison, Regional Pass recommendations, or structured `error_recovery` guidance if inputs are invalid.
    """
    if not isinstance(legs, list) or len(legs) == 0:
        return JRPassCalculationOutput(
            status="error",
            verdict="INVALID_INPUT",
            summary="Cannot evaluate JR Pass value because `legs` is empty.",
            pass_evaluated="None",
            national_pass_cost_jpy=0,
            individual_tickets_total_jpy=0,
            net_savings_with_national_pass_jpy=0,
            nozomi_supplement_warning="N/A",
            regional_pass_recommendations=[],
            itemized_legs=[],
            error_recovery=ErrorRecoveryGuidance(
                error_code="EMPTY_RAIL_LEGS",
                error_message="The `legs` parameter must be a non-empty list of 'Origin -> Destination' strings.",
                invalid_parameter="legs",
                provided_value=str(legs),
                allowed_values=["['Tokyo -> Kyoto', 'Kyoto -> Tokyo']", "['Tokyo -> Hiroshima', 'Hiroshima -> Osaka']"],
                llm_recovery_instruction=(
                    "Extract the traveler's intercity rail transitions as 'Origin -> Destination' strings and "
                    "re-invoke `calculate_jr_pass_value` with at least one leg."
                ),
                suggested_tool_call_example=(
                    "calculate_jr_pass_value(legs=['Tokyo -> Kyoto', 'Kyoto -> Hiroshima', 'Hiroshima -> Tokyo'], "
                    "duration_days=7, pass_class='ordinary')"
                ),
            ),
        )

    if duration_days not in (7, 14, 21):
        return JRPassCalculationOutput(
            status="error",
            verdict="INVALID_INPUT",
            summary=f"Invalid JR Pass duration_days={duration_days}. Official National JR Passes are only sold for 7, 14, or 21 days.",
            pass_evaluated="Invalid Duration",
            national_pass_cost_jpy=0,
            individual_tickets_total_jpy=0,
            net_savings_with_national_pass_jpy=0,
            nozomi_supplement_warning="N/A",
            regional_pass_recommendations=[],
            itemized_legs=[],
            error_recovery=ErrorRecoveryGuidance(
                error_code="INVALID_JR_PASS_DURATION",
                error_message=(
                    f"`duration_days={duration_days}` is not a valid Japan Rail Pass duration. "
                    "National JR Passes are exclusively issued in 7, 14, or 21 consecutive-day increments."
                ),
                invalid_parameter="duration_days",
                provided_value=str(duration_days),
                allowed_values=["7", "14", "21"],
                llm_recovery_instruction=(
                    "Map the traveler's trip length to the nearest valid JR Pass window (7, 14, or 21 days) "
                    "and re-call `calculate_jr_pass_value(legs=..., duration_days=7 | 14 | 21)`."
                ),
                suggested_tool_call_example=(
                    "calculate_jr_pass_value(legs=['Tokyo -> Kyoto', 'Kyoto -> Tokyo'], duration_days=7, pass_class='ordinary')"
                ),
            ),
        )

    cleaned_class = pass_class.strip().lower()
    if cleaned_class in ("ordinary", "ordinary car", "standard"):
        normalized_class: Literal["ordinary", "green"] = "ordinary"
    elif cleaned_class in ("green", "green car", "first class"):
        normalized_class = "green"
    else:
        return JRPassCalculationOutput(
            status="error",
            verdict="INVALID_INPUT",
            summary=f"Invalid pass_class='{pass_class}'. Must be 'ordinary' or 'green'.",
            pass_evaluated="Invalid Class",
            national_pass_cost_jpy=0,
            individual_tickets_total_jpy=0,
            net_savings_with_national_pass_jpy=0,
            nozomi_supplement_warning="N/A",
            regional_pass_recommendations=[],
            itemized_legs=[],
            error_recovery=ErrorRecoveryGuidance(
                error_code="INVALID_PASS_CLASS",
                error_message=f"`pass_class='{pass_class}'` is not recognized.",
                invalid_parameter="pass_class",
                provided_value=pass_class,
                allowed_values=["ordinary", "green"],
                llm_recovery_instruction=(
                    "Re-invoke `calculate_jr_pass_value` with `pass_class='ordinary'` (standard reserved car) "
                    "or `pass_class='green'` (Green Car first class)."
                ),
                suggested_tool_call_example=(
                    "calculate_jr_pass_value(legs=['Tokyo -> Kyoto', 'Kyoto -> Tokyo'], duration_days=7, pass_class='ordinary')"
                ),
            ),
        )

    national_pass_cost = NATIONAL_JR_PASS_PRICES[normalized_class][duration_days]
    analyzed_legs: list[AnalyzedRailLegSchema] = []
    total_individual_jpy = 0
    total_nozomi_supplements_jpy = 0
    visited_cities: set[str] = set()

    for raw_leg in legs:
        parsed = _parse_leg_string(raw_leg)
        if not parsed:
            return JRPassCalculationOutput(
                status="error",
                verdict="INVALID_INPUT",
                summary=f"Malformed rail leg '{raw_leg}'. Expected 'Origin -> Destination'.",
                pass_evaluated=f"{duration_days}-Day National JR Pass",
                national_pass_cost_jpy=national_pass_cost,
                individual_tickets_total_jpy=0,
                net_savings_with_national_pass_jpy=0,
                nozomi_supplement_warning="N/A",
                regional_pass_recommendations=[],
                itemized_legs=[],
                error_recovery=ErrorRecoveryGuidance(
                    error_code="MALFORMED_LEG_FORMAT",
                    error_message=f"Could not parse origin and destination from leg string '{raw_leg}'.",
                    invalid_parameter="legs",
                    provided_value=raw_leg,
                    allowed_values=["Origin -> Destination", "Origin to Destination"],
                    llm_recovery_instruction=(
                        f"Format every leg in `legs` as `'Origin -> Destination'` (for example, `'Tokyo -> Kyoto'`) "
                        f"instead of `'{raw_leg}'`, then retry `calculate_jr_pass_value`."
                    ),
                    suggested_tool_call_example=(
                        "calculate_jr_pass_value(legs=['Tokyo -> Kyoto', 'Kyoto -> Osaka'], duration_days=7)"
                    ),
                ),
            )

        raw_origin, raw_dest = parsed
        if not _is_valid_japan_city(raw_origin) or not _is_valid_japan_city(raw_dest):
            bad_city = raw_origin if not _is_valid_japan_city(raw_origin) else raw_dest
            return JRPassCalculationOutput(
                status="error",
                verdict="INVALID_INPUT",
                summary=f"Unrecognized or non-Japan city '{bad_city}' in leg '{raw_leg}'.",
                pass_evaluated=f"{duration_days}-Day National JR Pass",
                national_pass_cost_jpy=national_pass_cost,
                individual_tickets_total_jpy=0,
                net_savings_with_national_pass_jpy=0,
                nozomi_supplement_warning="N/A",
                regional_pass_recommendations=[],
                itemized_legs=[],
                error_recovery=ErrorRecoveryGuidance(
                    error_code="UNRECOGNIZED_JAPAN_RAIL_CITY",
                    error_message=f"City '{bad_city}' is either outside Japan or not a recognized JR rail hub.",
                    invalid_parameter="legs",
                    provided_value=bad_city,
                    allowed_values=sorted(c.title() for c in KNOWN_JAPAN_CITIES),
                    llm_recovery_instruction=(
                        f"Replace '{bad_city}' with a valid Japanese rail city (such as Tokyo, Kyoto, Osaka, "
                        "Hiroshima, Kanazawa, Hakone, Takayama, Fukuoka, Sendai, or Sapporo) and re-call "
                        "`calculate_jr_pass_value`."
                    ),
                    suggested_tool_call_example=(
                        "calculate_jr_pass_value(legs=['Tokyo -> Kyoto', 'Kyoto -> Hiroshima', 'Hiroshima -> Osaka'], duration_days=7)"
                    ),
                ),
            )

        origin = _normalize_city(raw_origin)
        dest = _normalize_city(raw_dest)
        visited_cities.add(origin)
        visited_cities.add(dest)

        info = _lookup_rail_leg(origin, dest)
        leg_fare = _lookup_green_fare(origin, dest, info.fare_jpy) if normalized_class == "green" else info.fare_jpy
        total_individual_jpy += leg_fare
        total_nozomi_supplements_jpy += info.nozomi_supplement_jpy
        analyzed_legs.append(
            AnalyzedRailLegSchema(
                leg=f"{origin.title()} -> {dest.title()}",
                fare_jpy=leg_fare,
                duration_mins=info.duration_mins,
                train_name=info.train_name,
                nozomi_supplement_jpy=info.nozomi_supplement_jpy,
                scenic_tip=info.scenic_tip,
            )
        )

    net_savings_jpy = total_individual_jpy - national_pass_cost
    regional_recommendations: list[RegionalPassRecommendationSchema] = []
    best_hybrid_cost_jpy: int | None = None

    if {"hiroshima"} & visited_cities and ({"kyoto", "osaka"} & visited_cities):
        kh_pass = REGIONAL_JR_PASSES["kansai_hiroshima"]
        kansai_hiroshima_legs_cost = 0
        for item in analyzed_legs:
            leg_lower = item.leg.lower()
            if any(c in leg_lower for c in ("hiroshima", "himeji", "okayama")):
                if "tokyo" in leg_lower:
                    kansai_hiroshima_legs_cost += 10950
                else:
                    kansai_hiroshima_legs_cost += item.fare_jpy
        non_kh_legs_cost = max(0, total_individual_jpy - kansai_hiroshima_legs_cost)
        hybrid_cost = non_kh_legs_cost + int(kh_pass["price_jpy"])
        if kansai_hiroshima_legs_cost > int(kh_pass["price_jpy"]):
            best_hybrid_cost_jpy = hybrid_cost
        regional_recommendations.append(
            RegionalPassRecommendationSchema(
                pass_name=str(kh_pass["name"]),
                price_jpy=int(kh_pass["price_jpy"]),
                duration_days=int(kh_pass["duration_days"]),
                hybrid_total_jpy=hybrid_cost,
                estimated_kansai_hiroshima_leg_value_jpy=max(kansai_hiroshima_legs_cost, 22890),
                why_it_wins=(
                    f"At ¥17,000 for 5 days, combining the {kh_pass['name']} with individual Tokyo<->Kansai SmartEX "
                    f"tickets totals ~¥{hybrid_cost:,} (saving ¥{max(0, total_individual_jpy - hybrid_cost):,} vs. "
                    f"point-to-point tickets and ¥{max(0, national_pass_cost - hybrid_cost):,} vs. the ¥{national_pass_cost:,} "
                    "National JR Pass), AND it covers Nozomi trains on the Sanyo Shinkansen plus the JR Miyajima Ferry!"
                ),
            )
        )

    if "kanazawa" in visited_cities and "tokyo" in visited_cities and ({"kyoto", "osaka"} & visited_cities):
        ha_pass = REGIONAL_JR_PASSES["hokuriku_arch"]
        regional_recommendations.append(
            RegionalPassRecommendationSchema(
                pass_name=str(ha_pass["name"]),
                price_jpy=int(ha_pass["price_jpy"]),
                duration_days=int(ha_pass["duration_days"]),
                why_it_wins=str(ha_pass["notes"]),
            )
        )

    if best_hybrid_cost_jpy is not None and best_hybrid_cost_jpy < national_pass_cost and regional_recommendations:
        verdict: Literal["WORTH_IT", "REGIONAL_PASS_BETTER", "BUY_INDIVIDUAL_TICKETS", "INVALID_INPUT"] = (
            "REGIONAL_PASS_BETTER"
        )
        summary = (
            f"Skip the {duration_days}-day National JR Pass (¥{national_pass_cost:,}). Combining individual SmartEX "
            f"tickets with the **{regional_recommendations[0].pass_name}** (¥{regional_recommendations[0].price_jpy:,}) "
            f"costs only **¥{best_hybrid_cost_jpy:,}** total—saving you ¥{total_individual_jpy - best_hybrid_cost_jpy:,} "
            f"over individual tickets AND ¥{national_pass_cost - best_hybrid_cost_jpy:,} over the National JR Pass!"
        )
    elif net_savings_jpy > 0:
        verdict = "WORTH_IT"
        summary = (
            f"The {duration_days}-day {normalized_class.title()} National JR Pass (¥{national_pass_cost:,}) "
            f"SAVES you approximately ¥{net_savings_jpy:,} compared to individual tickets (¥{total_individual_jpy:,})."
        )
    elif regional_recommendations:
        verdict = "REGIONAL_PASS_BETTER"
        summary = (
            f"Skip the {duration_days}-day National JR Pass (¥{national_pass_cost:,})—individual tickets total only "
            f"¥{total_individual_jpy:,} (you would lose ¥{abs(net_savings_jpy):,}). Instead, combine individual "
            f"SmartEX tickets with the **{regional_recommendations[0].pass_name}** (¥{regional_recommendations[0].price_jpy:,})!"
        )
    else:
        verdict = "BUY_INDIVIDUAL_TICKETS"
        summary = (
            f"Do NOT buy the {duration_days}-day National JR Pass (¥{national_pass_cost:,}). Your point-to-point "
            f"rail tickets total only ¥{total_individual_jpy:,}, meaning the National JR Pass would overpay by "
            f"¥{abs(net_savings_jpy):,}. Buy individual tickets via the SmartEX app or JR ticket machines and ride "
            f"the fastest Nozomi trains without supplemental fees."
        )

    return JRPassCalculationOutput(
        status="success",
        verdict=verdict,
        summary=summary,
        pass_evaluated=f"{duration_days}-Day National JR Pass ({normalized_class.title()} Car)",
        national_pass_cost_jpy=national_pass_cost,
        individual_tickets_total_jpy=total_individual_jpy,
        net_savings_with_national_pass_jpy=net_savings_jpy,
        nozomi_supplement_warning=(
            f"Note: With a National JR Pass, riding Nozomi or Mizuho trains requires an extra Nozomi/Mizuho Upgrade "
            f"Ticket (~¥{total_nozomi_supplements_jpy:,} across your legs), whereas Hikari, Sakura, Kodama, Hayabusa, "
            f"and Kagayaki are included at no extra fee."
        ),
        regional_pass_recommendations=regional_recommendations,
        itemized_legs=analyzed_legs,
        error_recovery=None,
    )


@trace_span("sora.tool.compare_rail_vs_air", component="tools")
def compare_rail_vs_air(origin: str, destination: str) -> RailVsAirComparisonOutput:
    """Compares Shinkansen/Limited Express rail vs. domestic air between two Japanese cities.

    Args:
        origin: Origin city name in Japan (e.g., 'Tokyo', 'Osaka').
        destination: Destination city name in Japan (e.g., 'Sapporo', 'Fukuoka', 'Hiroshima', 'Kyoto').

    Returns:
        Strict `RailVsAirComparisonOutput` Pydantic model comparing door-to-door time, cost, luggage rules,
        and recommended mode, or `error_recovery` guidance if inputs are invalid.
    """
    o = _normalize_city(origin)
    d = _normalize_city(destination)

    if not _is_valid_japan_city(origin) or not _is_valid_japan_city(destination):
        bad = origin if not _is_valid_japan_city(origin) else destination
        return RailVsAirComparisonOutput(
            status="error",
            corridor=f"{origin} <-> {destination}",
            winner="invalid_input",
            headline=f"Cannot compare rail vs. air for unrecognized or non-Japan city '{bad}'.",
            rail_details=TransitModeDetailsSchema(
                mode="N/A",
                door_to_door_mins=0,
                cost_jpy_range="N/A",
            ),
            air_details=TransitModeDetailsSchema(
                mode="N/A",
                door_to_door_mins=0,
                cost_jpy_range="N/A",
            ),
            luggage_note="N/A",
            error_recovery=ErrorRecoveryGuidance(
                error_code="INVALID_CORRIDOR_CITY",
                error_message=f"'{bad}' is not a valid Japanese city supported by `compare_rail_vs_air`.",
                invalid_parameter="origin" if not _is_valid_japan_city(origin) else "destination",
                provided_value=bad,
                allowed_values=sorted(c.title() for c in KNOWN_JAPAN_CITIES),
                llm_recovery_instruction=(
                    "Pass two distinct Japanese cities (e.g., origin='Tokyo', destination='Fukuoka' or 'Sapporo' "
                    "or 'Hiroshima') and re-invoke `compare_rail_vs_air`."
                ),
                suggested_tool_call_example="compare_rail_vs_air(origin='Tokyo', destination='Fukuoka')",
            ),
        )

    if o == d:
        return RailVsAirComparisonOutput(
            status="error",
            corridor=f"{o.title()} <-> {d.title()}",
            winner="invalid_input",
            headline=f"Origin and destination both normalize to '{o.title()}'. Use local transit within a single city.",
            rail_details=TransitModeDetailsSchema(
                mode="Local JR / Metro",
                door_to_door_mins=20,
                cost_jpy_range="¥180 - ¥400",
            ),
            air_details=TransitModeDetailsSchema(
                mode="N/A (Same City)",
                door_to_door_mins=0,
                cost_jpy_range="N/A",
            ),
            luggage_note="Use station coin lockers or hotel luggage hold for intra-city travel.",
            error_recovery=ErrorRecoveryGuidance(
                error_code="IDENTICAL_ORIGIN_AND_DESTINATION",
                error_message=f"Origin '{origin}' and destination '{destination}' resolve to the same city ({o.title()}).",
                invalid_parameter="destination",
                provided_value=destination,
                allowed_values=[c.title() for c in sorted(KNOWN_JAPAN_CITIES) if c != o],
                llm_recovery_instruction=(
                    "Do not call `compare_rail_vs_air` for intra-city movement. Instead, call "
                    "`get_ic_card_and_transit_guide` for local metro/IC card guidance, or pass two different "
                    "Japanese cities to `compare_rail_vs_air`."
                ),
                suggested_tool_call_example="compare_rail_vs_air(origin='Tokyo', destination='Sapporo')",
            ),
        )

    pair = (o, d) if (o, d) in RAIL_VS_AIR_CORRIDORS else (d, o)
    luggage_note = (
        "Shinkansen allows 2 pieces up to 160cm total dimensions in overhead racks for free "
        "(160-250cm requires a free 'Seat with Oversized Baggage Area' reservation). "
        "Domestic JAL/ANA fares include 20kg checked baggage; LCCs (Peach/Jetstar) charge extra for bags."
    )

    if pair in RAIL_VS_AIR_CORRIDORS:
        data = RAIL_VS_AIR_CORRIDORS[pair]
        rail_raw = data["rail"]
        air_raw = data["air"]
        return RailVsAirComparisonOutput(
            status="success",
            corridor=f"{o.title()} <-> {d.title()}",
            winner=data["winner"],
            headline=str(data["headline"]),
            rail_details=TransitModeDetailsSchema(
                mode=str(rail_raw.get("mode", "")),
                station_to_station_mins=rail_raw.get("station_to_station_mins"),
                door_to_door_mins=int(rail_raw.get("door_to_door_mins", 0)),
                cost_jpy_range=str(rail_raw.get("cost_jpy_range", "")),
                pros=list(rail_raw.get("pros", [])),
                cons=list(rail_raw.get("cons", [])),
            ),
            air_details=TransitModeDetailsSchema(
                mode=str(air_raw.get("mode", "")),
                airport_to_airport_mins=air_raw.get("airport_to_airport_mins"),
                door_to_door_mins=int(air_raw.get("door_to_door_mins", 0)),
                cost_jpy_range=str(air_raw.get("cost_jpy_range", "")),
                airport_transfer_note=air_raw.get("airport_transfer_note"),
                pros=list(air_raw.get("pros", [])),
                cons=list(air_raw.get("cons", [])),
            ),
            luggage_note=luggage_note,
            error_recovery=None,
        )

    rail_info = _lookup_rail_leg(o, d)
    winner: Literal["rail", "air"] = "rail" if rail_info.duration_mins <= 240 else "air"
    return RailVsAirComparisonOutput(
        status="success",
        corridor=f"{o.title()} <-> {d.title()}",
        winner=winner,
        headline=(
            f"{'Rail (Shinkansen/Limited Express)' if winner == 'rail' else 'Domestic Air'} is generally faster "
            f"door-to-door for {o.title()} to {d.title()}."
        ),
        rail_details=TransitModeDetailsSchema(
            mode=rail_info.train_name,
            station_to_station_mins=rail_info.duration_mins,
            door_to_door_mins=rail_info.duration_mins + 30,
            cost_jpy_range=f"¥{rail_info.fare_jpy:,}",
            scenic_tip=rail_info.scenic_tip,
        ),
        air_details=TransitModeDetailsSchema(
            mode="Domestic Flight (JAL / ANA / Skymark / Peach)",
            airport_to_airport_mins=80,
            door_to_door_mins=210,
            cost_jpy_range="¥10,000 - ¥24,000",
        ),
        luggage_note=luggage_note,
        error_recovery=None,
    )


@trace_span("sora.tool.get_ic_card_and_transit_guide", component="tools")
def get_ic_card_and_transit_guide(
    arrival_airport: str = "HND",
    regions: list[str] | None = None,
    has_iphone: bool = True,
) -> ICCardTransitGuideOutput:
    """Provides Japan IC card (Suica/PASMO/ICOCA) and airport-to-city transit mechanics.

    Args:
        arrival_airport: Arrival airport IATA code or Japanese city (e.g., 'HND', 'NRT', 'KIX', 'ITM', 'FUK', 'CTS', 'NGO', 'OKA').
        regions: Optional list of Japanese regions/cities visited.
        has_iphone: True if the traveler uses an iPhone with Apple Wallet.

    Returns:
        Strict `ICCardTransitGuideOutput` Pydantic model with IC card setup, SmartEX linkage, and exceptions,
        or structured `error_recovery` instructions if `arrival_airport` is invalid.
    """
    raw_airport = arrival_airport.upper().strip()
    airport = AIRPORT_CITY_ALIASES.get(raw_airport, raw_airport)

    if airport not in SUPPORTED_JAPAN_AIRPORTS:
        return ICCardTransitGuideOutput(
            status="error",
            primary_ic_card_recommendation="Invalid arrival_airport code provided.",
            nationwide_interoperability="N/A",
            arrival_airport_transfer="N/A",
            smartex_shinkansen_tip="N/A",
            critical_exceptions=[],
            regions_requested=regions or [],
            error_recovery=ErrorRecoveryGuidance(
                error_code="UNSUPPORTED_ARRIVAL_AIRPORT",
                error_message=f"Airport code '{arrival_airport}' is not a recognized Japanese arrival airport.",
                invalid_parameter="arrival_airport",
                provided_value=arrival_airport,
                allowed_values=sorted(SUPPORTED_JAPAN_AIRPORTS.keys()),
                llm_recovery_instruction=(
                    "Re-invoke `get_ic_card_and_transit_guide` using a valid Japanese airport IATA code: "
                    "'HND' (Tokyo Haneda), 'NRT' (Tokyo Narita), 'KIX' (Osaka/Kyoto Kansai), 'ITM' (Osaka Itami), "
                    "'FUK' (Fukuoka), 'CTS' (Sapporo New Chitose), 'NGO' (Nagoya Centrair), or 'OKA' (Okinawa Naha)."
                ),
                suggested_tool_call_example="get_ic_card_and_transit_guide(arrival_airport='HND', has_iphone=True)",
            ),
        )

    if has_iphone:
        ic_recommendation = (
            "Add a digital **Suica, PASMO, or ICOCA directly inside Apple Wallet** before you even land in Japan "
            "(Wallet -> '+' -> Transit Card -> Japan -> Suica/PASMO/ICOCA). Load funds instantly with a Mastercard, "
            "Amex, or Visa credit card in Apple Pay. Enable **Express Transit Mode** so you can tap through gates "
            "without waking your phone or using FaceID!"
        )
    else:
        ic_recommendation = (
            "For Android (non-Japanese models lack Osaifu-Keitai FeliCa chips) or physical card users: pick up a "
            "physical **Welcome Suica** at Haneda/Narita JR East Travel Service Centers, a standard green **Suica** "
            "at major JR East stations, or a physical **ICOCA** card at JR West stations (KIX, Kyoto, Shin-Osaka). "
            "Load physical IC cards with **JPY cash** at any station ticket machine or 7-Eleven ATM."
        )

    return ICCardTransitGuideOutput(
        status="success",
        primary_ic_card_recommendation=ic_recommendation,
        nationwide_interoperability=(
            "Japan's 10 major IC cards (**Suica, PASMO, ICOCA, Kitaca, TOICA, manaca, PiTaPa, Hayakaken, nimoca, SUGOCA**) "
            "are **100% mutually compatible nationwide**. One Suica or ICOCA works on Tokyo subways, Kyoto buses, "
            "Osaka Metro, Hiroshima streetcars, Fukuoka subways, Sapporo trains, and at all konbini & vending machines."
        ),
        arrival_airport_transfer=SUPPORTED_JAPAN_AIRPORTS[airport],
        smartex_shinkansen_tip=(
            "Download the **SmartEX app** to book Tokaido/Sanyo/Kyushu Shinkansen tickets and register your IC card's "
            "17-character ID number (found in the Suica/ICOCA app or on the back of a physical card). You can then tap "
            "your phone/IC card straight through the Shinkansen gates—no paper tickets needed!"
        ),
        critical_exceptions=[
            "You CANNOT tap an IC card to cross between different JR regions on local trains (e.g., Tokyo to Atami/Ito across the JR East / JR Central border).",
            "You CANNOT ride the Shinkansen by just tapping an unlinked IC card—link a SmartEX ticket first or insert a paper Shinkansen ticket.",
            "Since July 2024, **Kumamoto city trams/buses** and select rural buses stopped accepting nationwide IC cards (they accept contactless credit cards or cash).",
        ],
        regions_requested=regions or ["Nationwide Japan"],
        error_recovery=None,
    )


@trace_span("sora.tool.get_seasonal_travel_guide", component="tools")
def get_seasonal_travel_guide(month: int, regions: list[str] | None = None) -> SeasonalTravelGuideOutput:
    """Returns month-specific Japan travel guidance, sakura/koyo windows, festivals, and packing advice.

    Args:
        month: Calendar month as an integer strictly from 1 (January) to 12 (December).
        regions: Optional list of Japanese regions/cities the traveler is visiting.

    Returns:
        Strict `SeasonalTravelGuideOutput` Pydantic model for the specified month, or structured
        `error_recovery` instructions if `month` is outside `1..12`.
    """
    if isinstance(month, bool) or not isinstance(month, int) or month < 1 or month > 12:
        return SeasonalTravelGuideOutput(
            status="error",
            month=0,
            season="Invalid Month",
            weather_summary="N/A",
            crowd_alerts="N/A",
            highlights=[],
            seasonal_foods=[],
            packing_tips=[],
            regions_considered=regions or [],
            error_recovery=ErrorRecoveryGuidance(
                error_code="INVALID_CALENDAR_MONTH",
                error_message=f"`month={month}` is out of bounds. Calendar month must be an integer between 1 and 12.",
                invalid_parameter="month",
                provided_value=str(month),
                allowed_values=[str(m) for m in range(1, 13)],
                llm_recovery_instruction=(
                    "Convert the traveler's target travel season or month name into an integer between 1 (January) "
                    "and 12 (December)—for example, April=4 for Sakura, November=11 for autumn foliage—and re-call "
                    "`get_seasonal_travel_guide(month=...)`."
                ),
                suggested_tool_call_example="get_seasonal_travel_guide(month=11, regions=['Tokyo', 'Kyoto'])",
            ),
        )

    data = SEASONAL_GUIDE[month]
    return SeasonalTravelGuideOutput(
        status="success",
        month=month,
        season=str(data["season"]),
        weather_summary=str(data["weather_summary"]),
        crowd_alerts=str(data["crowd_alerts"]),
        highlights=list(data["highlights"]),
        seasonal_foods=list(data["seasonal_foods"]),
        packing_tips=list(data["packing_tips"]),
        regions_considered=regions or ["Honshu (Golden Route)", "Hokkaido", "Kyushu"],
        error_recovery=None,
    )


@trace_span("sora.tool.get_cultural_etiquette_and_logistics", component="tools")
def get_cultural_etiquette_and_logistics(topic: str = "all") -> CulturalEtiquetteOutput:
    """Returns Japan cultural etiquette and logistics guidance as a strict Pydantic schema.

    Args:
        topic: Must be one of 'ryokan_onsen', 'konbini', 'shrines_temples_dining',
            'luggage_connectivity', or 'all'.

    Returns:
        Strict `CulturalEtiquetteOutput` Pydantic model containing the requested topic sections,
        or structured `error_recovery` instructions if an unrecognized topic is requested.
    """
    key = topic.lower().strip()
    valid_topics = set(CULTURAL_TOPICS.keys()) | {"all"}

    if key not in valid_topics:
        return CulturalEtiquetteOutput(
            status="error",
            topic_requested=topic,
            error_recovery=ErrorRecoveryGuidance(
                error_code="INVALID_CULTURAL_TOPIC",
                error_message=f"Topic '{topic}' is not a valid cultural etiquette category.",
                invalid_parameter="topic",
                provided_value=topic,
                allowed_values=sorted(valid_topics),
                llm_recovery_instruction=(
                    "Re-invoke `get_cultural_etiquette_and_logistics` with `topic` set to one of: "
                    "'ryokan_onsen', 'konbini', 'shrines_temples_dining', 'luggage_connectivity', or 'all'."
                ),
                suggested_tool_call_example="get_cultural_etiquette_and_logistics(topic='ryokan_onsen')",
            ),
        )

    def _build_section(section_key: str) -> CulturalTopicSectionSchema:
        raw = CULTURAL_TOPICS[section_key]
        return CulturalTopicSectionSchema(
            title=str(raw["title"]),
            golden_rules=list(raw["golden_rules"]),
        )

    if key == "all":
        return CulturalEtiquetteOutput(
            status="success",
            topic_requested="all",
            ryokan_onsen=_build_section("ryokan_onsen"),
            konbini=_build_section("konbini"),
            shrines_temples_dining=_build_section("shrines_temples_dining"),
            luggage_connectivity=_build_section("luggage_connectivity"),
            error_recovery=None,
        )

    kwargs = {key: _build_section(key)}
    return CulturalEtiquetteOutput(
        status="success",
        topic_requested=key,
        error_recovery=None,
        **kwargs,
    )


@trace_span("sora.tool.check_japan_destination_scope", component="tools")
def check_japan_destination_scope(query_or_destinations: str) -> DestinationScopeOutput:
    """Checks if a user request involves non-Japan destinations outside Sora's specialist scope.

    Args:
        query_or_destinations: Non-empty user prompt or list of cities/countries.

    Returns:
        Strict `DestinationScopeOutput` Pydantic model indicating whether the request is strictly Japan-focused.
    """
    if not isinstance(query_or_destinations, str) or not query_or_destinations.strip():
        return DestinationScopeOutput(
            status="error",
            is_japan_only=False,
            detected_non_japan_destinations=[],
            detected_japan_destinations=[],
            policy_reminder="Cannot verify scope on an empty query.",
            error_recovery=ErrorRecoveryGuidance(
                error_code="EMPTY_SCOPE_QUERY",
                error_message="`query_or_destinations` must be a non-empty string.",
                invalid_parameter="query_or_destinations",
                provided_value=str(query_or_destinations),
                allowed_values=["Non-empty user travel query string"],
                llm_recovery_instruction=(
                    "Pass the traveler's full natural-language query or destination list to "
                    "`check_japan_destination_scope(query_or_destinations=...)`."
                ),
                suggested_tool_call_example=(
                    "check_japan_destination_scope(query_or_destinations='Plan an 8-day trip to Tokyo and Kyoto')"
                ),
            ),
        )

    lowered = query_or_destinations.lower()
    detected_non_japan = sorted(
        place.title()
        for place in NON_JAPAN_DESTINATIONS
        if re.search(rf"\b{re.escape(place)}\b", lowered)
    )
    detected_japan = sorted(
        city.title()
        for city in KNOWN_JAPAN_CITIES
        if re.search(rf"\b{re.escape(city)}\b", lowered)
    )
    return DestinationScopeOutput(
        status="success",
        is_japan_only=len(detected_non_japan) == 0,
        detected_non_japan_destinations=detected_non_japan,
        detected_japan_destinations=detected_japan,
        policy_reminder=(
            "Sora is strictly a Japan-specialist travel planning agent. Politely decline planning itineraries for "
            f"{', '.join(detected_non_japan)} and offer to design a Japan itinerary instead."
            if detected_non_japan
            else "All destinations are within Japan scope."
        ),
        error_recovery=None,
    )


@trace_span("sora.tool.generate_day_by_day_itinerary_template", component="tools")
def generate_day_by_day_itinerary_template(
    days: int = 7,
    cities: list[str] | None = None,
    month: int = 4,
    pace: str = "moderate",
) -> ItineraryTemplateOutput:
    """Generates a structured day-by-day Japan itinerary blueprint with logistics, JR Pass math, and clusters.

    Args:
        days: Total number of days in Japan (strictly 1 to 21).
        cities: Ordered list of Japanese cities to visit (e.g., ['Tokyo', 'Hakone', 'Kyoto', 'Hiroshima', 'Osaka']).
        month: Travel month (strictly 1 to 12) for seasonal customization.
        pace: Travel pace ('relaxed', 'moderate', or 'packed').

    Returns:
        Strict `ItineraryTemplateOutput` Pydantic model containing neighborhood clusters, transit legs, and
        JR Pass analysis, or structured `error_recovery` guidance if inputs are out of range.
    """
    if isinstance(days, bool) or not isinstance(days, int) or days < 1 or days > 21:
        return ItineraryTemplateOutput(
            status="error",
            trip_days=0,
            pace=pace,
            cities_in_order=[],
            seasonal_context=None,
            jr_pass_recommendation=None,
            day_by_day_plan=[],
            error_recovery=ErrorRecoveryGuidance(
                error_code="INVALID_ITINERARY_DAYS",
                error_message=f"`days={days}` is invalid. Itinerary duration must be between 1 and 21 days.",
                invalid_parameter="days",
                provided_value=str(days),
                allowed_values=["Integer between 1 and 21"],
                llm_recovery_instruction=(
                    "Re-invoke `generate_day_by_day_itinerary_template` with `days` set to an integer between 1 and 21. "
                    "For trips longer than 21 days, segment the itinerary into 21-day phases."
                ),
                suggested_tool_call_example=(
                    "generate_day_by_day_itinerary_template(days=8, cities=['Tokyo', 'Hakone', 'Kyoto'], month=11)"
                ),
            ),
        )

    if isinstance(month, bool) or not isinstance(month, int) or month < 1 or month > 12:
        return ItineraryTemplateOutput(
            status="error",
            trip_days=days,
            pace=pace,
            cities_in_order=[],
            seasonal_context=None,
            jr_pass_recommendation=None,
            day_by_day_plan=[],
            error_recovery=ErrorRecoveryGuidance(
                error_code="INVALID_ITINERARY_MONTH",
                error_message=f"`month={month}` is invalid. Month must be an integer between 1 and 12.",
                invalid_parameter="month",
                provided_value=str(month),
                allowed_values=[str(m) for m in range(1, 13)],
                llm_recovery_instruction=(
                    "Pass a valid calendar month integer (`1` for January through `12` for December) to "
                    "`generate_day_by_day_itinerary_template`."
                ),
                suggested_tool_call_example=(
                    "generate_day_by_day_itinerary_template(days=7, cities=['Tokyo', 'Kyoto'], month=4)"
                ),
            ),
        )

    normalized_pace = pace.strip().lower()
    if normalized_pace not in ("relaxed", "moderate", "packed"):
        return ItineraryTemplateOutput(
            status="error",
            trip_days=days,
            pace=pace,
            cities_in_order=[],
            seasonal_context=None,
            jr_pass_recommendation=None,
            day_by_day_plan=[],
            error_recovery=ErrorRecoveryGuidance(
                error_code="INVALID_ITINERARY_PACE",
                error_message=f"`pace='{pace}'` is not supported.",
                invalid_parameter="pace",
                provided_value=pace,
                allowed_values=["relaxed", "moderate", "packed"],
                llm_recovery_instruction=(
                    "Re-call `generate_day_by_day_itinerary_template` with `pace='relaxed'`, "
                    "`pace='moderate'`, or `pace='packed'`."
                ),
                suggested_tool_call_example=(
                    "generate_day_by_day_itinerary_template(days=7, cities=['Tokyo', 'Kyoto'], month=4, pace='moderate')"
                ),
            ),
        )

    raw_cities = cities or (["tokyo", "kyoto", "osaka"] if days >= 6 else ["tokyo"])
    for raw_city in raw_cities:
        if not _is_valid_japan_city(raw_city):
            return ItineraryTemplateOutput(
                status="error",
                trip_days=days,
                pace=normalized_pace,
                cities_in_order=[],
                seasonal_context=None,
                jr_pass_recommendation=None,
                day_by_day_plan=[],
                error_recovery=ErrorRecoveryGuidance(
                    error_code="UNRECOGNIZED_ITINERARY_CITY",
                    error_message=f"City '{raw_city}' is outside Japan or not a supported Japanese destination.",
                    invalid_parameter="cities",
                    provided_value=raw_city,
                    allowed_values=sorted(c.title() for c in KNOWN_JAPAN_CITIES),
                    llm_recovery_instruction=(
                        f"Remove '{raw_city}' and provide only valid Japanese cities from the supported list "
                        "when calling `generate_day_by_day_itinerary_template`."
                    ),
                    suggested_tool_call_example=(
                        "generate_day_by_day_itinerary_template(days=7, cities=['Tokyo', 'Kanazawa', 'Kyoto'], month=4)"
                    ),
                ),
            )

    norm_cities = [_normalize_city(c) for c in raw_cities if c.strip()]
    if not norm_cities:
        norm_cities = ["tokyo", "kyoto"]

    city_weights = {
        "tokyo": 3,
        "kyoto": 3,
        "osaka": 2,
        "hiroshima": 1,
        "hakone": 1,
        "kanazawa": 2,
        "takayama": 1,
        "fukuoka": 2,
        "sapporo": 2,
    }
    allocations: list[str] = []
    while len(allocations) < days:
        for city in norm_cities:
            weight = city_weights.get(city, 1)
            count = min(weight, days - len(allocations))
            allocations.extend([city] * count)
            if len(allocations) >= days:
                break

    ordered_schedule: list[str] = []
    for city in dict.fromkeys(norm_cities):
        ordered_schedule.extend([c for c in allocations if c == city])

    transit_legs: list[str] = []
    for idx in range(1, len(ordered_schedule)):
        prev_c = ordered_schedule[idx - 1]
        curr_c = ordered_schedule[idx]
        if prev_c != curr_c:
            transit_legs.append(f"{prev_c.title()} -> {curr_c.title()}")

    if len(set(ordered_schedule)) > 1 and ordered_schedule[0] != ordered_schedule[-1]:
        transit_legs.append(f"{ordered_schedule[-1].title()} -> {ordered_schedule[0].title()}")

    if not transit_legs:
        transit_legs = [f"{ordered_schedule[0].title()} -> {ordered_schedule[0].title()}"]

    jr_pass_analysis = calculate_jr_pass_value(
        legs=transit_legs,
        duration_days=7 if days <= 9 else 14,
        pass_class="ordinary",
    )
    seasonal_info = get_seasonal_travel_guide(
        month=month,
        regions=[c.title() for c in dict.fromkeys(ordered_schedule)],
    )

    city_day_counters: dict[str, int] = {}
    daily_plan: list[DailyPlanBlockSchema] = []

    etiquette_rotation = [
        "At Shinto shrines (Torii gates), purify at the Chozuya pavilion and follow the 2-bow, 2-clap, 1-bow ritual.",
        "Keep trains quiet: set phones to 'Manner Mode' (silent) and avoid voice calls or eating on commuter subways.",
        "At Buddhist temples, waft incense smoke toward yourself and bow silently with hands pressed together (do not clap).",
        "Konbini hack: grab a 7-Eleven Tamago Sando or FamilyMart Famichiki and withdraw JPY cash at 7-Bank ATMs.",
        "Ryokan & Onsen rule: wear your yukata LEFT side over RIGHT side, and wash/rinse thoroughly before entering the bath.",
        "Never leave a tip in Japan—saying 'Gochisosama deshita' (thank you for the meal) when leaving is the highest compliment!",
        "Look at Tabelog ratings like a local: 3.5+ out of 5.0 means a top-tier restaurant across Japan.",
    ]

    for day_idx, city in enumerate(ordered_schedule, start=1):
        city_day_num = city_day_counters.get(city, 0)
        city_day_counters[city] = city_day_num + 1

        clusters = CITY_CLUSTERS.get(city, CITY_CLUSTERS["tokyo"])
        cluster = clusters[city_day_num % len(clusters)]

        prev_city = ordered_schedule[day_idx - 2] if day_idx > 1 else None
        transition_note = None
        luggage_tip = None
        if prev_city and prev_city != city:
            leg_info = _lookup_rail_leg(prev_city, city)
            transition_note = (
                f"Transit from {prev_city.title()} to {city.title()}: {leg_info.train_name} "
                f"(~{leg_info.duration_mins} mins, ¥{leg_info.fare_jpy:,}). {leg_info.scenic_tip}"
            )
            if city in ("hakone", "takayama", "hiroshima", "kanazawa"):
                luggage_tip = (
                    f"Takkyubin Luggage Tip: Ship your main suitcases ahead via Yamato Transport from {prev_city.title()} "
                    f"and travel to {city.title()} with a light 1–2 night backpack."
                )
            else:
                luggage_tip = (
                    "Oversized Baggage Reminder: If your suitcase is 160–250cm (L+W+H), reserve a 'Seat with an Oversized "
                    "Baggage Area' on the Shinkansen."
                )

        daily_plan.append(
            DailyPlanBlockSchema(
                day=day_idx,
                base_city=city.title(),
                theme=str(cluster["cluster_name"]),
                intercity_transition=transition_note,
                luggage_strategy=luggage_tip,
                morning=str(cluster["morning"]),
                afternoon=str(cluster["afternoon"]),
                evening=str(cluster["evening"]),
                local_transit_tip=str(cluster["transit_tip"]),
                cultural_etiquette_tip=etiquette_rotation[(day_idx - 1) % len(etiquette_rotation)],
            )
        )

    return ItineraryTemplateOutput(
        status="success",
        trip_days=days,
        pace=normalized_pace,
        cities_in_order=[c.title() for c in dict.fromkeys(ordered_schedule)],
        seasonal_context=seasonal_info,
        jr_pass_recommendation=jr_pass_analysis,
        day_by_day_plan=daily_plan,
        error_recovery=None,
    )


@trace_span("sora.tool.request_high_stakes_booking_confirmation", component="tools")
@require_human_confirmation("HIGH_STAKES_TRAVEL_COMMITMENT")
def request_high_stakes_booking_confirmation(
    action_type: str,
    item_description: str,
    estimated_total_jpy: int,
    traveler_count: int = 1,
    non_refundable: bool = True,
) -> HighStakesBookingOutput:
    """Stages a high-stakes travel booking or purchase behind a mandatory Human-in-the-Loop (HITL) approval gate.

    Never commits financial charges or non-refundable reservations (such as ryokan kaiseki stays, JR Pass
    exchange orders, or Takkyubin luggage shipments) without explicit human confirmation.

    Args:
        action_type: One of 'BOOK_RYOKAN_KAISEKI', 'PURCHASE_JR_PASS', 'RESERVE_SHINKANSEN_OVERSIZED_BAGGAGE',
            'SCHEDULE_TAKKYUBIN_LUGGAGE', or 'CHARGE_IC_CARD_WALLET'.
        item_description: Specific reservation or pass being staged.
        estimated_total_jpy: Total cost in Japanese Yen (JPY).
        traveler_count: Number of travelers (must be >= 1).
        non_refundable: Whether the reservation carries strict cancellation penalties.

    Returns:
        Strict `HighStakesBookingOutput` Pydantic model containing `confirmation_id` and human approval instructions.
    """
    return hitl_manager.request_confirmation(
        action_type=action_type,
        item_description=item_description,
        estimated_total_jpy=estimated_total_jpy,
        traveler_count=traveler_count,
        non_refundable=non_refundable,
    )


@trace_span("sora.tool.resolve_booking_confirmation", component="tools")
def resolve_booking_confirmation(
    confirmation_id: str,
    approved: bool,
    reviewer_id: str = "human_traveler",
    reviewer_note: str = "",
) -> ConfirmationDecisionOutput:
    """Completes or cancels a pending Human-in-the-Loop (HITL) booking confirmation.

    Args:
        confirmation_id: Unique ID returned by `request_high_stakes_booking_confirmation`.
        approved: True if the human traveler approves the booking; False to reject and cancel.
        reviewer_id: Identifier of the human decision-maker.
        reviewer_note: Optional confirmation note.

    Returns:
        Strict `ConfirmationDecisionOutput` Pydantic model recording the human's final decision.
    """
    return hitl_manager.resolve_confirmation(
        confirmation_id=confirmation_id,
        approved=approved,
        reviewer_id=reviewer_id,
        reviewer_note=reviewer_note,
    )


ALL_SORA_TOOLS = [
    calculate_jr_pass_value,
    compare_rail_vs_air,
    get_ic_card_and_transit_guide,
    get_seasonal_travel_guide,
    get_cultural_etiquette_and_logistics,
    generate_day_by_day_itinerary_template,
    check_japan_destination_scope,
    request_high_stakes_booking_confirmation,
    resolve_booking_confirmation,
]
