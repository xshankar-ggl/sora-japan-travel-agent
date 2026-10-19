# ⛩️ Sora (空) — Japan-Specialist Travel Planning Agent

> **ROLE**
> You are **Sora**, a Japan-specialist travel planning agent. You design day-by-day itineraries for travelers visiting Japan. You are not a general world-travel agent — all recommendations, logistics, and cultural guidance are Japan-specific (JR Pass mechanics, IC cards, ryokan etiquette, konbini culture, seasonal travel, regional rail vs. domestic air).

**Sora** is a production-ready AI travel planning agent built with **Google ADK (Agent Development Kit)** and the **Google Gemini API**. It combines LLM reasoning with deterministic Japan-domain tools so that Shinkansen fares, post-October-2023 JR Pass break-even calculations, regional rail passes, door-to-door rail vs. flight comparisons, and cultural etiquette are always accurate.

---

## ✨ Key Features & Japan-Specific Capabilities

1. **🚅 Post-2023 JR Pass & Regional Pass Calculator (`calculate_jr_pass_value`)**
   - Evaluates itemized Shinkansen & Limited Express legs against the updated National JR Pass prices (**7-Day: ¥50,000**, **14-Day: ¥80,000**, **21-Day: ¥100,000** Ordinary; **¥70,000 / ¥110,000 / ¥140,000** Green Car).
   - Flags **Nozomi / Mizuho supplemental upgrade fees** and automatically recommends higher-value **Regional Passes** (such as the *JR West Kansai-Hiroshima Area Pass* at ¥17,000 or *Hokuriku Arch Pass* at ¥30,000) or individual **SmartEX** tickets when the National Pass doesn't pay off.

2. **✈️ vs. 🚅 Regional Rail vs. Domestic Air Comparator (`compare_rail_vs_air`)**
   - Compares station-to-station vs. realistic **door-to-door** travel times, fare ranges, airport transfer durations (e.g., Fukuoka Airport's 5-minute subway to Hakata vs. Hiroshima Airport's 50-minute bus), and the **160cm Shinkansen oversized baggage rule**.

3. **💳 IC Card & Local Transit Mechanics (`get_ic_card_and_transit_guide`)**
   - Guides travelers through **Apple Wallet Mobile Suica / PASMO / ICOCA** (with Express Transit Mode), physical **Welcome Suica / ICOCA** cards, **SmartEX IC card linkage** for ticketless Shinkansen boarding, and regional cash/contactless exceptions.

4. **🌸 12-Month Seasonal Travel Calendar (`get_seasonal_travel_guide`)**
   - Covers month-by-month weather, *Sakura* (cherry blossom) and *Koyo* (autumn foliage) windows by region, *Tsuyu* rainy season nuances (including Hokkaido's dry June), peak domestic travel alerts (**Golden Week, Obon, Shogatsu**), seasonal cuisine (*shun*), and packing lists.

5. **♨️ Ryokan, Onsen, Konbini & Cultural Etiquette (`get_cultural_etiquette_and_logistics`)**
   - Deep-dive guidance on ryokan *kaiseki* timing, wearing *yukata* (left over right), onsen bathing rituals & tattoo-friendly options (*Kinosaki Onsen*, *Beppu*, private *kashikiri* baths), konbini favorites (7-Eleven, FamilyMart, Lawson, 7-Bank ATMs), Shinto 2-2-1 vs. Buddhist temple etiquette, and **Yamato Takkyubin** luggage forwarding.

6. **🗓️ Geographically Clustered Day-by-Day Itinerary Engine (`generate_day_by_day_itinerary_template`)**
   - Prevents city zigzagging by grouping sights into walkable neighborhood clusters with morning/afternoon/evening pacing, luggage-forwarding checkpoints, and daily cultural tips.

7. **🛡️ Strict Japan-Only Scope Guardrail (`check_japan_destination_scope`)**
   - Politely declines non-Japan travel requests (e.g., Europe, Southeast Asia) while offering to plan the traveler's Japan journey.

---

## 📁 Project Structure (Root Repository)

```text
.
├── app.py                      # FastAPI Web UI & REST API server
├── pyproject.toml              # Package metadata, dependencies & `sora` CLI entrypoint
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variable template (GEMINI_API_KEY)
├── sora_agent/                 # Google ADK Agent package
│   ├── __init__.py             # Exports `root_agent` and tool functions
│   ├── agent.py                # ADK `Agent` definition & Gemini / offline execution engine
│   ├── cli.py                  # Interactive CLI & direct tool runner
│   ├── knowledge.py            # Curated Japan rail, air, seasonal & cultural knowledge base
│   ├── prompt.py               # Sora's system prompt & role definition
│   └── tools.py                # 7 Japan-specific tools for Google ADK
└── tests/
    └── test_sora_agent.py      # Pytest evaluation & unit test suite
```

---

## 🚀 Quickstart

### 1. Clone & Install

```bash
git clone https://github.com/xshankar-ggl/sora-japan-travel-agent.git
cd sora-japan-travel-agent

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure Your Gemini API Key (Optional for Offline Tool Mode, Required for Live Gemini LLM)

```bash
cp .env.example .env
export GEMINI_API_KEY="your-gemini-api-key"
```

---

## 💻 Usage

### Option A: Interactive CLI & Demo Modes

```bash
# Run a full showcase demo (8-day November itinerary: Tokyo -> Hakone -> Kyoto -> Hiroshima)
python3 -m sora_agent.cli --demo

# Ask Sora a custom itinerary prompt
python3 -m sora_agent.cli --prompt "Plan a 7-day April cherry blossom trip for Tokyo, Kanazawa, and Kyoto"

# Run the JR Pass Cost-Benefit Calculator directly
python3 -m sora_agent.cli --jr-pass "Tokyo -> Kyoto, Kyoto -> Hiroshima, Hiroshima -> Osaka, Osaka -> Tokyo" --days 7

# Compare Regional Rail vs. Domestic Air
python3 -m sora_agent.cli --rail-vs-air Tokyo Fukuoka

# Start an interactive chat session in your terminal
python3 -m sora_agent.cli
```

### Option B: Google ADK CLI / ADK Web UI

Because `sora_agent` exports `root_agent` following the standard Google ADK convention, you can run it directly with ADK:

```bash
adk run sora_agent
# or launch the Google ADK Web UI:
adk web
```

### Option C: Sora FastAPI Web Application

Launch the interactive Japan Travel Planner Web UI (includes Itinerary Chat, JR Pass Calculator, Rail vs. Air Comparator, and Etiquette Explorer):

```bash
python3 app.py
# Open http://127.0.0.1:8000 in your browser
```

---

## 🧪 Running the Test & Evaluation Suite

```bash
pytest -v
```
