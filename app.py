"""FastAPI Web UI and REST API for Sora, the Japan-Specialist Travel Planning Agent."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from sora_agent.agent import SORA_ROLE_HEADER, run_sora_query
from sora_agent.tools import (
    calculate_jr_pass_value,
    compare_rail_vs_air,
    get_cultural_etiquette_and_logistics,
    get_ic_card_and_transit_guide,
    get_seasonal_travel_guide,
)

app = FastAPI(
    title="Sora — Japan-Specialist Travel Planning Agent",
    description=SORA_ROLE_HEADER,
    version="1.0.0",
)


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Traveler request or itinerary prompt for Sora.")


class JRPassRequest(BaseModel):
    legs: list[str] = Field(
        default_factory=lambda: ["Tokyo -> Kyoto", "Kyoto -> Hiroshima", "Hiroshima -> Osaka", "Osaka -> Tokyo"],
        description="Ordered list of rail legs.",
    )
    duration_days: int = Field(default=7, description="JR Pass duration (7, 14, or 21 days).")
    pass_class: str = Field(default="ordinary", description="ordinary or green.")


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "agent": "Sora", "specialty": "Japan Travel Planning"}


@app.post("/api/chat")
def chat_with_sora(req: ChatRequest) -> dict[str, str]:
    reply = run_sora_query(req.prompt)
    return {"prompt": req.prompt, "response": reply}


@app.post("/api/jr-pass")
def evaluate_jr_pass(req: JRPassRequest) -> dict:
    return calculate_jr_pass_value(
        legs=req.legs,
        duration_days=req.duration_days,
        pass_class=req.pass_class,
    )


@app.get("/api/rail-vs-air")
def rail_vs_air_endpoint(
    origin: str = Query("Tokyo"),
    destination: str = Query("Fukuoka"),
) -> dict:
    return compare_rail_vs_air(origin=origin, destination=destination)


@app.get("/api/season/{month}")
def season_endpoint(month: int) -> dict:
    return get_seasonal_travel_guide(month=month)


@app.get("/api/etiquette/{topic}")
def etiquette_endpoint(topic: str = "all") -> dict:
    return get_cultural_etiquette_and_logistics(topic=topic)


@app.get("/api/ic-guide")
def ic_guide_endpoint(
    airport: str = Query("HND"),
    has_iphone: bool = Query(True),
) -> dict:
    return get_ic_card_and_transit_guide(arrival_airport=airport, has_iphone=has_iphone)


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Sora (空) — Japan-Specialist Travel Planning Agent</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
    .prose h1 { font-size: 1.5rem; font-weight: 700; margin-top: 1rem; margin-bottom: 0.5rem; color: #991b1b; }
    .prose h2 { font-size: 1.25rem; font-weight: 700; margin-top: 1.25rem; margin-bottom: 0.5rem; color: #1e293b; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.25rem; }
    .prose h3 { font-size: 1.1rem; font-weight: 600; margin-top: 1rem; margin-bottom: 0.35rem; color: #b91c1c; }
    .prose ul { list-style-type: disc; padding-left: 1.5rem; margin-bottom: 0.75rem; }
    .prose li { margin-bottom: 0.25rem; }
    .prose p { margin-bottom: 0.75rem; line-height: 1.6; }
    .prose blockquote { border-left: 4px solid #dc2626; padding-left: 1rem; background: #fef2f2; padding: 0.5rem 1rem; border-radius: 0.375rem; margin: 0.75rem 0; }
    .prose code { background: #f1f5f9; padding: 0.15rem 0.35rem; border-radius: 0.25rem; font-size: 0.875rem; }
  </style>
</head>
<body class="bg-stone-50 text-slate-800 min-h-screen">
  <!-- Header -->
  <header class="bg-gradient-to-r from-red-800 via-red-700 to-rose-800 text-white shadow-lg">
    <div class="max-w-6xl mx-auto px-6 py-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
      <div>
        <div class="flex items-center gap-3">
          <span class="text-3xl">⛩️</span>
          <h1 class="text-2xl md:text-3xl font-bold tracking-tight">Sora (空) — Japan Travel Specialist Agent</h1>
        </div>
        <p class="text-red-100 text-sm mt-1">
          Day-by-day Japan itineraries • JR Pass Post-2023 Math • Suica/ICOCA • Ryokan & Konbini Etiquette • Shinkansen vs. Air
        </p>
      </div>
      <div class="flex items-center gap-2 text-xs bg-red-900/50 px-3 py-2 rounded-lg border border-red-400/30">
        <span class="inline-block w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
        <span>Google ADK + Gemini Specialist</span>
      </div>
    </div>
  </header>

  <!-- Main Content -->
  <main class="max-w-6xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-12 gap-8">
    <!-- Left Column: Interactive Itinerary Planner -->
    <section class="lg:col-span-7 space-y-6">
      <div class="bg-white rounded-2xl shadow-sm border border-stone-200 p-6">
        <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
          <span>🗾</span> Design Your Day-by-Day Japan Itinerary
        </h2>
        <p class="text-xs text-slate-500 mt-1">
          Try a preset prompt below or ask Sora anything about Japan travel logistics.
        </p>

        <div class="flex flex-wrap gap-2 mt-4">
          <button onclick="setPreset('Plan an 8-day November autumn foliage itinerary for Tokyo, Hakone, Kyoto, and Hiroshima, and tell me if the 7-day JR Pass or a regional pass is better.')"
            class="text-xs bg-red-50 hover:bg-red-100 text-red-800 border border-red-200 px-3 py-1.5 rounded-full transition">
            🍁 8-Day Autumn: Tokyo → Hakone → Kyoto → Hiroshima
          </button>
          <button onclick="setPreset('Plan a 7-day April cherry blossom trip visiting Tokyo, Kanazawa, and Kyoto with luggage forwarding and IC card advice.')"
            class="text-xs bg-pink-50 hover:bg-pink-100 text-pink-800 border border-pink-200 px-3 py-1.5 rounded-full transition">
            🌸 7-Day Hokuriku Arch: Tokyo → Kanazawa → Kyoto
          </button>
          <button onclick="setPreset('Plan a 6-day winter food & snow trip in January to Tokyo and Sapporo, comparing Shinkansen vs flying.')"
            class="text-xs bg-sky-50 hover:bg-sky-100 text-sky-800 border border-sky-200 px-3 py-1.5 rounded-full transition">
            ❄️ 6-Day Winter: Tokyo & Sapporo (Rail vs. Air)
          </button>
          <button onclick="setPreset('Plan a 5-day trip to Paris and Rome.')"
            class="text-xs bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 px-3 py-1.5 rounded-full transition">
            🛡️ Test Japan-Only Guardrail (Paris & Rome)
          </button>
        </div>

        <div class="mt-4">
          <textarea id="chatPrompt" rows="3"
            class="w-full rounded-xl border border-stone-300 p-3 text-sm focus:ring-2 focus:ring-red-600 focus:outline-none"
            placeholder="e.g., Plan a 10-day itinerary for Tokyo, Hakone, Kyoto, Osaka, and Hiroshima in October..."></textarea>
          <div class="mt-3 flex justify-end">
            <button id="sendBtn" onclick="sendChat()"
              class="bg-red-700 hover:bg-red-800 text-white font-semibold text-sm px-5 py-2.5 rounded-xl shadow transition">
              Ask Sora ✨
            </button>
          </div>
        </div>
      </div>

      <!-- Response Output Card -->
      <div class="bg-white rounded-2xl shadow-sm border border-stone-200 p-6">
        <div class="flex items-center justify-between border-b border-stone-100 pb-3 mb-4">
          <h3 class="font-bold text-slate-800 text-sm uppercase tracking-wider">Sora's Itinerary & Logistics Plan</h3>
          <span id="statusBadge" class="text-xs text-slate-400">Ready</span>
        </div>
        <div id="chatOutput" class="prose max-w-none text-sm text-slate-700">
          <p class="text-slate-400 italic">Select a preset above or enter your Japan travel plans to generate a complete day-by-day itinerary.</p>
        </div>
      </div>
    </section>

    <!-- Right Column: Specialist Japan Tools -->
    <aside class="lg:col-span-5 space-y-6">
      <!-- Tool 1: JR Pass Cost-Benefit Calculator -->
      <div class="bg-white rounded-2xl shadow-sm border border-stone-200 p-6">
        <h2 class="text-base font-bold text-slate-900 flex items-center gap-2">
          <span>🚅</span> JR Pass Calculator (Post-Oct 2023 Prices)
        </h2>
        <p class="text-xs text-slate-500 mt-1">
          Enter comma-separated rail legs to check National vs. Regional JR Pass value.
        </p>
        <input id="jrLegs" type="text"
          value="Tokyo -> Kyoto, Kyoto -> Hiroshima, Hiroshima -> Osaka, Osaka -> Tokyo"
          class="w-full mt-3 rounded-lg border border-stone-300 px-3 py-2 text-xs" />
        <div class="grid grid-cols-2 gap-3 mt-3">
          <select id="jrDays" class="rounded-lg border border-stone-300 px-3 py-2 text-xs">
            <option value="7">7-Day Pass (¥50,000 Ord)</option>
            <option value="14">14-Day Pass (¥80,000 Ord)</option>
            <option value="21">21-Day Pass (¥100,000 Ord)</option>
          </select>
          <select id="jrClass" class="rounded-lg border border-stone-300 px-3 py-2 text-xs">
            <option value="ordinary">Ordinary Car</option>
            <option value="green">Green Car (First Class)</option>
          </select>
        </div>
        <button onclick="calcJrPass()"
          class="w-full mt-3 bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold py-2 rounded-lg transition">
          Calculate JR Pass Value
        </button>
        <div id="jrOutput" class="mt-3 text-xs bg-stone-50 p-3 rounded-lg border border-stone-200 hidden"></div>
      </div>

      <!-- Tool 2: Rail vs Domestic Air Comparator -->
      <div class="bg-white rounded-2xl shadow-sm border border-stone-200 p-6">
        <h2 class="text-base font-bold text-slate-900 flex items-center gap-2">
          <span>✈️</span> Regional Rail vs. Domestic Air
        </h2>
        <div class="grid grid-cols-2 gap-3 mt-3">
          <select id="rvaOrigin" class="rounded-lg border border-stone-300 px-3 py-2 text-xs">
            <option value="Tokyo">From: Tokyo</option>
            <option value="Osaka">From: Osaka</option>
          </select>
          <select id="rvaDest" class="rounded-lg border border-stone-300 px-3 py-2 text-xs">
            <option value="Fukuoka">To: Fukuoka (Hakata)</option>
            <option value="Sapporo">To: Sapporo (Hokkaido)</option>
            <option value="Hiroshima">To: Hiroshima</option>
            <option value="Kyoto">To: Kyoto</option>
            <option value="Kanazawa">To: Kanazawa</option>
            <option value="Okinawa">To: Okinawa (Naha)</option>
          </select>
        </div>
        <button onclick="compareRailAir()"
          class="w-full mt-3 bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold py-2 rounded-lg transition">
          Compare Door-to-Door Time & Cost
        </button>
        <div id="rvaOutput" class="mt-3 text-xs bg-stone-50 p-3 rounded-lg border border-stone-200 hidden"></div>
      </div>

      <!-- Tool 3: Cultural Etiquette & Seasonal Lookup -->
      <div class="bg-white rounded-2xl shadow-sm border border-stone-200 p-6">
        <h2 class="text-base font-bold text-slate-900 flex items-center gap-2">
          <span>♨️</span> Japan Etiquette & Logistics Guide
        </h2>
        <div class="flex gap-2 mt-3">
          <select id="etiquetteTopic" class="flex-1 rounded-lg border border-stone-300 px-3 py-2 text-xs">
            <option value="ryokan_onsen">Ryokan & Onsen Etiquette (+ Tattoos)</option>
            <option value="konbini">Konbini Culture (7-Eleven / Lawson / FamilyMart)</option>
            <option value="shrines_temples_dining">Shrines vs. Temples & Dining</option>
            <option value="luggage_connectivity">Takkyubin Luggage & 160cm Shinkansen Rule</option>
          </select>
          <button onclick="loadEtiquette()"
            class="bg-red-700 hover:bg-red-800 text-white text-xs font-semibold px-4 py-2 rounded-lg transition">
            View
          </button>
        </div>
        <div id="etiquetteOutput" class="mt-3 text-xs bg-stone-50 p-3 rounded-lg border border-stone-200 hidden"></div>
      </div>
    </aside>
  </main>

  <script>
    function setPreset(text) {
      document.getElementById('chatPrompt').value = text;
      sendChat();
    }

    async function sendChat() {
      const prompt = document.getElementById('chatPrompt').value.trim();
      if (!prompt) return;
      const badge = document.getElementById('statusBadge');
      const out = document.getElementById('chatOutput');
      badge.textContent = 'Planning itinerary...';
      out.innerHTML = '<p class="text-slate-500 animate-pulse">Sora is calculating Shinkansen routes, JR Pass math, and daily clusters...</p>';
      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt })
        });
        const data = await res.json();
        out.innerHTML = marked.parse(data.response);
        badge.textContent = 'Complete';
      } catch (err) {
        out.innerHTML = '<p class="text-red-600">Error contacting Sora API.</p>';
        badge.textContent = 'Error';
      }
    }

    async function calcJrPass() {
      const legsRaw = document.getElementById('jrLegs').value;
      const legs = legsRaw.split(',').map(s => s.trim()).filter(Boolean);
      const duration_days = parseInt(document.getElementById('jrDays').value, 10);
      const pass_class = document.getElementById('jrClass').value;
      const box = document.getElementById('jrOutput');
      box.classList.remove('hidden');
      box.innerHTML = 'Calculating...';
      const res = await fetch('/api/jr-pass', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ legs, duration_days, pass_class })
      });
      const data = await res.json();
      const badgeColor = data.verdict === 'WORTH_IT' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800';
      let html = `<div class="font-bold px-2 py-1 rounded inline-block mb-2 ${badgeColor}">${data.verdict}</div>`;
      html += `<p class="mb-2 text-slate-700">${data.summary}</p>`;
      html += `<div class="text-slate-600 space-y-1 border-t pt-2 mt-2">`;
      html += `<div><strong>National Pass:</strong> ¥${data.national_pass_cost_jpy.toLocaleString()} | <strong>Individual Tickets:</strong> ¥${data.individual_tickets_total_jpy.toLocaleString()}</div>`;
      data.itemized_legs.forEach(l => {
        html += `<div>• ${l.leg}: <strong>¥${l.fare_jpy.toLocaleString()}</strong> (${l.duration_mins}m)</div>`;
      });
      html += `</div>`;
      box.innerHTML = html;
    }

    async function compareRailAir() {
      const origin = document.getElementById('rvaOrigin').value;
      const dest = document.getElementById('rvaDest').value;
      const box = document.getElementById('rvaOutput');
      box.classList.remove('hidden');
      const res = await fetch(`/api/rail-vs-air?origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(dest)}`);
      const data = await res.json();
      box.innerHTML = `
        <div class="font-bold text-red-800 mb-1">${data.corridor}: ${data.headline}</div>
        <div class="mt-2"><strong>🚅 Rail:</strong> ${data.rail_details.mode} (~${data.rail_details.door_to_door_mins}m door-to-door, ${data.rail_details.cost_jpy_range})</div>
        <div class="mt-1"><strong>✈️ Air:</strong> ${data.air_details.mode} (~${data.air_details.door_to_door_mins}m door-to-door, ${data.air_details.cost_jpy_range})</div>
      `;
    }

    async function loadEtiquette() {
      const topic = document.getElementById('etiquetteTopic').value;
      const box = document.getElementById('etiquetteOutput');
      box.classList.remove('hidden');
      const res = await fetch(`/api/etiquette/${encodeURIComponent(topic)}`);
      const data = await res.json();
      const entry = data[topic];
      let html = `<div class="font-bold text-slate-900 mb-2">${entry.title}</div><ul class="list-disc pl-4 space-y-1 text-slate-700">`;
      entry.golden_rules.forEach(rule => {
        html += `<li>${marked.parseInline(rule)}</li>`;
      });
      html += `</ul>`;
      box.innerHTML = html;
    }
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def serve_ui() -> HTMLResponse:
    return HTMLResponse(content=INDEX_HTML)


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
