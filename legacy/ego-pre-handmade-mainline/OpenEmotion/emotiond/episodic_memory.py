"""MVP-6.2 D2: Episodic Memory v0 (deterministic, lightweight, safe)."""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite

from emotiond.db import get_db_path, get_recent_events


SAFE_UTILITIES = {"tone", "clarify", "topic_continuity", "curiosity", "strategy_preference"}
STOPWORDS = {
    "the", "a", "an", "is", "are", "to", "of", "and", "or", "i", "you", "it", "we", "they",
    "this", "that", "in", "on", "for", "with", "as", "at", "be", "do", "did", "was", "were",
}


class EpisodicMemoryManager:
    def __init__(self, turns_per_episode: int = 6):
        self.turns_per_episode = max(2, turns_per_episode)
        self.default_top_k = 3
        self._telemetry = {
            "queries": 0,
            "hits": 0,
            "budget_bytes": 0,
            "utility_sum": 0.0,
            "selected_total": 0,
        }

    async def init_db(self) -> None:
        db_path = get_db_path()
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS episodic_turn_state (
                    target_id TEXT PRIMARY KEY,
                    turns INTEGER DEFAULT 0,
                    updated_at REAL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS episodic_episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS episodic_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_id INTEGER NOT NULL,
                    target_id TEXT NOT NULL,
                    q TEXT NOT NULL,
                    a TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    utility TEXT NOT NULL,
                    score REAL DEFAULT 0,
                    event_json TEXT DEFAULT '{}',
                    appraisal_json TEXT DEFAULT '{}',
                    state_delta_json TEXT DEFAULT '{}',
                    action_taken TEXT DEFAULT '',
                    outcome TEXT DEFAULT '',
                    lesson TEXT DEFAULT '',
                    created_at REAL NOT NULL,
                    FOREIGN KEY(episode_id) REFERENCES episodic_episodes(id)
                )
                """
            )
            # Backward-compatible schema upgrades (SQLite)
            for ddl in [
                "ALTER TABLE episodic_items ADD COLUMN event_json TEXT DEFAULT '{}'",
                "ALTER TABLE episodic_items ADD COLUMN appraisal_json TEXT DEFAULT '{}'",
                "ALTER TABLE episodic_items ADD COLUMN state_delta_json TEXT DEFAULT '{}'",
                "ALTER TABLE episodic_items ADD COLUMN action_taken TEXT DEFAULT ''",
                "ALTER TABLE episodic_items ADD COLUMN outcome TEXT DEFAULT ''",
                "ALTER TABLE episodic_items ADD COLUMN lesson TEXT DEFAULT ''",
            ]:
                try:
                    await db.execute(ddl)
                except Exception:
                    pass
            await db.execute("CREATE INDEX IF NOT EXISTS idx_epi_target_created ON episodic_items(target_id, created_at DESC)")
            await db.commit()

    async def observe_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        target_id = self._extract_target_id(event)
        if not target_id:
            return None

        should_increment = self._is_conversation_turn(event)
        forced_reason = self._episode_end_reason(event)

        turns = await self._get_turns(target_id)
        if should_increment:
            turns += 1
            await self._set_turns(target_id, turns)

        reason = forced_reason
        if reason is None and turns >= self.turns_per_episode:
            reason = "n_turns"

        if not reason:
            return None

        items = await self._build_summary_items(target_id)
        if not items:
            await self._set_turns(target_id, 0)
            return {"target_id": target_id, "reason": reason, "stored": 0}

        episode_id = await self._store_episode(target_id, reason)
        await self._store_items(episode_id, target_id, items)
        await self._set_turns(target_id, 0)
        return {"target_id": target_id, "reason": reason, "stored": len(items), "episode_id": episode_id}

    async def retrieve(self, target_id: str, query: str, k: int = 3) -> Dict[str, Any]:
        k = max(1, int(k or self.default_top_k))
        rows = await self._get_items_for_target(target_id, limit=200)
        ranked = self._rank_rows(rows, query)
        selected = ranked[:k]

        memories = [
            {
                "memory_id": r["id"],
                "episode_ref": f"episode:{r['episode_id']}",
                "q": r["q"],
                "a": r["a"],
                "kind": r["kind"],
                "utility": r["utility"],
                "safe_effects": ["tone", "clarify", "topic_continuity", "curiosity", "strategy_preference"],
                "no_high_impact_trigger": True,
            }
            for r in selected
        ]

        payload = json.dumps(memories, ensure_ascii=False)
        budget_bytes = len(payload.encode("utf-8"))

        self._telemetry["queries"] += 1
        self._telemetry["selected_total"] += len(selected)
        self._telemetry["budget_bytes"] += budget_bytes
        if selected:
            self._telemetry["hits"] += 1
            self._telemetry["utility_sum"] += float(sum(max(0.0, r["retrieval_score"]) for r in selected) / len(selected))

        return {
            "target_id": target_id,
            "top_k": k,
            "memories": memories,
            "telemetry": self.telemetry_snapshot(),
        }

    def telemetry_snapshot(self) -> Dict[str, Any]:
        queries = self._telemetry["queries"]
        hits = self._telemetry["hits"]
        return {
            "memory_hit_rate": (hits / queries) if queries else 0.0,
            "injection_budget_usage_bytes_avg": (self._telemetry["budget_bytes"] / queries) if queries else 0.0,
            "memory_utility_proxy": (self._telemetry["utility_sum"] / queries) if queries else 0.0,
            "queries": queries,
            "hits": hits,
            "selected_total": self._telemetry["selected_total"],
        }

    async def _store_episode(self, target_id: str, reason: str) -> int:
        async with aiosqlite.connect(get_db_path()) as db:
            cursor = await db.execute(
                "INSERT INTO episodic_episodes(target_id, reason, created_at) VALUES (?, ?, ?)",
                (target_id, reason, time.time()),
            )
            await db.commit()
            return int(cursor.lastrowid)

    async def _store_items(self, episode_id: int, target_id: str, items: List[Dict[str, Any]]) -> None:
        async with aiosqlite.connect(get_db_path()) as db:
            for it in items:
                utility = it.get("utility", "clarify")
                if utility not in SAFE_UTILITIES:
                    utility = "clarify"
                await db.execute(
                    """
                    INSERT INTO episodic_items(
                        episode_id, target_id, q, a, kind, utility, score,
                        event_json, appraisal_json, state_delta_json, action_taken, outcome, lesson,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        episode_id,
                        target_id,
                        it["q"][:240],
                        it["a"][:380],
                        it["kind"][:64],
                        utility,
                        float(it.get("score", 0.0)),
                        json.dumps(it.get("event", {}), ensure_ascii=False),
                        json.dumps(it.get("appraisal", {}), ensure_ascii=False),
                        json.dumps(it.get("state_delta", {}), ensure_ascii=False),
                        str(it.get("action_taken", ""))[:120],
                        str(it.get("outcome", ""))[:240],
                        str(it.get("lesson", ""))[:240],
                        time.time(),
                    ),
                )
            await db.commit()

    async def _get_turns(self, target_id: str) -> int:
        async with aiosqlite.connect(get_db_path()) as db:
            cur = await db.execute("SELECT turns FROM episodic_turn_state WHERE target_id = ?", (target_id,))
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def _set_turns(self, target_id: str, turns: int) -> None:
        async with aiosqlite.connect(get_db_path()) as db:
            await db.execute(
                "INSERT INTO episodic_turn_state(target_id, turns, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(target_id) DO UPDATE SET turns=excluded.turns, updated_at=excluded.updated_at",
                (target_id, turns, time.time()),
            )
            await db.commit()

    async def _build_summary_items(self, target_id: str) -> List[Dict[str, Any]]:
        events = await get_recent_events(limit=300)
        events = [e for e in events if self._extract_target_id(e) == target_id]
        events = list(reversed(events[-32:]))
        texts = [str(e.get("text") or "").strip() for e in events if (e.get("text") or "").strip()]
        words = self._tokens(" ".join(texts))
        common = [w for w, _ in Counter(words).most_common(4)]
        common_txt = ", ".join(common) if common else "general coordination"

        items: List[Dict[str, Any]] = []
        items.append({
            "q": "What has been the recurring topic?",
            "a": f"Recurring focus: {common_txt}.",
            "kind": "topic",
            "utility": "topic_continuity",
            "score": 1.0,
        })

        pref = self._extract_preference(texts)
        if pref:
            items.append({
                "q": "Any stable user preference?",
                "a": pref,
                "kind": "preference",
                "utility": "strategy_preference",
                "score": 0.9,
            })

        if any("?" in t for t in texts):
            items.append({
                "q": "What clarification pattern appeared?",
                "a": "User asked clarifying questions; keep answers concrete and concise.",
                "kind": "clarification",
                "utility": "clarify",
                "score": 0.8,
            })

        tone = self._infer_tone(texts)
        items.append({
            "q": "Which tone works best now?",
            "a": f"Prefer {tone} tone based on recent exchanges.",
            "kind": "tone",
            "utility": "tone",
            "score": 0.7,
        })

        items.append({
            "q": "What should continue next?",
            "a": "Continue from the latest unresolved point before introducing new branches.",
            "kind": "continuity",
            "utility": "curiosity",
            "score": 0.6,
        })

        # deterministically return 3-5 concise items
        return items[:5]

    async def _get_items_for_target(self, target_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(get_db_path()) as db:
            cur = await db.execute(
                "SELECT id, episode_id, q, a, kind, utility, score, event_json, appraisal_json, state_delta_json, action_taken, outcome, lesson, created_at FROM episodic_items WHERE target_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (target_id, limit),
            )
            rows = await cur.fetchall()
        return [
            {
                "id": int(r[0]),
                "episode_id": int(r[1]),
                "q": r[2],
                "a": r[3],
                "kind": r[4],
                "utility": r[5] if r[5] in SAFE_UTILITIES else "clarify",
                "score": float(r[6] or 0.0),
                "event": json.loads(r[7] or "{}"),
                "appraisal": json.loads(r[8] or "{}"),
                "state_delta": json.loads(r[9] or "{}"),
                "action_taken": r[10] or "",
                "outcome": r[11] or "",
                "lesson": r[12] or "",
                "created_at": float(r[13] or 0.0),
            }
            for r in rows
        ]

    def _rank_rows(self, rows: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        qtok = set(self._tokens(query or ""))
        now = time.time()
        ranked = []
        for r in rows:
            text_tokens = set(self._tokens(f"{r['q']} {r['a']} {r['kind']}"))
            overlap = len(qtok & text_tokens)
            base = r["score"]
            recency = 1.0 / max(1.0, (now - r["created_at"]) / 3600.0)
            retrieval_score = base + overlap * 0.25 + recency * 0.1
            x = dict(r)
            x["retrieval_score"] = retrieval_score
            ranked.append(x)
        ranked.sort(key=lambda x: (-x["retrieval_score"], -x["created_at"], x["id"]))
        return ranked

    def _extract_target_id(self, event: Dict[str, Any]) -> Optional[str]:
        meta = event.get("meta") or {}
        return meta.get("target_id") or (event.get("actor") if event.get("type") == "user_message" else event.get("target"))

    def _is_conversation_turn(self, event: Dict[str, Any]) -> bool:
        et = event.get("type")
        if et in {"user_message", "assistant_reply"}:
            return True
        meta = event.get("meta") or {}
        subtype = meta.get("subtype")
        return et == "world_event" and subtype in {"user_message", "interaction_outcome"}

    def _episode_end_reason(self, event: Dict[str, Any]) -> Optional[str]:
        meta = event.get("meta") or {}
        subtype = meta.get("subtype")
        if subtype in {"episode_end", "session_wrap", "conversation_end"}:
            return subtype
        if subtype == "interaction_outcome" and str(meta.get("result", "")).lower() in {"end", "done", "closed"}:
            return "interaction_end"
        return None

    def _tokens(self, text: str) -> List[str]:
        out = re.findall(r"[a-zA-Z0-9_]+", (text or "").lower())
        return [t for t in out if t not in STOPWORDS and len(t) > 1]

    def _extract_preference(self, texts: List[str]) -> Optional[str]:
        for t in reversed(texts):
            lt = t.lower()
            if any(k in lt for k in ["prefer", "i like", "i love", "don't like", "do not like", "hate"]):
                return f"User preference cue: {t[:160]}"
        return None

    def _infer_tone(self, texts: List[str]) -> str:
        joined = " ".join(texts).lower()
        pos = sum(joined.count(w) for w in ["thanks", "great", "good", "love"])
        neg = sum(joined.count(w) for w in ["bad", "wrong", "hate", "angry"])
        if neg > pos:
            return "calm and precise"
        if pos > neg:
            return "warm and concise"
        return "neutral and direct"


episodic_memory_manager = EpisodicMemoryManager()
