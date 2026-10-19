# ⛩️ Sora (空) — Japan-Specialist Travel Planning Agent

> **ROLE**
> You are **Sora**, a Japan-specialist travel planning agent. You design day-by-day itineraries for travelers visiting Japan. You are not a general world-travel agent — all recommendations, logistics, and cultural guidance are Japan-specific (JR Pass mechanics, IC cards, ryokan etiquette, konbini culture, seasonal travel, regional rail vs. domestic air).

**Sora** is an enterprise-grade, multi-agent AI travel planning system built with **Google ADK (Agent Development Kit)**, the **Google Gemini API**, **OpenTelemetry**, **SQLite + Vector Memory**, **Google Cloud Secret Manager**, and **Terraform**.

---

## 🏗️ Enterprise Architecture across the 5 Evaluation Pillars

### 1. 🛠️ Tool & Interface Design (`sora_agent/tools.py`, `sora_agent/schemas.py`)
- **Strict Pydantic v2 & `TypedDict` Output Schemas**: Every tool validates inputs and returns strict Pydantic `StrictToolOutputModel` (`BaseModel` with `ConfigDict(extra="forbid")`) and `TypedDict` schemas (`JRPassCalculationOutput`, `RailVsAirComparisonOutput`, `ICCardTransitGuideOutput`, `SeasonalTravelGuideOutput`, `CulturalEtiquetteOutput`, `DestinationScopeOutput`, `ItineraryTemplateOutput`, `HighStakesBookingOutput`, `ConfirmationDecisionOutput`)—never generic `dict[str, Any]`.
- **Guided Error Handling for Autonomous LLM Recovery**: Instead of silently clamping out-of-range inputs or falling back to defaults, invalid parameters return `status="error"` with a structured `ErrorRecoveryGuidance` payload containing `error_code`, `invalid_parameter`, `allowed_values`, `llm_recovery_instruction`, and `suggested_tool_call_example` so the LLM can self-correct and retry.

### 2. 🧠 Context & Memory (`sora_agent/memory.py`, `sora_agent/prompt.py`)
- **Persistent SQLite Session Database (`PersistentSessionMemoryManager`)**: Stores multi-turn sessions (`sessions`), conversation turns (`conversation_turns`), and pinned `TravelerProfileMemory` entities in SQLite with WAL concurrency (`SORA_SESSION_DB_PATH`).
- **Semantic Vector Store (`vector_memories`)**: Computes L2-normalized dense embeddings combining a 64-dimension Japan travel ontology with hashed n-gram features to perform cosine similarity retrieval (`search_semantic_memory` / `asearch_semantic_memory`).
- **Automated History Compaction**: Monitors active turn counts and token budgets (`estimate_token_count`). When thresholds are exceeded, `compact_session_history` / `acompact_session_history` folds older turns into a dense entity-preserving summary (`CompactedHistorySummary`) while retaining recent verbatim turns.
- **Asynchronous Non-Blocking Memory Operations**: Provides native `async/await` methods (`aget_session_state`, `aadd_turn`, `acompact_session_history`, `astore_semantic_memory`, `asearch_semantic_memory`, and `abuild_context_window` using `asyncio.gather`).

### 3. 🎼 Orchestration & Logic (`sora_agent/orchestration.py`, `sora_agent/guardrails.py`, `sora_agent/hitl.py`)
- **Hierarchical Multi-Agent Architecture**: `root_agent` (`sora_japan_travel_agent`) coordinates 4 specialist Google ADK sub-agents:
  1. `rail_and_transit_specialist` (Post-Oct-2023 JR Pass math, Regional Passes, Rail vs. Air, IC cards)
  2. `cultural_and_seasonal_specialist` (12-month seasonal calendar, ryokan/onsen tattoo etiquette, konbini, Takkyubin)
  3. `itinerary_architect_specialist` (Geographically clustered day-by-day itineraries & HITL booking staging)
  4. `safety_and_critic_specialist` (Scope verification & rubric self-evaluation critic)
- **Strategic Model Routing (`StrategicModelRouter`)**: Dynamically routes tasks across `gemini-2.5-flash-lite` (low-latency lookups, scope checks, compaction), `gemini-2.5-flash` (standard multi-tool execution), and `gemini-2.5-pro` (complex multi-city day-by-day itinerary synthesis & reasoning) with automatic fallback chains.
- **Cloud-Native & Agentic Self-Eval Guardrails (`DefenseInDepthGuardrailEngine`)**:
  - **Layer 1**: Prompt-injection defense, PII redaction, and strict Japan-only destination scope enforcement.
  - **Layer 2**: Cloud-native Vertex AI / Gemini `SafetySetting` (`BLOCK_LOW_AND_ABOVE` across all 4 harm categories) and Google Cloud Model Armor policy configuration.
  - **Layer 3**: **Agentic Self-Evaluation Critic Loop** (`evaluate_itinerary_quality`) auditing responses against a 5-point Japan Specialist rubric and automatically refining drafts before returning to the user.
- **Human-in-the-Loop (HITL) Confirmation Hooks (`HumanInTheLoopManager`)**: High-stakes actions (`BOOK_RYOKAN_KAISEKI`, `PURCHASE_JR_PASS`, `RESERVE_SHINKANSEN_OVERSIZED_BAGGAGE`, `SCHEDULE_TAKKYUBIN_LUGGAGE`, `CHARGE_IC_CARD_WALLET`) are intercepted by `@require_human_confirmation` and ADK `before_tool_callback`, staging a `PENDING_HUMAN_APPROVAL` record (`request_high_stakes_booking_confirmation`) that cannot execute until explicitly approved via `resolve_booking_confirmation`.

### 4. 📊 Observability & Tracing (`sora_agent/observability.py`)
- **Structured JSON Logging (`StructuredJSONLogger`)**: Emits Google Cloud Logging-compatible JSON records correlated with `logging.googleapis.com/trace` and `logging.googleapis.com/spanId`.
- **OpenTelemetry Distributed Tracing (`DistributedTracer`, `@trace_span`)**: Captures hierarchical parent/child spans with W3C `traceparent` headers (`00-<trace_id>-<span_id>-01`) and millisecond latency tracking across every tool, memory query, guardrail, and model call.
- **Intent vs. Outcome Tracking (`IntentOutcomeTracker`)**: Classifies user intent and expected tools prior to execution and records actual outcome status, tool alignment score, self-evaluation score, and drift detection after execution.
- **Automatic PII Redaction (`PIIRedactor`)**: Scrubs emails, phone numbers, credit cards, passport numbers, government IDs, and IP addresses (`[REDACTED_*]`) across prompts, logs, trace attributes, and database records.

### 5. ☁️ Infrastructure & CI/CD (`terraform/`, `sora_agent/secrets.py`, `Dockerfile`, `cloudbuild.yaml`, `.github/workflows/ci.yml`)
- **Dedicated Google Cloud Secret Manager Service (`SecretManagerService`)**: Resolves `sora-gemini-api-key` directly from Google Cloud Secret Manager (`projects/*/secrets/*/versions/latest`) with in-memory TTL caching, key rotation invalidation, and local development fallback.
- **Terraform Infrastructure as Code (`terraform/main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`)**: Provisions GCP APIs, a least-privilege IAM Service Account, Secret Manager secrets & IAM bindings, Artifact Registry, and a Cloud Run v2 service with Secret Manager mounting and health probes.
- **Automated CI/CD & Pytest Evaluation Suite**: GitHub Actions (`.github/workflows/ci.yml`) and Cloud Build (`cloudbuild.yaml`) run the 18-test `pytest` evaluation suite and validate Terraform IaC on every push.

---

## 📁 Project Structure

```text
.
├── app.py                          # Async FastAPI Web UI & REST API server with strict Pydantic models
├── Dockerfile                      # Hardened non-root Python 3.11 container image
├── cloudbuild.yaml                 # Google Cloud Build CI/CD pipeline
├── pyproject.toml                  # Package metadata, dependencies & `sora` CLI entrypoint
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment & GCP Secret Manager template
├── .github/workflows/ci.yml        # GitHub Actions CI/CD (Pytest + Terraform validate)
├── terraform/                      # Terraform Infrastructure as Code (IaC) for GCP
│   ├── main.tf                     # Cloud Run v2, Secret Manager, Artifact Registry & IAM
│   ├── variables.tf                # Configurable GCP project, region & scaling variables
│   ├── outputs.tf                  # Cloud Run URI, Service Account & Secret resource outputs
│   └── versions.tf                 # Terraform & Google provider version constraints
├── sora_agent/                     # Google ADK Multi-Agent package
│   ├── __init__.py                 # Package exports
│   ├── agent.py                    # Hierarchical ADK `root_agent` & async execution engine
│   ├── cli.py                      # Interactive CLI & direct tool runner
│   ├── guardrails.py               # Cloud-native safety, prompt-injection & self-eval critic guardrails
│   ├── hitl.py                     # Human-in-the-Loop (HITL) confirmation hooks & state machine
│   ├── knowledge.py                # Curated Japan rail, air, seasonal & cultural knowledge base
│   ├── memory.py                   # Async SQLite session store, vector memory & history compaction
│   ├── observability.py            # Structured JSON logging, OpenTelemetry tracing, PII redaction & intent tracking
│   ├── orchestration.py            # Specialist ADK sub-agents & Strategic Model Router
│   ├── prompt.py                   # Sora's system prompt & role definition
│   ├── schemas.py                  # Strict Pydantic v2 & TypedDict schemas + ErrorRecoveryGuidance
│   ├── secrets.py                  # Google Cloud Secret Manager client with TTL caching
│   └── tools.py                    # 9 Japan-specific tools with strict schemas & guided error recovery
└── tests/
    └── test_sora_agent.py          # 18-test Pytest & Unittest evaluation suite
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

### 2. Configure Google Cloud Secret Manager or Local API Key

```bash
cp .env.example .env
# Production (Google Cloud Secret Manager):
export GCP_PROJECT_ID="your-gcp-project-id"
export SORA_GEMINI_SECRET_ID="sora-gemini-api-key"

# Or Local Development Fallback:
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
```

### Option B: Google ADK CLI / ADK Web UI

```bash
adk run sora_agent
# or launch the Google ADK Web UI:
adk web
```

### Option C: Sora FastAPI Web Application

```bash
python3 app.py
# Open http://127.0.0.1:8000 in your browser
```

### Option D: Provision Cloud Infrastructure with Terraform

```bash
cd terraform
terraform init
terraform plan -var="project_id=your-gcp-project-id"
terraform apply -var="project_id=your-gcp-project-id"
```

---

## 🧪 Running the Test & Evaluation Suite

```bash
pytest -v
# or using standard library unittest:
python3 -m unittest discover -s tests -v
```
