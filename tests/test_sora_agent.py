"""Test and evaluation suite for Sora, the Japan-Specialist Travel Planning Agent.

Compatible with both `pytest` and standard library `python3 -m unittest discover -s tests -v`.
"""

from __future__ import annotations

import unittest

from sora_agent import (
    SORA_ROLE_HEADER,
    SORA_SYSTEM_PROMPT,
    calculate_jr_pass_value,
    check_japan_destination_scope,
    compare_rail_vs_air,
    create_sora_agent,
    generate_day_by_day_itinerary_template,
    get_cultural_etiquette_and_logistics,
    get_ic_card_and_transit_guide,
    get_seasonal_travel_guide,
    root_agent,
    run_sora_query,
)


def test_role_and_system_prompt_completeness() -> None:
    """Verifies that Sora's system prompt includes the exact role header and core domains."""
    assert "You are **Sora**, a Japan-specialist travel planning agent." in SORA_ROLE_HEADER
    assert SORA_ROLE_HEADER in SORA_SYSTEM_PROMPT
    for required_topic in (
        "JR Pass mechanics",
        "IC cards",
        "ryokan etiquette",
        "konbini",
        "seasonal travel",
        "regional rail vs. domestic air",
    ):
        assert required_topic in SORA_SYSTEM_PROMPT


def test_adk_agent_configuration() -> None:
    """Verifies that root_agent is properly configured with tools and instructions."""
    agent = create_sora_agent()
    assert agent.name == "sora_japan_travel_agent"
    assert len(agent.tools) >= 7
    assert root_agent.name == "sora_japan_travel_agent"


def test_jr_pass_golden_route_not_worth_national_pass() -> None:
    """A simple Tokyo <-> Kyoto round trip (~¥28,340) should NOT recommend a ¥50,000 7-day JR Pass."""
    result = calculate_jr_pass_value(
        legs=["Tokyo -> Kyoto", "Kyoto -> Osaka", "Osaka -> Tokyo"],
        duration_days=7,
        pass_class="ordinary",
    )
    assert result["verdict"] == "BUY_INDIVIDUAL_TICKETS"
    assert result["national_pass_cost_jpy"] == 50000
    assert result["individual_tickets_total_jpy"] < 50000
    assert result["net_savings_with_national_pass_jpy"] < 0


def test_jr_pass_recommends_kansai_hiroshima_regional_pass() -> None:
    """Tokyo -> Kyoto -> Hiroshima -> Osaka -> Tokyo should recommend the JR West Kansai-Hiroshima Area Pass."""
    result = calculate_jr_pass_value(
        legs=["Tokyo -> Kyoto", "Kyoto -> Hiroshima", "Hiroshima -> Osaka", "Osaka -> Tokyo"],
        duration_days=7,
        pass_class="ordinary",
    )
    assert result["verdict"] == "REGIONAL_PASS_BETTER"
    assert any(
        "Kansai-Hiroshima" in rec["pass_name"]
        for rec in result["regional_pass_recommendations"]
    )


def test_jr_pass_worth_it_for_heavy_shinkansen_itinerary() -> None:
    """High-mileage 7-day Shinkansen travel exceeding ¥50,000 should return WORTH_IT."""
    result = calculate_jr_pass_value(
        legs=[
            "Tokyo -> Hiroshima",
            "Hiroshima -> Fukuoka",
            "Fukuoka -> Tokyo",
            "Tokyo -> Sendai",
        ],
        duration_days=7,
        pass_class="ordinary",
    )
    assert result["verdict"] == "WORTH_IT"
    assert result["individual_tickets_total_jpy"] > 50000
    assert result["net_savings_with_national_pass_jpy"] > 0


def test_rail_vs_air_comparisons() -> None:
    """Verifies accurate rail vs. domestic air recommendations across major Japan corridors."""
    tokyo_kyoto = compare_rail_vs_air("Tokyo", "Kyoto")
    assert tokyo_kyoto["winner"] == "rail"

    tokyo_fukuoka = compare_rail_vs_air("Tokyo", "Fukuoka")
    assert tokyo_fukuoka["winner"] == "air"
    assert "5 mins" in str(tokyo_fukuoka["air_details"])

    tokyo_sapporo = compare_rail_vs_air("Tokyo", "Sapporo")
    assert tokyo_sapporo["winner"] == "air"


def test_ic_card_and_seasonal_guides() -> None:
    """Verifies IC card guidance and all 12 months of seasonal travel data."""
    ic_iphone = get_ic_card_and_transit_guide(arrival_airport="HND", has_iphone=True)
    assert "Apple Wallet" in ic_iphone["primary_ic_card_recommendation"]
    assert "SmartEX" in ic_iphone["smartex_shinkansen_tip"]

    ic_android = get_ic_card_and_transit_guide(arrival_airport="KIX", has_iphone=False)
    assert "Welcome Suica" in ic_android["primary_ic_card_recommendation"]

    for month in range(1, 13):
        guide = get_seasonal_travel_guide(month=month)
        assert guide["month"] == month
        assert guide["season"]
        assert len(guide["highlights"]) > 0


def test_cultural_etiquette_topics() -> None:
    """Verifies ryokan, onsen, konbini, shrines/temples, and Takkyubin luggage topics."""
    all_topics = get_cultural_etiquette_and_logistics("all")
    assert "ryokan_onsen" in all_topics
    assert "konbini" in all_topics
    assert "shrines_temples_dining" in all_topics
    assert "luggage_connectivity" in all_topics

    ryokan_rules = " ".join(all_topics["ryokan_onsen"]["golden_rules"])
    assert "LEFT side over the RIGHT side" in ryokan_rules
    assert "Kinosaki Onsen" in ryokan_rules

    luggage_rules = " ".join(all_topics["luggage_connectivity"]["golden_rules"])
    assert "160 cm" in luggage_rules
    assert "Yamato" in luggage_rules


def test_scope_guardrail_rejects_non_japan_trips() -> None:
    """Sora must politely decline non-Japan travel requests and stay in character."""
    scope = check_japan_destination_scope("Plan a 5-day trip to Paris and Rome.")
    assert scope["is_japan_only"] is False
    assert "Paris" in scope["detected_non_japan_destinations"]

    response = run_sora_query("Plan a 5-day trip to Paris and Rome.", prefer_live_api=False)
    assert "Sora" in response
    assert "Japan-specialist" in response
    assert "Paris" in response


def test_day_by_day_itinerary_generation() -> None:
    """Verifies full day-by-day Japan itinerary generation with logistics and etiquette."""
    prompt = "Plan an 8-day November itinerary for Tokyo, Hakone, Kyoto, and Hiroshima."
    response = run_sora_query(prompt, prefer_live_api=False)
    assert "Day 1:" in response
    assert "Day 8:" in response
    assert "Kansai-Hiroshima" in response
    assert "Takkyubin" in response
    assert "Suica" in response


class TestSoraAgentSuite(unittest.TestCase):
    """Unittest wrapper around all Sora evaluation tests."""

    def test_01_role_and_prompt(self) -> None:
        test_role_and_system_prompt_completeness()

    def test_02_adk_agent(self) -> None:
        test_adk_agent_configuration()

    def test_03_jr_pass_golden_route(self) -> None:
        test_jr_pass_golden_route_not_worth_national_pass()

    def test_04_jr_pass_regional_recommendation(self) -> None:
        test_jr_pass_recommends_kansai_hiroshima_regional_pass()

    def test_05_jr_pass_worth_it(self) -> None:
        test_jr_pass_worth_it_for_heavy_shinkansen_itinerary()

    def test_06_rail_vs_air(self) -> None:
        test_rail_vs_air_comparisons()

    def test_07_ic_and_seasonal(self) -> None:
        test_ic_card_and_seasonal_guides()

    def test_08_cultural_etiquette(self) -> None:
        test_cultural_etiquette_topics()

    def test_09_scope_guardrail(self) -> None:
        test_scope_guardrail_rejects_non_japan_trips()

    def test_10_day_by_day_itinerary(self) -> None:
        test_day_by_day_itinerary_generation()


if __name__ == "__main__":
    unittest.main()
