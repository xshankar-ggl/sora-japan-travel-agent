"""Strict Pydantic v2 and TypedDict JSON schemas for Sora tools, memory, orchestration, and observability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Literal, TypedDict

try:
    from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

    HAS_PYDANTIC = True
except ImportError:  # pragma: no cover - lightweight compatibility shim for bare stdlib environments
    HAS_PYDANTIC = False

    class ValidationError(ValueError):  # type: ignore[no-redef]
        """Fallback validation error when Pydantic is unavailable."""

    def ConfigDict(**kwargs: Any) -> dict[str, Any]:  # type: ignore[no-redef]
        return dict(kwargs)

    def Field(default: Any = None, *, default_factory: Any = None, **kwargs: Any) -> Any:  # type: ignore[no-redef]
        return default_factory if default_factory is not None else default

    def field_validator(*fields: str, **kwargs: Any) -> Any:  # type: ignore[no-redef]
        def _decorator(fn: Any) -> Any:
            return classmethod(fn) if not isinstance(fn, classmethod) else fn

        return _decorator

    class BaseModel:  # type: ignore[no-redef]
        """Minimal Pydantic BaseModel compatibility layer for stdlib-only test runners."""

        def __init__(self, **data: Any) -> None:
            annotations: dict[str, Any] = {}
            for cls in reversed(self.__class__.__mro__):
                annotations.update(getattr(cls, "__annotations__", {}))
            for key in annotations:
                if key in data:
                    setattr(self, key, data[key])
                elif hasattr(self.__class__, key):
                    attr = getattr(self.__class__, key)
                    setattr(self, key, attr() if callable(attr) else attr)
                else:
                    setattr(self, key, None)
            for key, value in data.items():
                setattr(self, key, value)

        def model_dump(self) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in self.__dict__.items():
                if key.startswith("_"):
                    continue
                if isinstance(value, BaseModel):
                    result[key] = value.model_dump()
                elif isinstance(value, list):
                    result[key] = [
                        item.model_dump() if isinstance(item, BaseModel) else item
                        for item in value
                    ]
                elif isinstance(value, dict):
                    result[key] = {
                        k: (v.model_dump() if isinstance(v, BaseModel) else v)
                        for k, v in value.items()
                    }
                else:
                    result[key] = value
            return result

        @classmethod
        def model_json_schema(cls) -> dict[str, Any]:
            return {
                "title": cls.__name__,
                "type": "object",
                "properties": {k: {"type": str(v)} for k, v in getattr(cls, "__annotations__", {}).items()},
            }


class StrictToolOutputModel(BaseModel):
    """Base Pydantic schema for all Sora tool outputs.

    Enforces strict JSON schema serialization while also supporting mapping-style key access
    (`result["field"]`) for seamless interoperability across Google ADK, FastAPI, and test suites.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    def to_dict(self) -> dict[str, Any]:
        """Serializes the Pydantic model into a plain JSON-compatible dictionary."""
        return self.model_dump()

    def __getitem__(self, key: str) -> Any:
        dump = self.model_dump()
        if key not in dump:
            raise KeyError(key)
        return dump[key]

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key in self.model_dump()

    def get(self, key: str, default: Any = None) -> Any:
        return self.model_dump().get(key, default)

    def keys(self) -> Any:
        return self.model_dump().keys()

    def items(self) -> Any:
        return self.model_dump().items()

    def values(self) -> Any:
        return self.model_dump().values()

    def __iter__(self) -> Iterator[str]:
        return iter(self.model_dump())


# ============================================================================
# 1. Guided Error Recovery Schemas (Instructing the LLM how to self-correct)
# ============================================================================


class ErrorRecoveryGuidanceDict(TypedDict):
    """TypedDict representation of guided LLM error recovery metadata."""

    error_code: str
    error_message: str
    invalid_parameter: str
    provided_value: str
    allowed_values: list[str]
    llm_recovery_instruction: str
    suggested_tool_call_example: str


class ErrorRecoveryGuidance(StrictToolOutputModel):
    """Actionable error recovery schema that instructs the LLM on how to fix invalid tool inputs."""

    error_code: str = Field(..., description="Machine-readable error code (e.g., INVALID_DURATION_DAYS).")
    error_message: str = Field(..., description="Clear human- and LLM-readable explanation of the validation error.")
    invalid_parameter: str = Field(..., description="Name of the parameter that failed validation.")
    provided_value: str = Field(..., description="String representation of the invalid value passed by the caller.")
    allowed_values: list[str] = Field(
        default_factory=list,
        description="Explicit list of valid values or patterns accepted by this parameter.",
    )
    llm_recovery_instruction: str = Field(
        ...,
        description=(
            "Direct instruction to the LLM explaining how to reformulate the tool call with valid arguments "
            "or what clarifying question to ask the traveler."
        ),
    )
    suggested_tool_call_example: str = Field(
        ...,
        description="Concrete example of a valid invocation of this tool.",
    )


# ============================================================================
# 2. Tool Input Validation Schemas
# ============================================================================


class JRPassCalculationInput(BaseModel):
    """Strict input validation schema for `calculate_jr_pass_value`."""

    model_config = ConfigDict(extra="forbid")

    legs: list[str] = Field(
        ...,
        min_length=1,
        description="Non-empty ordered list of intercity rail legs formatted as 'Origin -> Destination'.",
    )
    duration_days: Literal[7, 14, 21] = Field(
        default=7,
        description="Official National JR Pass duration in days. Must be exactly 7, 14, or 21.",
    )
    pass_class: Literal["ordinary", "green"] = Field(
        default="ordinary",
        description="JR Pass car class: 'ordinary' (standard reserved) or 'green' (first class).",
    )


class RailVsAirComparisonInput(BaseModel):
    """Strict input validation schema for `compare_rail_vs_air`."""

    model_config = ConfigDict(extra="forbid")

    origin: str = Field(..., min_length=2, description="Origin city in Japan (e.g., 'Tokyo', 'Osaka').")
    destination: str = Field(
        ..., min_length=2, description="Destination city in Japan (e.g., 'Fukuoka', 'Sapporo', 'Hiroshima')."
    )


class ICCardTransitGuideInput(BaseModel):
    """Strict input validation schema for `get_ic_card_and_transit_guide`."""

    model_config = ConfigDict(extra="forbid")

    arrival_airport: str = Field(
        default="HND",
        description="Arrival airport IATA code or Japanese city (HND, NRT, KIX, ITM, NGO, FUK, CTS, OKA).",
    )
    regions: list[str] | None = Field(
        default=None,
        description="Optional list of Japanese regions or cities in the itinerary.",
    )
    has_iphone: bool = Field(
        default=True,
        description="True if the traveler has an iPhone / Apple Watch supporting Apple Wallet Transit Cards.",
    )


class SeasonalTravelGuideInput(BaseModel):
    """Strict input validation schema for `get_seasonal_travel_guide`."""

    model_config = ConfigDict(extra="forbid")

    month: int = Field(
        ...,
        ge=1,
        le=12,
        description="Calendar month as an integer strictly between 1 (January) and 12 (December).",
    )
    regions: list[str] | None = Field(
        default=None,
        description="Optional list of Japanese regions to tailor seasonal advice.",
    )


class CulturalEtiquetteInput(BaseModel):
    """Strict input validation schema for `get_cultural_etiquette_and_logistics`."""

    model_config = ConfigDict(extra="forbid")

    topic: Literal[
        "ryokan_onsen",
        "konbini",
        "shrines_temples_dining",
        "luggage_connectivity",
        "all",
    ] = Field(
        default="all",
        description="Specific cultural/logistics domain to retrieve.",
    )


classItineraryPaceLiteral = Literal["relaxed", "moderate", "packed"]


class ItineraryTemplateInput(BaseModel):
    """Strict input validation schema for `generate_day_by_day_itinerary_template`."""

    model_config = ConfigDict(extra="forbid")

    days: int = Field(
        default=7,
        ge=1,
        le=21,
        description="Total itinerary length in days, strictly between 1 and 21.",
    )
    cities: list[str] | None = Field(
        default=None,
        description="Ordered list of Japanese cities to visit.",
    )
    month: int = Field(
        default=4,
        ge=1,
        le=12,
        description="Month of travel (1 to 12).",
    )
    pace: Literal["relaxed", "moderate", "packed"] = Field(
        default="moderate",
        description="Daily itinerary pacing ('relaxed', 'moderate', or 'packed').",
    )


# ============================================================================
# 3. Strict Tool Output Schemas (Pydantic BaseModel + TypedDict)
# ============================================================================


class AnalyzedRailLegDict(TypedDict):
    leg: str
    fare_jpy: int
    duration_mins: int
    train_name: str
    nozomi_supplement_jpy: int
    scenic_tip: str


class AnalyzedRailLegSchema(StrictToolOutputModel):
    """Schema for a single evaluated Shinkansen or Limited Express rail leg."""

    leg: str = Field(..., description="Formatted origin -> destination leg string.")
    fare_jpy: int = Field(..., ge=0, description="Point-to-point fare in Japanese Yen (JPY).")
    duration_mins: int = Field(..., ge=0, description="Approximate rail duration in minutes.")
    train_name: str = Field(..., description="Shinkansen or Limited Express service names.")
    nozomi_supplement_jpy: int = Field(
        default=0,
        ge=0,
        description="Supplemental Nozomi/Mizuho upgrade ticket price in JPY required for National JR Pass holders.",
    )
    scenic_tip: str = Field(..., description="Actionable boarding, seat, or transfer tip for this leg.")


class RegionalPassRecommendationDict(TypedDict, total=False):
    pass_name: str
    price_jpy: int
    duration_days: int
    hybrid_total_jpy: int | None
    estimated_kansai_hiroshima_leg_value_jpy: int | None
    why_it_wins: str


class RegionalPassRecommendationSchema(StrictToolOutputModel):
    """Schema for a Regional JR Pass recommendation."""

    pass_name: str = Field(..., description="Official name of the Regional JR Pass.")
    price_jpy: int = Field(..., ge=0, description="Official pass price in JPY.")
    duration_days: int = Field(..., ge=1, description="Validity window in consecutive days.")
    hybrid_total_jpy: int | None = Field(
        default=None,
        description="Estimated total cost combining this regional pass with point-to-point tickets.",
    )
    estimated_kansai_hiroshima_leg_value_jpy: int | None = Field(
        default=None,
        description="Value of legs covered by the regional pass in JPY.",
    )
    why_it_wins: str = Field(..., description="Explanation of why this regional pass outperforms the National Pass.")


class JRPassCalculationOutputDict(TypedDict):
    status: Literal["success", "error"]
    verdict: Literal["WORTH_IT", "REGIONAL_PASS_BETTER", "BUY_INDIVIDUAL_TICKETS", "INVALID_INPUT"]
    summary: str
    pass_evaluated: str
    national_pass_cost_jpy: int
    individual_tickets_total_jpy: int
    net_savings_with_national_pass_jpy: int
    nozomi_supplement_warning: str
    regional_pass_recommendations: list[RegionalPassRecommendationDict]
    itemized_legs: list[AnalyzedRailLegDict]
    error_recovery: ErrorRecoveryGuidanceDict | None


class JRPassCalculationOutput(StrictToolOutputModel):
    """Strict output schema for `calculate_jr_pass_value`."""

    status: Literal["success", "error"] = Field(default="success", description="Tool execution status.")
    verdict: Literal["WORTH_IT", "REGIONAL_PASS_BETTER", "BUY_INDIVIDUAL_TICKETS", "INVALID_INPUT"] = Field(
        ..., description="Cost-benefit recommendation verdict."
    )
    summary: str = Field(..., description="Concise summary of the JR Pass math and recommendation.")
    pass_evaluated: str = Field(..., description="Name and class of the National JR Pass evaluated.")
    national_pass_cost_jpy: int = Field(..., ge=0, description="Post-Oct-2023 National JR Pass cost in JPY.")
    individual_tickets_total_jpy: int = Field(..., ge=0, description="Sum of point-to-point rail tickets in JPY.")
    net_savings_with_national_pass_jpy: int = Field(
        ..., description="Net savings (positive) or overpayment loss (negative) in JPY."
    )
    nozomi_supplement_warning: str = Field(
        ..., description="Explanation of Nozomi/Mizuho upgrade fee mechanics."
    )
    regional_pass_recommendations: list[RegionalPassRecommendationSchema] = Field(
        default_factory=list,
        description="List of higher-value regional rail passes applicable to the route.",
    )
    itemized_legs: list[AnalyzedRailLegSchema] = Field(
        default_factory=list,
        description="Itemized breakdown of each rail leg.",
    )
    error_recovery: ErrorRecoveryGuidance | None = Field(
        default=None,
        description="Populated with LLM recovery instructions when status == 'error'.",
    )


class TransitModeDetailsSchema(StrictToolOutputModel):
    """Detailed metrics for either the Rail or Domestic Air option on an intercity corridor."""

    mode: str = Field(..., description="Primary transit service or carrier names.")
    station_to_station_mins: int | None = Field(default=None, description="In-vehicle rail travel time in minutes.")
    airport_to_airport_mins: int | None = Field(default=None, description="In-air flight block time in minutes.")
    door_to_door_mins: int = Field(..., ge=0, description="Realistic city-center to city-center total duration.")
    cost_jpy_range: str = Field(..., description="Typical one-way fare range in JPY.")
    airport_transfer_note: str | None = Field(default=None, description="Airport ground transfer timing and cost.")
    pros: list[str] = Field(default_factory=list, description="Key advantages of this mode.")
    cons: list[str] = Field(default_factory=list, description="Key drawbacks of this mode.")
    scenic_tip: str | None = Field(default=None, description="Optional scenic or boarding tip.")


class RailVsAirComparisonOutput(StrictToolOutputModel):
    """Strict output schema for `compare_rail_vs_air`."""

    status: Literal["success", "error"] = Field(default="success", description="Tool execution status.")
    corridor: str = Field(..., description="Origin <-> Destination corridor label.")
    winner: Literal["rail", "air", "either_or_hybrid", "invalid_input"] = Field(
        ..., description="Recommended travel mode for this corridor."
    )
    headline: str = Field(..., description="Top-level recommendation summary.")
    rail_details: TransitModeDetailsSchema = Field(..., description="Shinkansen / Limited Express rail details.")
    air_details: TransitModeDetailsSchema = Field(..., description="Domestic flight details.")
    luggage_note: str = Field(..., description="Comparison of Shinkansen 160cm rule vs. airline baggage limits.")
    error_recovery: ErrorRecoveryGuidance | None = Field(
        default=None,
        description="Populated with LLM recovery instructions when status == 'error'.",
    )


class ICCardTransitGuideOutput(StrictToolOutputModel):
    """Strict output schema for `get_ic_card_and_transit_guide`."""

    status: Literal["success", "error"] = Field(default="success", description="Tool execution status.")
    primary_ic_card_recommendation: str = Field(..., description="Recommended IC card provisioning workflow.")
    nationwide_interoperability: str = Field(..., description="Explanation of the 10-card nationwide IC network.")
    arrival_airport_transfer: str = Field(..., description="Specific rail/bus transfer guide from arrival airport.")
    smartex_shinkansen_tip: str = Field(..., description="How to link IC card to SmartEX for ticketless boarding.")
    critical_exceptions: list[str] = Field(
        default_factory=list,
        description="Important transit edge cases where IC cards cannot be tapped directly.",
    )
    regions_requested: list[str] = Field(default_factory=list, description="Regions covered by this transit guide.")
    error_recovery: ErrorRecoveryGuidance | None = Field(
        default=None,
        description="Populated with LLM recovery instructions when status == 'error'.",
    )


class SeasonalTravelGuideOutput(StrictToolOutputModel):
    """Strict output schema for `get_seasonal_travel_guide`."""

    status: Literal["success", "error"] = Field(default="success", description="Tool execution status.")
    month: int = Field(..., description="Evaluated month (1-12), or 0 if invalid.")
    season: str = Field(..., description="Season name and Japanese seasonal theme.")
    weather_summary: str = Field(..., description="Temperature and precipitation summary across regions.")
    crowd_alerts: str = Field(..., description="Major Japanese national holidays or peak crowd alerts.")
    highlights: list[str] = Field(default_factory=list, description="Top seasonal experiences and festivals.")
    seasonal_foods: list[str] = Field(default_factory=list, description="In-season Japanese culinary specialties (shun).")
    packing_tips: list[str] = Field(default_factory=list, description="Actionable packing recommendations.")
    regions_considered: list[str] = Field(default_factory=list, description="Regions evaluated.")
    error_recovery: ErrorRecoveryGuidance | None = Field(
        default=None,
        description="Populated with LLM recovery instructions when status == 'error'.",
    )


class CulturalTopicSectionSchema(StrictToolOutputModel):
    """Schema for a single cultural etiquette & logistics topic."""

    title: str = Field(..., description="Human-readable topic title.")
    golden_rules: list[str] = Field(default_factory=list, description="Actionable etiquette and logistics rules.")


class CulturalEtiquetteOutput(StrictToolOutputModel):
    """Strict output schema for `get_cultural_etiquette_and_logistics`."""

    status: Literal["success", "error"] = Field(default="success", description="Tool execution status.")
    topic_requested: str = Field(..., description="Topic requested by the caller.")
    ryokan_onsen: CulturalTopicSectionSchema | None = Field(default=None)
    konbini: CulturalTopicSectionSchema | None = Field(default=None)
    shrines_temples_dining: CulturalTopicSectionSchema | None = Field(default=None)
    luggage_connectivity: CulturalTopicSectionSchema | None = Field(default=None)
    error_recovery: ErrorRecoveryGuidance | None = Field(
        default=None,
        description="Populated with LLM recovery instructions when status == 'error'.",
    )


class DestinationScopeOutput(StrictToolOutputModel):
    """Strict output schema for `check_japan_destination_scope`."""

    status: Literal["success", "error"] = Field(default="success", description="Tool execution status.")
    is_japan_only: bool = Field(..., description="True if no out-of-scope non-Japan destinations were detected.")
    detected_non_japan_destinations: list[str] = Field(
        default_factory=list,
        description="List of non-Japan destinations detected in the query.",
    )
    detected_japan_destinations: list[str] = Field(
        default_factory=list,
        description="List of valid Japanese cities/regions detected in the query.",
    )
    policy_reminder: str = Field(..., description="Instruction on how Sora must handle scope boundaries.")
    error_recovery: ErrorRecoveryGuidance | None = Field(
        default=None,
        description="Populated with LLM recovery instructions when status == 'error'.",
    )


class DailyPlanBlockSchema(StrictToolOutputModel):
    """Schema for a single day inside a generated day-by-day Japan itinerary."""

    day: int = Field(..., ge=1, description="1-indexed day number of the itinerary.")
    base_city: str = Field(..., description="Overnight base city in Japan.")
    theme: str = Field(..., description="Neighborhood cluster theme for the day.")
    intercity_transition: str | None = Field(default=None, description="Shinkansen/rail transfer details if changing cities.")
    luggage_strategy: str | None = Field(default=None, description="Takkyubin or 160cm baggage rule guidance.")
    morning: str = Field(..., description="Morning neighborhood cluster activities.")
    afternoon: str = Field(..., description="Afternoon neighborhood cluster activities.")
    evening: str = Field(..., description="Evening dining and neighborhood ambiance.")
    local_transit_tip: str = Field(..., description="Specific metro, JR, or bus guidance.")
    cultural_etiquette_tip: str = Field(..., description="Daily cultural etiquette or konbini tip.")


class ItineraryTemplateOutput(StrictToolOutputModel):
    """Strict output schema for `generate_day_by_day_itinerary_template`."""

    status: Literal["success", "error"] = Field(default="success", description="Tool execution status.")
    trip_days: int = Field(..., ge=0, description="Total number of itinerary days.")
    pace: str = Field(..., description="Selected travel pace ('relaxed', 'moderate', or 'packed').")
    cities_in_order: list[str] = Field(default_factory=list, description="Contiguous ordered list of base cities.")
    seasonal_context: SeasonalTravelGuideOutput | None = Field(
        default=None, description="Month-specific seasonal travel context."
    )
    jr_pass_recommendation: JRPassCalculationOutput | None = Field(
        default=None, description="JR Pass cost-benefit evaluation for the itinerary's rail legs."
    )
    day_by_day_plan: list[DailyPlanBlockSchema] = Field(
        default_factory=list, description="Structured day-by-day schedule."
    )
    error_recovery: ErrorRecoveryGuidance | None = Field(
        default=None,
        description="Populated with LLM recovery instructions when status == 'error'.",
    )


class HighStakesBookingOutput(StrictToolOutputModel):
    """Strict output schema for HITL-gated booking/reservation actions."""

    status: Literal["pending_human_approval", "approved", "rejected", "error"] = Field(
        ..., description="Current state of the human-in-the-loop confirmation workflow."
    )
    requires_human_confirmation: bool = Field(
        default=True,
        description="Always True for financial, non-refundable, or reservation commitments.",
    )
    confirmation_id: str = Field(..., description="Unique tracking ID for the pending confirmation hook.")
    action_type: str = Field(..., description="Category of high-stakes action.")
    item_description: str = Field(..., description="Detailed description of the reservation or purchase.")
    estimated_total_jpy: int = Field(..., ge=0, description="Total financial commitment in JPY.")
    cancellation_policy_warning: str = Field(..., description="Disclosure of cancellation or non-refundable rules.")
    approval_instructions: str = Field(
        ...,
        description="Instructions for the human traveler or operator to approve or reject the action.",
    )
    error_recovery: ErrorRecoveryGuidance | None = Field(
        default=None,
        description="Populated with LLM recovery instructions when status == 'error'.",
    )


__all__ = [
    "AnalyzedRailLegDict",
    "AnalyzedRailLegSchema",
    "CulturalEtiquetteInput",
    "CulturalEtiquetteOutput",
    "CulturalTopicSectionSchema",
    "DailyPlanBlockSchema",
    "DestinationScopeOutput",
    "ErrorRecoveryGuidance",
    "ErrorRecoveryGuidanceDict",
    "HAS_PYDANTIC",
    "HighStakesBookingOutput",
    "ICCardTransitGuideInput",
    "ICCardTransitGuideOutput",
    "ItineraryTemplateInput",
    "ItineraryTemplateOutput",
    "JRPassCalculationInput",
    "JRPassCalculationOutput",
    "JRPassCalculationOutputDict",
    "RailVsAirComparisonInput",
    "RailVsAirComparisonOutput",
    "RegionalPassRecommendationDict",
    "RegionalPassRecommendationSchema",
    "SeasonalTravelGuideInput",
    "SeasonalTravelGuideOutput",
    "StrictToolOutputModel",
    "TransitModeDetailsSchema",
    "ValidationError",
]
