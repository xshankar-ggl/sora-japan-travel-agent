"""Japan-specific tools for the Sora Travel Planning Agent (compatible with Google ADK)."""

from __future__ import annotations

import re
from typing import Any

from sora_agent.knowledge import (
    CITY_CLUSTERS,
    CULTURAL_TOPICS,
    NATIONAL_JR_PASS_PRICES,
    RAIL_ROUTES,
    RAIL_VS_AIR_CORRIDORS,
    REGIONAL_JR_PASSES,
    SEASONAL_GUIDE,
)

# Known city aliases for normalization
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

NON_JAPAN_DESTINATIONS: set[str] = {
    "seoul", "busan", "korea", "south korea", "taipei", "taiwan", "bangkok", "thailand",
    "singapore", "vietnam", "hanoi", "bali", "indonesia", "beijing", "shanghai", "china",
    "hong kong", "paris", "france", "london", "uk", "rome", "italy", "madrid", "spain",
    "berlin", "germany", "new york", "los angeles", "hawaii", "australia", "sydney",
    "cancun", "mexico", "dubai", "india", "switzerland",
}


def _normalize_city(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z\s\-]", "", name).strip().lower()
    return CITY_ALIASES.get(cleaned, cleaned)


def _lookup_rail_leg(origin: str, destination: str) -> dict[str, Any]:
    o = _normalize_city(origin)
    d = _normalize_city(destination)
    if o == d:
        return {
            "origin": o,
            "destination": d,
            "fare_jpy": 0,
            "green_fare_jpy": 0,
            "nozomi_supplement_jpy": 0,
            "duration_mins": 0,
            "train_name": "Local intra-city transit",
            "scenic_tip": "Use IC card (Suica/PASMO/ICOCA) for local metro and JR lines.",
        }
    if (o, d) in RAIL_ROUTES:
        return {"origin": o, "destination": d, **RAIL_ROUTES[(o, d)]}
    if (d, o) in RAIL_ROUTES:
        return {"origin": o, "destination": d, **RAIL_ROUTES[(d, o)]}

    # Try two-hop composition via Tokyo, Osaka, or Kyoto
    for hub in ("osaka", "kyoto", "tokyo", "hiroshima", "kanazawa"):
        leg1 = RAIL_ROUTES.get((o, hub)) or RAIL_ROUTES.get((hub, o))
        leg2 = RAIL_ROUTES.get((hub, d)) or RAIL_ROUTES.get((d, hub))
        if leg1 and leg2:
            return {
                "origin": o,
                "destination": d,
                "fare_jpy": int((leg1["fare_jpy"] + leg2["fare_jpy"]) * 0.92),
                "green_fare_jpy": int((leg1["green_fare_jpy"] + leg2["green_fare_jpy"]) * 0.92),
                "nozomi_supplement_jpy": leg1["nozomi_supplement_jpy"] + leg2["nozomi_supplement_jpy"],
                "duration_mins": leg1["duration_mins"] + leg2["duration_mins"] + 20,
                "train_name": f"{leg1['train_name']} + {leg2['train_name']} (via {hub.title()})",
                "scenic_tip": f"Transfer at {hub.title()} Station.",
            }

    # Fallback estimate for unlisted regional JR routes
    return {
        "origin": o,
        "destination": d,
        "fare_jpy": 8500,
        "green_fare_jpy": 11500,
        "nozomi_supplement_jpy": 0,
        "duration_mins": 120,
        "train_name": "JR Limited Express / Regional Shinkansen",
        "scenic_tip": "Verify exact timetable on Navitime or SmartEX.",
    }


def _parse_leg_string(leg_str: str) -> tuple[str, str] | None:
    parts = re.split(r"\s*(?:->|→|\bto\b|--|/|\s-\s)\s*", leg_str.strip(), maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 2 and parts[0] and parts[1]:
        return _normalize_city(parts[0]), _normalize_city(parts[1])
    return None


def calculate_jr_pass_value(
    legs: list[str],
    duration_days: int = 7,
    pass_class: str = "ordinary",
) -> dict[str, Any]:
    """Calculates whether a National JR Pass, Regional JR Pass, or individual tickets are best.

    Args:
        legs: Ordered list of rail legs, e.g. ["Tokyo -> Kyoto", "Kyoto -> Hiroshima", "Hiroshima -> Tokyo"].
        duration_days: Pass duration in days (7, 14, or 21). Defaults to 7.
        pass_class: Either "ordinary" or "green". Defaults to "ordinary".

    Returns:
        Dictionary with itemized leg fares, National JR Pass comparison, Regional Pass suggestions,
        and a clear recommendation verdict.
    """
    normalized_class = "green" if pass_class.lower().startswith("green") else "ordinary"
    if duration_days <= 7:
        pass_days = 7
    elif duration_days <= 14:
        pass_days = 14
    else:
        pass_days = 21

    national_pass_cost = NATIONAL_JR_PASS_PRICES[normalized_class][pass_days]

    analyzed_legs: list[dict[str, Any]] = []
    total_individual_jpy = 0
    total_nozomi_supplements_jpy = 0
    visited_cities: set[str] = set()

    for raw_leg in legs:
        parsed = _parse_leg_string(raw_leg)
        if not parsed:
            continue
        origin, dest = parsed
        visited_cities.add(origin)
        visited_cities.add(dest)
        info = _lookup_rail_leg(origin, dest)
        leg_fare = info["green_fare_jpy"] if normalized_class == "green" else info["fare_jpy"]
        total_individual_jpy += leg_fare
        total_nozomi_supplements_jpy += info["nozomi_supplement_jpy"]
        analyzed_legs.append(
            {
                "leg": f"{origin.title()} -> {dest.title()}",
                "fare_jpy": leg_fare,
                "duration_mins": info["duration_mins"],
                "train_name": info["train_name"],
                "nozomi_supplement_jpy": info["nozomi_supplement_jpy"],
                "scenic_tip": info["scenic_tip"],
            }
        )

    net_savings_jpy = total_individual_jpy - national_pass_cost

    # Check if any Regional JR Pass offers a better hybrid deal
    regional_recommendations: list[dict[str, Any]] = []
    best_hybrid_cost_jpy: int | None = None

    if {"hiroshima"} & visited_cities and ({"kyoto", "osaka"} & visited_cities):
        kh_pass = REGIONAL_JR_PASSES["kansai_hiroshima"]
        kansai_hiroshima_legs_cost = 0
        for item in analyzed_legs:
            leg_lower = item["leg"].lower()
            if any(c in leg_lower for c in ("hiroshima", "himeji", "okayama")):
                if "tokyo" in leg_lower:
                    # The Hiroshima <-> Shin-Osaka portion (~¥10,950) is covered by the Kansai-Hiroshima Pass
                    kansai_hiroshima_legs_cost += 10950
                else:
                    kansai_hiroshima_legs_cost += item["fare_jpy"]
        non_kh_legs_cost = max(0, total_individual_jpy - kansai_hiroshima_legs_cost)
        hybrid_cost = non_kh_legs_cost + kh_pass["price_jpy"]
        if kansai_hiroshima_legs_cost > kh_pass["price_jpy"]:
            best_hybrid_cost_jpy = hybrid_cost
        regional_recommendations.append(
            {
                "pass_name": kh_pass["name"],
                "price_jpy": kh_pass["price_jpy"],
                "duration_days": kh_pass["duration_days"],
                "hybrid_total_jpy": hybrid_cost,
                "estimated_kansai_hiroshima_leg_value_jpy": max(kansai_hiroshima_legs_cost, 22890),
                "why_it_wins": (
                    f"At ¥17,000 for 5 days, combining the {kh_pass['name']} with individual Tokyo<->Kansai SmartEX "
                    f"tickets totals ~¥{hybrid_cost:,} (saving ¥{max(0, total_individual_jpy - hybrid_cost):,} vs. "
                    f"point-to-point tickets and ¥{max(0, national_pass_cost - hybrid_cost):,} vs. the ¥{national_pass_cost:,} "
                    "National JR Pass), AND it covers Nozomi trains on the Sanyo Shinkansen plus the JR Miyajima Ferry!"
                ),
            }
        )

    if "kanazawa" in visited_cities and "tokyo" in visited_cities and ({"kyoto", "osaka"} & visited_cities):
        ha_pass = REGIONAL_JR_PASSES["hokuriku_arch"]
        regional_recommendations.append(
            {
                "pass_name": ha_pass["name"],
                "price_jpy": ha_pass["price_jpy"],
                "duration_days": ha_pass["duration_days"],
                "why_it_wins": ha_pass["notes"],
            }
        )

    if best_hybrid_cost_jpy is not None and best_hybrid_cost_jpy < national_pass_cost and regional_recommendations:
        verdict = "REGIONAL_PASS_BETTER"
        summary = (
            f"Skip the {pass_days}-day National JR Pass (¥{national_pass_cost:,}). Combining individual SmartEX "
            f"tickets with the **{regional_recommendations[0]['pass_name']}** (¥{regional_recommendations[0]['price_jpy']:,}) "
            f"costs only **¥{best_hybrid_cost_jpy:,}** total—saving you ¥{total_individual_jpy - best_hybrid_cost_jpy:,} "
            f"over individual tickets AND ¥{national_pass_cost - best_hybrid_cost_jpy:,} over the National JR Pass!"
        )
    elif net_savings_jpy > 0:
        verdict = "WORTH_IT"
        summary = (
            f"The {pass_days}-day {normalized_class.title()} National JR Pass (¥{national_pass_cost:,}) "
            f"SAVES you approximately ¥{net_savings_jpy:,} compared to individual tickets (¥{total_individual_jpy:,})."
        )
    elif regional_recommendations:
        verdict = "REGIONAL_PASS_BETTER"
        summary = (
            f"Skip the {pass_days}-day National JR Pass (¥{national_pass_cost:,})—individual tickets total only "
            f"¥{total_individual_jpy:,} (you would lose ¥{abs(net_savings_jpy):,}). Instead, combine individual "
            f"SmartEX tickets with the **{regional_recommendations[0]['pass_name']}** (¥{regional_recommendations[0]['price_jpy']:,})!"
        )
    else:
        verdict = "BUY_INDIVIDUAL_TICKETS"
        summary = (
            f"Do NOT buy the {pass_days}-day National JR Pass (¥{national_pass_cost:,}). Your point-to-point "
            f"rail tickets total only ¥{total_individual_jpy:,}, meaning the National JR Pass would overpay by "
            f"¥{abs(net_savings_jpy):,}. Buy individual tickets via the SmartEX app or JR ticket machines and ride "
            f"the fastest Nozomi trains without supplemental fees."
        )

    return {
        "verdict": verdict,
        "summary": summary,
        "pass_evaluated": f"{pass_days}-Day National JR Pass ({normalized_class.title()} Car)",
        "national_pass_cost_jpy": national_pass_cost,
        "individual_tickets_total_jpy": total_individual_jpy,
        "net_savings_with_national_pass_jpy": net_savings_jpy,
        "nozomi_supplement_warning": (
            f"Note: With a National JR Pass, riding Nozomi or Mizuho trains requires an extra Nozomi/Mizuho Upgrade "
            f"Ticket (~¥{total_nozomi_supplements_jpy:,} across your legs), whereas Hikari, Sakura, Kodama, Hayabusa, "
            f"and Kagayaki are included at no extra fee."
        ),
        "regional_pass_recommendations": regional_recommendations,
        "itemized_legs": analyzed_legs,
    }


def compare_rail_vs_air(origin: str, destination: str) -> dict[str, Any]:
    """Compares Shinkansen/Limited Express rail vs. domestic air between two Japanese cities.

    Args:
        origin: Origin city name in Japan (e.g., "Tokyo", "Osaka").
        destination: Destination city name in Japan (e.g., "Sapporo", "Fukuoka", "Hiroshima", "Kyoto").

    Returns:
        Detailed comparison of door-to-door time, cost, luggage rules, and Sora's recommendation.
    """
    o = _normalize_city(origin)
    d = _normalize_city(destination)
    pair = (o, d) if (o, d) in RAIL_VS_AIR_CORRIDORS else (d, o)

    if pair in RAIL_VS_AIR_CORRIDORS:
        data = RAIL_VS_AIR_CORRIDORS[pair]
        return {
            "corridor": f"{o.title()} <-> {d.title()}",
            "winner": data["winner"],
            "headline": data["headline"],
            "rail_details": data["rail"],
            "air_details": data["air"],
            "luggage_note": (
                "Shinkansen allows 2 pieces up to 160cm total dimensions in overhead racks for free "
                "(160-250cm requires a free 'Seat with Oversized Baggage Area' reservation). "
                "Domestic JAL/ANA fares include 20kg checked baggage; LCCs (Peach/Jetstar) charge extra for bags."
            ),
        }

    # Fallback dynamic comparison using rail lookup
    rail_info = _lookup_rail_leg(o, d)
    winner = "rail" if rail_info["duration_mins"] <= 240 else "air"
    return {
        "corridor": f"{o.title()} <-> {d.title()}",
        "winner": winner,
        "headline": (
            f"{'Rail (Shinkansen/Limited Express)' if winner == 'rail' else 'Domestic Air'} is generally faster "
            f"door-to-door for {o.title()} to {d.title()}."
        ),
        "rail_details": {
            "mode": rail_info["train_name"],
            "station_to_station_mins": rail_info["duration_mins"],
            "door_to_door_mins": rail_info["duration_mins"] + 30,
            "cost_jpy_range": f"¥{rail_info['fare_jpy']:,}",
            "scenic_tip": rail_info["scenic_tip"],
        },
        "air_details": {
            "mode": "Domestic Flight (JAL / ANA / Skymark / Peach)",
            "airport_to_airport_mins": 80,
            "door_to_door_mins": 210,
            "cost_jpy_range": "¥10,000 - ¥24,000",
        },
    }


def get_ic_card_and_transit_guide(
    arrival_airport: str = "HND",
    regions: list[str] | None = None,
    has_iphone: bool = True,
) -> dict[str, Any]:
    """Provides Japan IC card (Suica/PASMO/ICOCA) and local transit mechanics for a traveler.

    Args:
        arrival_airport: Arrival airport code or city (e.g., "HND", "NRT", "KIX", "FUK").
        regions: List of Japanese regions/cities visited (e.g., ["Tokyo", "Kyoto", "Hiroshima"]).
        has_iphone: Whether the traveler uses an iPhone with Apple Wallet.

    Returns:
        Dictionary explaining the best IC card setup, airport transfer options, SmartEX linkage, and exceptions.
    """
    airport = arrival_airport.upper().strip()
    airport_transfers = {
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
        "FUK": (
            "Fukuoka Airport (FUK): Take the free shuttle to the Domestic Terminal, then the **Fukuoka City Subway** "
            "(just 5 minutes / 2 stops to Hakata Station, or 11 minutes to Tenjin!)."
        ),
    }

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

    return {
        "primary_ic_card_recommendation": ic_recommendation,
        "nationwide_interoperability": (
            "Japan's 10 major IC cards (**Suica, PASMO, ICOCA, Kitaca, TOICA, manaca, PiTaPa, Hayakaken, nimoca, SUGOCA**) "
            "are **100% mutually compatible nationwide**. One Suica or ICOCA works on Tokyo subways, Kyoto buses, "
            "Osaka Metro, Hiroshima streetcars, Fukuoka subways, Sapporo trains, and at all konbini & vending machines."
        ),
        "arrival_airport_transfer": airport_transfers.get(
            airport,
            f"At {airport}: Follow signs for Rail/Monorail and tap your IC card (or reserve a Limited Express seat).",
        ),
        "smartex_shinkansen_tip": (
            "Download the **SmartEX app** to book Tokaido/Sanyo/Kyushu Shinkansen tickets and register your IC card's "
            "17-character ID number (found in the Suica/ICOCA app or on the back of a physical card). You can then tap "
            "your phone/IC card straight through the Shinkansen gates—no paper tickets needed!"
        ),
        "critical_exceptions": [
            "You CANNOT tap an IC card to cross between different JR regions on local trains (e.g., Tokyo to Atami/Ito across the JR East / JR Central border).",
            "You CANNOT ride the Shinkansen by just tapping an unlinked IC card—link a SmartEX ticket first or insert a paper Shinkansen ticket.",
            "Since July 2024, **Kumamoto city trams/buses** and select rural buses stopped accepting nationwide IC cards (they accept contactless credit cards or cash).",
        ],
        "regions_requested": regions or ["Nationwide Japan"],
    }


def get_seasonal_travel_guide(month: int, regions: list[str] | None = None) -> dict[str, Any]:
    """Returns month-specific Japan travel guidance, sakura/koyo windows, festivals, and packing advice.

    Args:
        month: Month of the year as an integer from 1 (January) to 12 (December).
        regions: Optional list of regions/cities the traveler is visiting.

    Returns:
        Seasonal travel guide for the specified month.
    """
    clamped_month = max(1, min(12, int(month)))
    data = SEASONAL_GUIDE[clamped_month]
    return {
        "month": clamped_month,
        "season": data["season"],
        "weather_summary": data["weather_summary"],
        "crowd_alerts": data["crowd_alerts"],
        "highlights": data["highlights"],
        "seasonal_foods": data["seasonal_foods"],
        "packing_tips": data["packing_tips"],
        "regions_considered": regions or ["Honshu (Golden Route)", "Hokkaido", "Kyushu"],
    }


def get_cultural_etiquette_and_logistics(topic: str = "all") -> dict[str, Any]:
    """Returns Japan cultural etiquette and logistics guidance.

    Args:
        topic: One of "ryokan_onsen", "konbini", "shrines_temples_dining", "luggage_connectivity", or "all".

    Returns:
        Dictionary of actionable Japan-specific cultural and logistical rules.
    """
    key = topic.lower().strip()
    if key in CULTURAL_TOPICS:
        return {key: CULTURAL_TOPICS[key]}
    return CULTURAL_TOPICS


def check_japan_destination_scope(query_or_destinations: str) -> dict[str, Any]:
    """Checks if a user request involves non-Japan destinations outside Sora's specialist scope.

    Args:
        query_or_destinations: User prompt or list of cities/countries.

    Returns:
        Dictionary indicating whether the request is strictly Japan-focused or contains out-of-scope destinations.
    """
    lowered = query_or_destinations.lower()
    detected_non_japan = sorted(
        place.title()
        for place in NON_JAPAN_DESTINATIONS
        if re.search(rf"\b{re.escape(place)}\b", lowered)
    )
    return {
        "is_japan_only": len(detected_non_japan) == 0,
        "detected_non_japan_destinations": detected_non_japan,
        "policy_reminder": (
            "Sora is strictly a Japan-specialist travel planning agent. Politely decline planning itineraries for "
            f"{', '.join(detected_non_japan)} and offer to design a Japan itinerary instead."
            if detected_non_japan
            else "All destinations are within Japan scope."
        ),
    }


def generate_day_by_day_itinerary_template(
    days: int = 7,
    cities: list[str] | None = None,
    month: int = 4,
    pace: str = "moderate",
) -> dict[str, Any]:
    """Generates a structured day-by-day Japan itinerary blueprint with logistics, JR Pass math, and clusters.

    Args:
        days: Total number of days in Japan (1 to 21).
        cities: Ordered list of cities to visit (e.g., ["Tokyo", "Hakone", "Kyoto", "Hiroshima", "Osaka"]).
        month: Travel month (1-12) for seasonal customization.
        pace: Travel pace ("relaxed", "moderate", or "packed").

    Returns:
        Complete day-by-day itinerary structure with neighborhood clusters, transit legs, and JR Pass analysis.
    """
    total_days = max(1, min(21, int(days)))
    raw_cities = cities or (
        ["tokyo", "kyoto", "osaka"]
        if total_days >= 6
        else ["tokyo"]
    )
    norm_cities = [_normalize_city(c) for c in raw_cities if c.strip()]
    if not norm_cities:
        norm_cities = ["tokyo", "kyoto"]

    # Allocate days proportionally across requested cities
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
    while len(allocations) < total_days:
        for city in norm_cities:
            weight = city_weights.get(city, 1)
            count = min(weight, total_days - len(allocations))
            allocations.extend([city] * count)
            if len(allocations) >= total_days:
                break

    # Sort allocations so each city's days stay contiguous in the user's requested order
    ordered_schedule: list[str] = []
    for city in dict.fromkeys(norm_cities):
        ordered_schedule.extend([c for c in allocations if c == city])

    # Build intercity transit legs
    transit_legs: list[str] = []
    for idx in range(1, len(ordered_schedule)):
        prev_c = ordered_schedule[idx - 1]
        curr_c = ordered_schedule[idx]
        if prev_c != curr_c:
            transit_legs.append(f"{prev_c.title()} -> {curr_c.title()}")

    # Add return leg to Tokyo if multi-city loop and >= 7 days
    if len(set(ordered_schedule)) > 1 and ordered_schedule[0] != ordered_schedule[-1]:
        transit_legs.append(f"{ordered_schedule[-1].title()} -> {ordered_schedule[0].title()}")

    jr_pass_analysis = calculate_jr_pass_value(
        legs=transit_legs,
        duration_days=7 if total_days <= 9 else 14,
        pass_class="ordinary",
    )
    seasonal_info = get_seasonal_travel_guide(month=month, regions=[c.title() for c in dict.fromkeys(ordered_schedule)])

    city_day_counters: dict[str, int] = {}
    daily_plan: list[dict[str, Any]] = []

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
                f"Transit from {prev_city.title()} to {city.title()}: {leg_info['train_name']} "
                f"(~{leg_info['duration_mins']} mins, ¥{leg_info['fare_jpy']:,}). {leg_info['scenic_tip']}"
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
            {
                "day": day_idx,
                "base_city": city.title(),
                "theme": cluster["cluster_name"],
                "intercity_transition": transition_note,
                "luggage_strategy": luggage_tip,
                "morning": cluster["morning"],
                "afternoon": cluster["afternoon"],
                "evening": cluster["evening"],
                "local_transit_tip": cluster["transit_tip"],
                "cultural_etiquette_tip": etiquette_rotation[(day_idx - 1) % len(etiquette_rotation)],
            }
        )

    return {
        "trip_days": total_days,
        "pace": pace,
        "cities_in_order": [c.title() for c in dict.fromkeys(ordered_schedule)],
        "seasonal_context": seasonal_info,
        "jr_pass_recommendation": jr_pass_analysis,
        "day_by_day_plan": daily_plan,
    }


ALL_SORA_TOOLS = [
    calculate_jr_pass_value,
    compare_rail_vs_air,
    get_ic_card_and_transit_guide,
    get_seasonal_travel_guide,
    get_cultural_etiquette_and_logistics,
    generate_day_by_day_itinerary_template,
    check_japan_destination_scope,
]
