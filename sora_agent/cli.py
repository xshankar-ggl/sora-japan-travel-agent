"""Interactive CLI for Sora, the Japan-specialist travel planning agent."""

from __future__ import annotations

import argparse
import json
import sys

from sora_agent.agent import run_sora_query
from sora_agent.tools import (
    calculate_jr_pass_value,
    compare_rail_vs_air,
    get_cultural_etiquette_and_logistics,
    get_ic_card_and_transit_guide,
    get_seasonal_travel_guide,
)

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel

    _CONSOLE = Console()
    HAS_RICH = True
except ImportError:
    _CONSOLE = None
    HAS_RICH = False


def _print_markdown(text: str, title: str | None = None) -> None:
    if HAS_RICH and _CONSOLE is not None:
        if title:
            _CONSOLE.print(Panel(Markdown(text), title=title, border_style="bright_red"))
        else:
            _CONSOLE.print(Markdown(text))
    else:
        if title:
            print(f"\n=== {title} ===")
        print(text)


def _print_json(data: object, title: str) -> None:
    formatted = json.dumps(data, indent=2, ensure_ascii=False)
    if HAS_RICH and _CONSOLE is not None:
        _CONSOLE.print(Panel(formatted, title=title, border_style="cyan"))
    else:
        print(f"\n=== {title} ===\n{formatted}")


def run_interactive_repl() -> None:
    """Starts an interactive terminal chat session with Sora."""
    welcome = (
        "**Konnichiwa! I am Sora (空), your Japan-specialist travel planning agent.**\n\n"
        "Ask me to design a day-by-day Japan itinerary, calculate whether a National or Regional JR Pass "
        "is worth it, compare Shinkansen vs. domestic flights, or explain ryokan, onsen, IC card, and "
        "konbini etiquette.\n\n"
        "*Type `exit` or `quit` to leave.*"
    )
    _print_markdown(welcome, title="🇯🇵 Sora — Japan Travel Specialist Agent")

    while True:
        try:
            user_input = input("\n🧳 You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSayonara! Safe travels in Japan! 🇯🇵")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "q"}:
            print("Sayonara! Safe travels in Japan! 🇯🇵")
            break

        response = run_sora_query(user_input)
        _print_markdown(response, title="🗾 Sora")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sora",
        description="Sora: Japan-Specialist Travel Planning Agent CLI",
    )
    parser.add_argument(
        "-p",
        "--prompt",
        type=str,
        help="Run a single travel planning prompt and print Sora's response.",
    )
    parser.add_argument(
        "--jr-pass",
        type=str,
        help="Comma-separated rail legs to evaluate for JR Pass value (e.g. 'Tokyo -> Kyoto, Kyoto -> Hiroshima, Hiroshima -> Tokyo').",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Pass or trip duration in days (default: 7).",
    )
    parser.add_argument(
        "--rail-vs-air",
        nargs=2,
        metavar=("ORIGIN", "DESTINATION"),
        help="Compare Shinkansen/rail vs. domestic air between two Japanese cities (e.g. Tokyo Fukuoka).",
    )
    parser.add_argument(
        "--season",
        type=int,
        choices=range(1, 13),
        metavar="MONTH",
        help="Get seasonal Japan travel guide for month 1..12.",
    )
    parser.add_argument(
        "--etiquette",
        type=str,
        choices=["ryokan_onsen", "konbini", "shrines_temples_dining", "luggage_connectivity", "all"],
        help="Display Japan cultural etiquette & logistics guide.",
    )
    parser.add_argument(
        "--ic-guide",
        type=str,
        metavar="AIRPORT",
        help="Display IC card (Suica/PASMO/ICOCA) & transit guide for arrival airport (HND, NRT, KIX, FUK).",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run a showcase demo of Sora's Japan itinerary planner & JR Pass calculator.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.jr_pass:
        legs = [leg.strip() for leg in args.jr_pass.split(",") if leg.strip()]
        result = calculate_jr_pass_value(legs=legs, duration_days=args.days)
        _print_json(result, title="🚅 Sora JR Pass Cost-Benefit Calculator")
        return 0

    if args.rail_vs_air:
        origin, dest = args.rail_vs_air
        result = compare_rail_vs_air(origin, dest)
        _print_json(result, title=f"🚅 vs ✈️ Rail vs. Domestic Air: {origin} <-> {dest}")
        return 0

    if args.season:
        result = get_seasonal_travel_guide(month=args.season)
        _print_json(result, title=f"🌸 Seasonal Guide — Month {args.season}")
        return 0

    if args.etiquette:
        result = get_cultural_etiquette_and_logistics(topic=args.etiquette)
        _print_json(result, title=f"🙇 Cultural Etiquette & Logistics — {args.etiquette}")
        return 0

    if args.ic_guide:
        result = get_ic_card_and_transit_guide(arrival_airport=args.ic_guide)
        _print_json(result, title=f"💳 IC Card & Transit Guide — {args.ic_guide}")
        return 0

    if args.demo:
        demo_prompt = (
            "Plan an 8-day autumn (November) itinerary visiting Tokyo, Hakone, Kyoto, and Hiroshima, "
            "and tell me if the 7-day JR Pass or a regional pass is better."
        )
        _print_markdown(f"**Demo Traveler Prompt:** *{demo_prompt}*", title="🎒 Traveler Request")
        response = run_sora_query(demo_prompt)
        _print_markdown(response, title="🗾 Sora's Japan-Specialist Response")
        return 0

    if args.prompt:
        response = run_sora_query(args.prompt)
        _print_markdown(response, title="🗾 Sora")
        return 0

    run_interactive_repl()
    return 0


if __name__ == "__main__":
    sys.exit(main())
