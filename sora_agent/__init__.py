"""Sora: Japan-Specialist Travel Planning Agent package."""

from sora_agent.agent import (
    SORA_ROLE_HEADER,
    SORA_SYSTEM_PROMPT,
    create_sora_agent,
    render_tool_assisted_response,
    root_agent,
    run_sora_query,
)
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

__version__ = "1.0.0"

__all__ = [
    "ALL_SORA_TOOLS",
    "SORA_ROLE_HEADER",
    "SORA_SYSTEM_PROMPT",
    "calculate_jr_pass_value",
    "check_japan_destination_scope",
    "compare_rail_vs_air",
    "create_sora_agent",
    "generate_day_by_day_itinerary_template",
    "get_cultural_etiquette_and_logistics",
    "get_ic_card_and_transit_guide",
    "get_seasonal_travel_guide",
    "render_tool_assisted_response",
    "root_agent",
    "run_sora_query",
]
