"""Persistent Database Session Store, Vector Memory Index, History Compaction, and Async Memory Operations for Sora."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sora_agent.observability import pii_redactor, structured_logger, trace_span
from sora_agent.schemas import StrictToolOutputModel, Field

DEFAULT_DB_PATH = os.getenv(
    "SORA_SESSION_DB_PATH",
    str(Path(__file__).resolve().parent.parent / ".sora_data" / "sora_sessions.db"),
)

# Domain vocabulary dimensions for deterministic semantic + n-gram vector embeddings
_JAPAN_DOMAIN_DIMENSIONS: list[str] = [
    "tokyo", "kyoto", "osaka", "hiroshima", "hakone", "kanazawa", "takayama", "fukuoka",
    "sapporo", "okinawa", "nara", "kobe", "himeji", "miyajima", "kinosaki", "beppu",
    "shinkansen", "jr pass", "kansai-hiroshima", "hokuriku", "smartex", "nozomi", "hikari",
    "suica", "pasmo", "icoca", "iphone", "apple wallet", "android", "welcome suica",
    "ryokan", "onsen", "kaiseki", "yukata", "tattoo", "kashikiri", "private bath",
    "konbini", "7-eleven", "familymart", "lawson", "atm", "cash",
    "takkyubin", "yamato", "luggage", "160cm", "oversized baggage",
    "sakura", "cherry blossom", "koyo", "autumn", "foliage", "winter", "snow", "summer",
    "vegetarian", "vegan", "gluten", "halal", "allergy", "budget", "luxury", "relaxed",
]


# ============================================================================
# 1. Strict Pydantic Memory & Session Schemas
# ============================================================================


class TravelerProfileMemory(StrictToolOutputModel):
    """Structured long-term traveler profile extracted across conversation turns."""

    visited_cities: list[str] = Field(default_factory=list, description="Japanese cities discussed or planned.")
    preferred_duration_days: int | None = Field(default=None, description="Last requested trip length in days.")
    preferred_month: int | None = Field(default=None, description="Last requested travel month (1-12).")
    has_iphone: bool | None = Field(default=None, description="Whether traveler uses iPhone Apple Wallet.")
    tattoo_friendly_onsen_needed: bool = Field(
        default=False, description="True if traveler mentioned tattoos for onsen visits."
    )
    dietary_preferences: list[str] = Field(
        default_factory=list, description="Dietary constraints (e.g., vegetarian, vegan, ramen, sushi)."
    )
    last_jr_pass_verdict: str | None = Field(default=None, description="Most recent JR Pass calculation verdict.")


class ConversationTurnModel(StrictToolOutputModel):
    """Single PII-redacted conversation turn stored in SQLite."""

    turn_id: int = Field(..., description="Sequential turn identifier.")
    session_id: str = Field(..., description="Conversation session ID.")
    role: str = Field(..., description="Message role ('user' or 'assistant').")
    content: str = Field(..., description="PII-redacted message text.")
    token_count: int = Field(..., ge=0, description="Estimated token count.")
    is_compacted: bool = Field(default=False, description="True if folded into compacted history summary.")
    created_at_utc: str = Field(..., description="ISO-8601 UTC creation timestamp.")


class CompactedHistorySummary(StrictToolOutputModel):
    """Result of conversation history compaction."""

    session_id: str = Field(..., description="Compacted session identifier.")
    turns_compacted: int = Field(..., ge=0, description="Number of older turns folded into summary.")
    active_turns_remaining: int = Field(..., ge=0, description="Number of recent uncompacted turns retained.")
    tokens_before_compaction: int = Field(..., ge=0, description="Estimated tokens prior to compaction.")
    tokens_after_compaction: int = Field(..., ge=0, description="Estimated tokens after compaction.")
    compacted_summary_text: str = Field(..., description="Dense entity-preserving summary of older conversation turns.")
    preserved_profile: TravelerProfileMemory = Field(..., description="Pinned traveler constraints preserved.")


class VectorMemoryMatch(StrictToolOutputModel):
    """A semantic memory record retrieved from the vector store."""

    memory_id: str = Field(..., description="Unique vector record identifier.")
    session_id: str = Field(..., description="Session namespace.")
    category: str = Field(default="preference", description="Memory category (preference, summary, itinerary).")
    content: str = Field(..., description="PII-scrubbed semantic memory text.")
    similarity_score: float = Field(..., description="Cosine similarity score in [-1.0, 1.0].")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Associated structured metadata.")


class SessionStateModel(StrictToolOutputModel):
    """Complete persistent state of a user session."""

    session_id: str = Field(..., description="Unique session ID.")
    user_id: str = Field(default="anonymous", description="User identifier.")
    traveler_profile: TravelerProfileMemory = Field(..., description="Extracted traveler constraints.")
    compacted_summary: str = Field(default="", description="Rolling summary of compacted historical turns.")
    compaction_count: int = Field(default=0, ge=0, description="Number of compaction cycles executed.")
    active_turns: list[ConversationTurnModel] = Field(
        default_factory=list, description="Uncompacted recent conversation turns."
    )
    total_active_tokens: int = Field(default=0, ge=0, description="Token count of active window + summary.")


class AssembledMemoryContext(StrictToolOutputModel):
    """Context payload assembled asynchronously before an LLM/orchestrator turn."""

    session_id: str = Field(..., description="Session ID.")
    compacted_summary: str = Field(default="", description="Compacted historical summary.")
    traveler_profile: TravelerProfileMemory = Field(..., description="Pinned traveler profile.")
    recent_turns: list[ConversationTurnModel] = Field(default_factory=list, description="Recent verbatim turns.")
    relevant_vector_memories: list[VectorMemoryMatch] = Field(
        default_factory=list, description="Top semantic matches from the vector store."
    )
    formatted_context_prompt: str = Field(
        default="", description="Formatted memory block ready for injection into the agent prompt."
    )


# ============================================================================
# 2. Token Estimator & Deterministic Dense Vector Embedding Engine
# ============================================================================


def estimate_token_count(text: str) -> int:
    """Estimates LLM token count (~4 characters per token with word boundary weighting)."""
    if not text:
        return 0
    words = len(text.split())
    chars = len(text)
    return max(1, int((words * 1.3 + chars / 4.0) / 2.0))


def compute_dense_embedding(text: str, dimensions: int = 96) -> list[float]:
    """Computes an L2-normalized dense semantic + character n-gram vector embedding.

    Combines explicit Japan travel ontology dimensions with hashed character 3-gram projections
    so semantic similarity search works reliably both offline and in cloud deployments.
    """
    lowered = text.lower()
    vec = [0.0] * dimensions

    # First 64 dimensions: Japan travel domain ontology concepts
    for idx, concept in enumerate(_JAPAN_DOMAIN_DIMENSIONS[: min(64, dimensions)]):
        if concept in lowered:
            vec[idx] += 2.5

    # Remaining dimensions: hashed word + character 3-gram features
    tokens = re.findall(r"[a-z0-9\-]+", lowered)
    for tok in tokens:
        digest = hashlib.md5(tok.encode("utf-8")).digest()
        bucket = 64 + (digest[0] % max(1, dimensions - 64)) if dimensions > 64 else digest[0] % dimensions
        sign = 1.0 if (digest[1] % 2 == 0) else -1.0
        vec[bucket] += sign * 1.0

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 1e-9:
        vec = [round(v / norm, 6) for v in vec]
    return vec


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Computes cosine similarity between two dense vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    return round(dot / (norm_a * norm_b), 4)


# ============================================================================
# 3. Persistent SQLite Session Store + Vector Store + History Compactor
# ============================================================================


class PersistentSessionMemoryManager:
    """Manages persistent SQLite session state, vector memory search, history compaction, and async operations."""

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        *,
        max_uncompacted_turns: int = 6,
        retain_recent_turns: int = 2,
        max_token_budget: int = 1800,
    ) -> None:
        self.db_path = db_path
        self.max_uncompacted_turns = max_uncompacted_turns
        self.retain_recent_turns = retain_recent_turns
        self.max_token_budget = max_token_budget
        self._async_lock = asyncio.Lock()
        self._init_database()

    def _connect(self) -> sqlite3.Connection:
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_database(self) -> None:
        self._shared_mem_conn: sqlite3.Connection | None = None
        conn = self._get_conn()
        with conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'anonymous',
                    traveler_profile_json TEXT NOT NULL,
                    compacted_summary TEXT NOT NULL DEFAULT '',
                    compaction_count INTEGER NOT NULL DEFAULT 0,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversation_turns (
                    turn_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    token_count INTEGER NOT NULL,
                    is_compacted INTEGER NOT NULL DEFAULT 0,
                    created_at_utc TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_turns_session
                ON conversation_turns(session_id, is_compacted, turn_id);

                CREATE TABLE IF NOT EXISTS vector_memories (
                    memory_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_vector_session
                ON vector_memories(session_id, category);
                """
            )
        if self.db_path != ":memory:":
            conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        if self.db_path == ":memory:":
            if self._shared_mem_conn is None:
                self._shared_mem_conn = self._connect()
            return self._shared_mem_conn
        return self._connect()

    def _close_if_file(self, conn: sqlite3.Connection) -> None:
        if self.db_path != ":memory:":
            conn.close()

    def _extract_profile_updates(self, text: str, profile: TravelerProfileMemory) -> TravelerProfileMemory:
        lowered = text.lower()
        for city in (
            "tokyo", "hakone", "kyoto", "osaka", "hiroshima", "kanazawa",
            "takayama", "fukuoka", "sapporo", "okinawa", "nara", "kobe", "himeji",
        ):
            if re.search(rf"\b{city}\b", lowered) and city.title() not in profile.visited_cities:
                profile.visited_cities.append(city.title())

        day_match = re.search(r"\b(\d{1,2})\s*(?:-|\s)?\s*(?:day|days|night|nights)\b", lowered)
        if day_match:
            val = int(day_match.group(1))
            if 1 <= val <= 21:
                profile.preferred_duration_days = val

        months = {
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        }
        for m_name, m_num in months.items():
            if re.search(rf"\b{m_name}\b", lowered):
                profile.preferred_month = m_num

        if "tattoo" in lowered:
            profile.tattoo_friendly_onsen_needed = True
        if "iphone" in lowered or "apple wallet" in lowered:
            profile.has_iphone = True
        elif "android" in lowered:
            profile.has_iphone = False

        for diet in ("vegetarian", "vegan", "gluten-free", "halal", "pescatarian", "no pork", "shellfish allergy"):
            if diet in lowered and diet not in profile.dietary_preferences:
                profile.dietary_preferences.append(diet)

        for verdict in ("REGIONAL_PASS_BETTER", "BUY_INDIVIDUAL_TICKETS", "WORTH_IT"):
            if verdict in text:
                profile.last_jr_pass_verdict = verdict

        return profile

    @trace_span("sora.memory.get_session_state", component="memory")
    def get_session_state(self, session_id: str = "default", user_id: str = "anonymous") -> SessionStateModel:
        """Retrieves or initializes the persistent session state from SQLite."""
        conn = self._get_conn()
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()

            if row is None:
                default_profile = TravelerProfileMemory()
                with conn:
                    conn.execute(
                        """
                        INSERT INTO sessions (
                            session_id, user_id, traveler_profile_json,
                            compacted_summary, compaction_count, created_at_utc, updated_at_utc
                        ) VALUES (?, ?, ?, '', 0, ?, ?)
                        """,
                        (session_id, user_id, json.dumps(default_profile.model_dump()), now_iso, now_iso),
                    )
                profile = default_profile
                compacted_summary = ""
                compaction_count = 0
            else:
                profile = TravelerProfileMemory(**json.loads(row["traveler_profile_json"]))
                compacted_summary = str(row["compacted_summary"])
                compaction_count = int(row["compaction_count"])

            turn_rows = conn.execute(
                """
                SELECT * FROM conversation_turns
                WHERE session_id = ? AND is_compacted = 0
                ORDER BY turn_id ASC
                """,
                (session_id,),
            ).fetchall()

            active_turns = [
                ConversationTurnModel(
                    turn_id=int(r["turn_id"]),
                    session_id=str(r["session_id"]),
                    role=str(r["role"]),
                    content=str(r["content"]),
                    token_count=int(r["token_count"]),
                    is_compacted=bool(r["is_compacted"]),
                    created_at_utc=str(r["created_at_utc"]),
                )
                for r in turn_rows
            ]
            total_tokens = estimate_token_count(compacted_summary) + sum(t.token_count for t in active_turns)
            return SessionStateModel(
                session_id=session_id,
                user_id=user_id,
                traveler_profile=profile,
                compacted_summary=compacted_summary,
                compaction_count=compaction_count,
                active_turns=active_turns,
                total_active_tokens=total_tokens,
            )
        finally:
            self._close_if_file(conn)

    @trace_span("sora.memory.add_turn", component="memory")
    def add_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        auto_compact: bool = True,
    ) -> ConversationTurnModel:
        """Scrubs PII, persists a conversation turn to SQLite, updates traveler profile, and triggers compaction if needed."""
        state = self.get_session_state(session_id=session_id)
        scrubbed_content = pii_redactor.redact_text(content).redacted_text
        tokens = estimate_token_count(scrubbed_content)
        now_iso = datetime.now(timezone.utc).isoformat()

        updated_profile = self._extract_profile_updates(scrubbed_content, state.traveler_profile)

        conn = self._get_conn()
        try:
            with conn:
                cursor = conn.execute(
                    """
                    INSERT INTO conversation_turns (
                        session_id, role, content, token_count, is_compacted, created_at_utc
                    ) VALUES (?, ?, ?, ?, 0, ?)
                    """,
                    (session_id, role, scrubbed_content, tokens, now_iso),
                )
                turn_id = int(cursor.lastrowid or 0)
                conn.execute(
                    """
                    UPDATE sessions
                    SET traveler_profile_json = ?, updated_at_utc = ?
                    WHERE session_id = ?
                    """,
                    (json.dumps(updated_profile.model_dump()), now_iso, session_id),
                )
        finally:
            self._close_if_file(conn)

        if role == "user" and len(scrubbed_content.strip()) > 12:
            self.store_semantic_memory(
                session_id=session_id,
                content=scrubbed_content,
                category="user_turn",
                metadata={"turn_id": turn_id, "role": role},
            )

        if auto_compact:
            refreshed = self.get_session_state(session_id=session_id)
            if (
                len(refreshed.active_turns) > self.max_uncompacted_turns
                or refreshed.total_active_tokens > self.max_token_budget
            ):
                self.compact_session_history(session_id=session_id)

        return ConversationTurnModel(
            turn_id=turn_id,
            session_id=session_id,
            role=role,
            content=scrubbed_content,
            token_count=tokens,
            is_compacted=False,
            created_at_utc=now_iso,
        )

    @trace_span("sora.memory.compact_session_history", component="memory")
    def compact_session_history(self, session_id: str, *, force: bool = False) -> CompactedHistorySummary:
        """Compacts older conversation turns into a dense entity-preserving summary to prevent context window bloat."""
        state = self.get_session_state(session_id=session_id)
        tokens_before = state.total_active_tokens
        active = state.active_turns

        if not force and len(active) <= self.retain_recent_turns:
            return CompactedHistorySummary(
                session_id=session_id,
                turns_compacted=0,
                active_turns_remaining=len(active),
                tokens_before_compaction=tokens_before,
                tokens_after_compaction=tokens_before,
                compacted_summary_text=state.compacted_summary,
                preserved_profile=state.traveler_profile,
            )

        cutoff = max(1, len(active) - self.retain_recent_turns) if len(active) > self.retain_recent_turns else len(active)
        turns_to_compact = active[:cutoff]
        remaining_turns = active[cutoff:]

        bullet_points: list[str] = []
        for t in turns_to_compact:
            snippet = " ".join(t.content.strip().split())
            if len(snippet) > 160:
                snippet = snippet[:157] + "..."
            bullet_points.append(f"[{t.role.upper()} #{t.turn_id}]: {snippet}")

        profile = state.traveler_profile
        profile_header = (
            f"Pinned Traveler Profile: cities={profile.visited_cities or ['unspecified']}, "
            f"days={profile.preferred_duration_days or 'unspecified'}, "
            f"month={profile.preferred_month or 'unspecified'}, "
            f"tattoo_onsen={profile.tattoo_friendly_onsen_needed}, "
            f"dietary={profile.dietary_preferences or ['none']}, "
            f"jr_pass={profile.last_jr_pass_verdict or 'pending'}."
        )

        prior_block = f"{state.compacted_summary}\n" if state.compacted_summary else ""
        new_summary = (
            f"{profile_header}\n"
            f"{prior_block}"
            f"Compacted History ({len(turns_to_compact)} turns): " + " | ".join(bullet_points)
        ).strip()
        if len(new_summary) > 1200:
            new_summary = f"{profile_header}\n" + new_summary[-950:]

        conn = self._get_conn()
        try:
            turn_ids = [t.turn_id for t in turns_to_compact]
            now_iso = datetime.now(timezone.utc).isoformat()
            with conn:
                if turn_ids:
                    placeholders = ",".join("?" for _ in turn_ids)
                    conn.execute(
                        f"UPDATE conversation_turns SET is_compacted = 1 WHERE turn_id IN ({placeholders})",
                        tuple(turn_ids),
                    )
                conn.execute(
                    """
                    UPDATE sessions
                    SET compacted_summary = ?, compaction_count = compaction_count + 1, updated_at_utc = ?
                    WHERE session_id = ?
                    """,
                    (new_summary, now_iso, session_id),
                )
        finally:
            self._close_if_file(conn)

        self.store_semantic_memory(
            session_id=session_id,
            content=new_summary,
            category="compacted_summary",
            metadata={"turns_compacted": len(turns_to_compact)},
        )

        tokens_after = estimate_token_count(new_summary) + sum(t.token_count for t in remaining_turns)
        structured_logger.info(
            f"Compacted {len(turns_to_compact)} turns for session '{session_id}' ({tokens_before} -> {tokens_after} tokens)",
            component="memory",
            event_type="history_compacted",
            session_id=session_id,
            attributes={
                "turns_compacted": len(turns_to_compact),
                "tokens_before": tokens_before,
                "tokens_after": tokens_after,
            },
        )

        return CompactedHistorySummary(
            session_id=session_id,
            turns_compacted=len(turns_to_compact),
            active_turns_remaining=len(remaining_turns),
            tokens_before_compaction=tokens_before,
            tokens_after_compaction=tokens_after,
            compacted_summary_text=new_summary,
            preserved_profile=profile,
        )

    @trace_span("sora.memory.store_semantic_memory", component="memory")
    def store_semantic_memory(
        self,
        session_id: str,
        content: str,
        *,
        category: str = "preference",
        metadata: dict[str, Any] | None = None,
    ) -> VectorMemoryMatch:
        """Computes a vector embedding and stores a PII-redacted semantic memory in the vector store."""
        clean_text = pii_redactor.redact_text(content).redacted_text
        clean_meta = pii_redactor.redact_payload(metadata or {})
        embedding = compute_dense_embedding(clean_text)
        memory_id = f"mem-{secrets.token_hex(6)}"
        now_iso = datetime.now(timezone.utc).isoformat()

        conn = self._get_conn()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO vector_memories (
                        memory_id, session_id, category, content, embedding_json, metadata_json, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        memory_id,
                        session_id,
                        category,
                        clean_text,
                        json.dumps(embedding),
                        json.dumps(clean_meta),
                        now_iso,
                    ),
                )
        finally:
            self._close_if_file(conn)

        return VectorMemoryMatch(
            memory_id=memory_id,
            session_id=session_id,
            category=category,
            content=clean_text,
            similarity_score=1.0,
            metadata=clean_meta,
        )

    @trace_span("sora.memory.search_semantic_memory", component="memory")
    def search_semantic_memory(
        self,
        query: str,
        *,
        session_id: str | None = None,
        top_k: int = 3,
        min_score: float = 0.05,
    ) -> list[VectorMemoryMatch]:
        """Performs cosine similarity vector search across stored semantic memories."""
        query_vec = compute_dense_embedding(query)
        conn = self._get_conn()
        try:
            if session_id:
                rows = conn.execute(
                    "SELECT * FROM vector_memories WHERE session_id = ? ORDER BY created_at_utc DESC LIMIT 200",
                    (session_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM vector_memories ORDER BY created_at_utc DESC LIMIT 200"
                ).fetchall()
        finally:
            self._close_if_file(conn)

        scored: list[VectorMemoryMatch] = []
        for r in rows:
            emb = json.loads(r["embedding_json"])
            sim = cosine_similarity(query_vec, emb)
            if sim >= min_score:
                scored.append(
                    VectorMemoryMatch(
                        memory_id=str(r["memory_id"]),
                        session_id=str(r["session_id"]),
                        category=str(r["category"]),
                        content=str(r["content"]),
                        similarity_score=sim,
                        metadata=json.loads(r["metadata_json"]),
                    )
                )

        scored.sort(key=lambda m: m.similarity_score, reverse=True)
        return scored[: max(1, top_k)]

    # ========================================================================
    # 4. Asynchronous Memory Operations (asyncio-native non-blocking I/O)
    # ========================================================================

    @trace_span("sora.memory.aget_session_state", component="memory")
    async def aget_session_state(self, session_id: str = "default", user_id: str = "anonymous") -> SessionStateModel:
        """Asynchronously retrieves persistent session state without blocking the event loop."""
        async with self._async_lock:
            return await asyncio.to_thread(self.get_session_state, session_id, user_id)

    @trace_span("sora.memory.aadd_turn", component="memory")
    async def aadd_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        auto_compact: bool = True,
    ) -> ConversationTurnModel:
        """Asynchronously appends a turn, updates the traveler profile, and compacts history if needed."""
        async with self._async_lock:
            return await asyncio.to_thread(
                self.add_turn,
                session_id,
                role,
                content,
                auto_compact=auto_compact,
            )

    @trace_span("sora.memory.acompact_session_history", component="memory")
    async def acompact_session_history(self, session_id: str, *, force: bool = False) -> CompactedHistorySummary:
        """Asynchronously executes conversation history compaction."""
        async with self._async_lock:
            return await asyncio.to_thread(self.compact_session_history, session_id, force=force)

    @trace_span("sora.memory.astore_semantic_memory", component="memory")
    async def astore_semantic_memory(
        self,
        session_id: str,
        content: str,
        *,
        category: str = "preference",
        metadata: dict[str, Any] | None = None,
    ) -> VectorMemoryMatch:
        """Asynchronously computes vector embeddings and persists semantic memory."""
        async with self._async_lock:
            return await asyncio.to_thread(
                self.store_semantic_memory,
                session_id,
                content,
                category=category,
                metadata=metadata,
            )

    @trace_span("sora.memory.asearch_semantic_memory", component="memory")
    async def asearch_semantic_memory(
        self,
        query: str,
        *,
        session_id: str | None = None,
        top_k: int = 3,
        min_score: float = 0.05,
    ) -> list[VectorMemoryMatch]:
        """Asynchronously performs vector similarity search."""
        return await asyncio.to_thread(
            self.search_semantic_memory,
            query,
            session_id=session_id,
            top_k=top_k,
            min_score=min_score,
        )

    @trace_span("sora.memory.abuild_context_window", component="memory")
    async def abuild_context_window(
        self,
        session_id: str,
        current_query: str,
        *,
        top_k_memories: int = 3,
    ) -> AssembledMemoryContext:
        """Concurrently fetches session state and vector memories via `asyncio.gather`."""
        state, vector_matches = await asyncio.gather(
            self.aget_session_state(session_id=session_id),
            self.asearch_semantic_memory(current_query, session_id=session_id, top_k=top_k_memories),
        )

        parts: list[str] = []
        if state.compacted_summary:
            parts.append(f"### Compacted Session Memory\n{state.compacted_summary}")
        if vector_matches:
            mem_lines = [f"- ({m.similarity_score:.2f}) {m.content}" for m in vector_matches]
            parts.append("### Retrieved Vector Memories\n" + "\n".join(mem_lines))
        if state.active_turns:
            turn_lines = [f"- {t.role.upper()}: {t.content[:200]}" for t in state.active_turns[-4:]]
            parts.append("### Recent Conversation Turns\n" + "\n".join(turn_lines))

        return AssembledMemoryContext(
            session_id=session_id,
            compacted_summary=state.compacted_summary,
            traveler_profile=state.traveler_profile,
            recent_turns=state.active_turns,
            relevant_vector_memories=vector_matches,
            formatted_context_prompt="\n\n".join(parts),
        )


session_memory_manager = PersistentSessionMemoryManager()

__all__ = [
    "AssembledMemoryContext",
    "CompactedHistorySummary",
    "ConversationTurnModel",
    "DEFAULT_DB_PATH",
    "PersistentSessionMemoryManager",
    "SessionStateModel",
    "TravelerProfileMemory",
    "VectorMemoryMatch",
    "compute_dense_embedding",
    "cosine_similarity",
    "estimate_token_count",
    "session_memory_manager",
]
