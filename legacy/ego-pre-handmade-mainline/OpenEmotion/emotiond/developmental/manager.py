"""
MVP16: Developmental Manager

Manages long-horizon developmental continuity with real persistence.

WP11 / MVP16 status:
- reference-only compatibility surface
- not the formal owner path
- not current-mainline closeout proof
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .schema import (
    DevelopmentalEpisode,
    DevelopmentalState,
    DevelopmentalTrajectory,
    DevelopmentalWritebackEvent,
    GrowthMetric,
    TransitionRecord,
)


EGO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STATE_PATH = EGO_ROOT / "OpenEmotion" / "data" / "developmental_state.json"
DEFAULT_REAL_SAMPLE_ARTIFACTS_DIR = EGO_ROOT / "artifacts" / "telegram_real_mainline_v1" / "real_telegram"
LEGACY_REAL_SAMPLE_ARTIFACTS_DIR = EGO_ROOT / "EgoCore" / "artifacts" / "telegram_real_mainline_v1" / "real_telegram"
DEFAULT_OBSERVATION_DIR = EGO_ROOT / "OpenEmotion" / "artifacts" / "mvp16-observation"

REAL_CHANNEL = "real_channel"
REAL_OUTPUT_SCHEMA_VERSION = "proto_self.output.v2"
REAL_TRACE_SCHEMA_VERSION = "proto_self.trace.v2"
SESSION_RESET_COMMAND = "/new"
TRANSITION_SESSION_RESET = "session_reset"
TRANSITION_CALENDAR_ROLLOVER = "calendar_rollover"
TRANSITION_GOVERNANCE_CHECKPOINT = "governance_checkpoint"
TRANSITION_PHASE_CHANGE = "phase_change"


class DevelopmentalManager:
    """Manager for open developmental continuity with real persistence."""

    _instance: Optional["DevelopmentalManager"] = None

    def __init__(
        self,
        initial_state: Optional[DevelopmentalState] = None,
        state_path: Optional[Path] = None,
    ):
        self._state_path = Path(state_path or DEFAULT_STATE_PATH)

        if initial_state is not None:
            self.state = initial_state
        else:
            loaded_state = self._load_state()
            if loaded_state is not None:
                self.state = loaded_state
            else:
                self.state = DevelopmentalState()
                self._initialize_metrics_on(self.state)

    @classmethod
    def get_instance(cls, state_path: Optional[Path] = None) -> "DevelopmentalManager":
        if cls._instance is None:
            cls._instance = cls(state_path=state_path)
        return cls._instance

    @classmethod
    def reset(cls, clear_persistence: bool = False, state_path: Optional[Path] = None) -> None:
        if clear_persistence:
            path = Path(state_path or DEFAULT_STATE_PATH)
            if path.exists():
                path.unlink()
        cls._instance = None

    def _load_state(self) -> Optional[DevelopmentalState]:
        if not self._state_path.exists():
            return None

        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            return DevelopmentalState(**data)
        except (json.JSONDecodeError, Exception):
            return None

    def save(self) -> bool:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(self.state.model_dump_json(indent=2), encoding="utf-8")
            return True
        except Exception:
            return False

    def has_persisted_state(self) -> bool:
        return self._state_path.exists()

    def has_real_data(self) -> bool:
        summary = self.get_summary()
        return bool(summary.get("has_real_data", False))

    def _initialize_metrics_on(self, state: DevelopmentalState) -> None:
        default_metrics = [
            ("continuity_score", 0.0),
            ("growth_rate", 0.0),
            ("identity_stability", 1.0),
            ("governance_compliance", 1.0),
        ]
        for name, value in default_metrics:
            if name not in state.metrics:
                state.metrics[name] = GrowthMetric(metric_name=name, value=value)

    def _set_metric_value(self, name: str, value: float, *, target: Optional[float] = None) -> GrowthMetric:
        if name not in self.state.metrics:
            self.state.metrics[name] = GrowthMetric(metric_name=name, value=value, target=target)
            return self.state.metrics[name]

        metric = self.state.metrics[name]
        metric.history.append(metric.value)
        metric.value = value
        if target is not None:
            metric.target = target
        previous = metric.history[-1] if metric.history else value
        if value > previous:
            metric.trend = "improving"
        elif value < previous:
            metric.trend = "declining"
        else:
            metric.trend = "stable"
        return metric

    def _repo_relative_ref(self, path: Path) -> str:
        resolved = path.resolve()
        try:
            return str(resolved.relative_to(EGO_ROOT)).replace("\\", "/")
        except ValueError:
            return str(resolved).replace("\\", "/")

    def _path_from_ref(self, ref: str) -> Path:
        ref_path = Path(ref)
        if ref_path.is_absolute():
            return ref_path
        return EGO_ROOT / ref_path

    def _extract_calendar_day(self, value: Any) -> str:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value)).date().isoformat()
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
            except ValueError:
                date_part = value.split("T", 1)[0]
                if len(date_part) == 10 and date_part.count("-") == 2:
                    return date_part
        return ""

    def _load_json_if_exists(self, path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _resolve_sample_artifacts_dir(self, sample_artifacts_dir: Optional[Path]) -> Path:
        if sample_artifacts_dir is not None:
            return Path(sample_artifacts_dir)
        for candidate in (DEFAULT_REAL_SAMPLE_ARTIFACTS_DIR, LEGACY_REAL_SAMPLE_ARTIFACTS_DIR):
            if candidate.exists():
                return candidate
        return DEFAULT_REAL_SAMPLE_ARTIFACTS_DIR

    def _iter_sample_records(self, sample_artifacts_dir: Path) -> List[Tuple[Path, Dict[str, Any], Dict[str, Any]]]:
        records: List[Tuple[str, str, Path, Dict[str, Any], Dict[str, Any]]] = []
        if not sample_artifacts_dir.exists():
            return []

        for sample_dir in sample_artifacts_dir.iterdir():
            if not sample_dir.is_dir() or not sample_dir.name.startswith("sample_"):
                continue
            sample = self._load_json_if_exists(sample_dir / "sample.json") or {}
            ledger = self._load_json_if_exists(sample_dir / "ledger.json") or {}
            timestamp = str(sample.get("timestamp") or ledger.get("timestamp") or sample_dir.name)
            records.append((timestamp, sample_dir.name, sample_dir, sample, ledger))

        records.sort(key=lambda item: (item[0], item[1]))
        return [(sample_dir, sample, ledger) for _, _, sample_dir, sample, ledger in records]

    def _extract_message_text(self, sample: Dict[str, Any], ledger: Dict[str, Any]) -> str:
        raw_update = sample.get("raw_update") or (ledger.get("inputs") or {}).get("raw_update") or {}
        text = (raw_update.get("message") or {}).get("text")
        if isinstance(text, str) and text:
            return text

        normalized_event = sample.get("normalized_event") or (ledger.get("inputs") or {}).get("normalized_event") or {}
        event_block = normalized_event.get("event") or {}
        for candidate in (
            event_block.get("raw_text"),
            normalized_event.get("raw_text"),
            event_block.get("user_intent"),
            normalized_event.get("user_intent"),
        ):
            if isinstance(candidate, str) and candidate:
                return candidate
        return ""

    def _extract_session_id(self, sample: Dict[str, Any], ledger: Dict[str, Any]) -> str:
        normalized_event = sample.get("normalized_event") or (ledger.get("inputs") or {}).get("normalized_event") or {}
        for block in (
            normalized_event.get("conversation_summary") or {},
            normalized_event.get("conversation_context") or {},
        ):
            session_id = block.get("session_id")
            if session_id:
                return str(session_id)
        return str((ledger.get("ids") or {}).get("session_id") or "")

    def _extract_schema_versions(self, sample: Dict[str, Any], ledger: Dict[str, Any]) -> Tuple[str, str]:
        result = sample.get("openemotion_result") or (ledger.get("openemotion") or {}).get("result") or {}
        trace = sample.get("openemotion_trace") or (ledger.get("openemotion") or {}).get("trace_payload") or {}
        return str(result.get("schema_version") or ""), str(trace.get("schema_version") or "")

    def _extract_timestamp(self, sample: Dict[str, Any], ledger: Dict[str, Any], sample_dir: Path) -> Tuple[float, str]:
        raw_timestamp = sample.get("timestamp") or ledger.get("timestamp") or ""
        calendar_day = self._extract_calendar_day(raw_timestamp)
        if isinstance(raw_timestamp, (int, float)):
            return float(raw_timestamp), calendar_day
        if isinstance(raw_timestamp, str) and raw_timestamp:
            try:
                dt = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
                return dt.timestamp(), calendar_day
            except ValueError:
                pass
        return sample_dir.stat().st_mtime, calendar_day

    def _build_governance_snapshot(self, sample: Dict[str, Any], ledger: Dict[str, Any]) -> Dict[str, Any]:
        response_plan = sample.get("response_plan") or (ledger.get("host") or {}).get("response_plan") or {}
        outbox_record = sample.get("outbox_record") or (ledger.get("host") or {}).get("outbox_record") or {}
        return {
            "response_plan_status": response_plan.get("status"),
            "delivery_kind": response_plan.get("delivery_kind"),
            "outbox_success": bool(outbox_record.get("success")),
            "reply_length": response_plan.get("reply_length"),
            "text_length": outbox_record.get("text_length"),
            "message_id": outbox_record.get("message_id"),
        }

    def _build_invariant_snapshot(
        self,
        *,
        session_id: str,
        sample_ref: str,
        ledger_ref: str,
        output_schema_version: str,
        trace_schema_version: str,
    ) -> Dict[str, Any]:
        source_refs_intact = bool(sample_ref and ledger_ref)
        schema_chain_ok = (
            output_schema_version == REAL_OUTPUT_SCHEMA_VERSION
            and trace_schema_version == REAL_TRACE_SCHEMA_VERSION
        )
        return {
            "identity_preserved": bool(session_id) and source_refs_intact and schema_chain_ok,
            "source_refs_intact": source_refs_intact,
            "session_id_present": bool(session_id),
            "proto_self_output_schema_version": output_schema_version,
            "proto_self_trace_schema_version": trace_schema_version,
        }

    def _is_session_reset_anchor(self, sample: Dict[str, Any], ledger: Dict[str, Any]) -> bool:
        text = self._extract_message_text(sample, ledger).strip()
        return text == SESSION_RESET_COMMAND

    def _build_writeback_event_from_sample(
        self,
        *,
        sample_dir: Path,
        sample: Dict[str, Any],
        ledger: Dict[str, Any],
    ) -> Optional[DevelopmentalWritebackEvent]:
        source_type = str(sample.get("source_type") or ledger.get("source_type") or "")
        if source_type != REAL_CHANNEL:
            return None

        text = self._extract_message_text(sample, ledger).strip()
        if not text or text.startswith("/"):
            return None

        output_schema_version, trace_schema_version = self._extract_schema_versions(sample, ledger)
        if output_schema_version != REAL_OUTPUT_SCHEMA_VERSION or trace_schema_version != REAL_TRACE_SCHEMA_VERSION:
            return None

        session_id = self._extract_session_id(sample, ledger)
        sample_ref_path = sample_dir / "sample.json"
        ledger_ref_path = sample_dir / "ledger.json"
        replay_ref_path = sample_dir / "replay.json"
        sample_ref = self._repo_relative_ref(sample_ref_path if sample_ref_path.exists() else sample_dir)
        ledger_ref = self._repo_relative_ref(ledger_ref_path if ledger_ref_path.exists() else sample_dir)
        replay_ref = self._repo_relative_ref(replay_ref_path) if replay_ref_path.exists() else ""
        timestamp, calendar_day = self._extract_timestamp(sample, ledger, sample_dir)
        governance_snapshot = self._build_governance_snapshot(sample, ledger)
        invariant_snapshot = self._build_invariant_snapshot(
            session_id=session_id,
            sample_ref=sample_ref,
            ledger_ref=ledger_ref,
            output_schema_version=output_schema_version,
            trace_schema_version=trace_schema_version,
        )
        response_plan = sample.get("response_plan") or (ledger.get("host") or {}).get("response_plan") or {}
        outbox_record = sample.get("outbox_record") or (ledger.get("host") or {}).get("outbox_record") or {}
        outcome_summary = (
            f"response_plan={response_plan.get('status') or 'unknown'};"
            f" delivery_kind={response_plan.get('delivery_kind') or 'unknown'};"
            f" outbox_success={bool(outbox_record.get('success'))}"
        )

        return DevelopmentalWritebackEvent(
            source_type=source_type,
            session_id=session_id,
            sample_ref=sample_ref,
            ledger_ref=ledger_ref,
            user_turn_kind="natural_language",
            final_action=str(response_plan.get("delivery_kind") or "reply"),
            outcome_summary=outcome_summary,
            proto_self_output_schema_version=output_schema_version,
            proto_self_trace_schema_version=trace_schema_version,
            governance_snapshot=governance_snapshot,
            invariant_snapshot=invariant_snapshot,
            timestamp=timestamp,
            calendar_day=calendar_day,
            sample_id=sample.get("sample_id") or sample_dir.name,
            replay_ref=replay_ref,
        )

    def _new_projection_state(self) -> DevelopmentalState:
        state = DevelopmentalState()
        self._initialize_metrics_on(state)
        return state

    def _record_episode_into_state(
        self,
        state: DevelopmentalState,
        event: DevelopmentalWritebackEvent,
    ) -> DevelopmentalEpisode:
        existing = next((ep for ep in state.trajectory.episodes if ep.sample_ref == event.sample_ref), None)
        if existing is not None:
            return existing

        episode = DevelopmentalEpisode(
            episode_id=f"ep_{int(event.timestamp)}_{uuid.uuid4().hex[:8]}",
            episode_type="real_mainline_turn",
            phase="MVP16",
            description=event.outcome_summary,
            started_at=event.timestamp,
            completed_at=event.timestamp,
            achievements=["real_mainline_capture"],
            source_type=event.source_type,
            session_id=event.session_id,
            sample_ref=event.sample_ref,
            ledger_ref=event.ledger_ref,
            replay_ref=event.replay_ref,
            final_action=event.final_action,
            outcome_summary=event.outcome_summary,
            proto_self_output_schema_version=event.proto_self_output_schema_version,
            proto_self_trace_schema_version=event.proto_self_trace_schema_version,
            real_mainline=True,
            governance_snapshot=event.governance_snapshot,
            invariant_snapshot=event.invariant_snapshot,
            calendar_day=event.calendar_day,
        )
        state.trajectory.episodes.append(episode)
        return episode

    def _append_transition(
        self,
        state: DevelopmentalState,
        *,
        transition_kind: str,
        from_episode: DevelopmentalEpisode,
        to_episode: DevelopmentalEpisode,
        trigger_ref: str,
        replay_ref: str,
        approver: str,
    ) -> None:
        for existing in state.trajectory.transitions:
            if (
                existing.transition_kind == transition_kind
                and existing.from_episode_ref == from_episode.sample_ref
                and existing.to_episode_ref == to_episode.sample_ref
            ):
                return

        transition = TransitionRecord(
            transition_id=f"tr_{int(time.time())}_{uuid.uuid4().hex[:8]}",
            from_phase=state.trajectory.current_phase,
            to_phase=state.trajectory.current_phase,
            timestamp=to_episode.completed_at or to_episode.started_at,
            approved=True,
            approver=approver,
            replay_hash=hashlib.sha256(
                f"{transition_kind}:{from_episode.sample_ref}:{to_episode.sample_ref}:{trigger_ref}".encode("utf-8")
            ).hexdigest()[:16],
            transition_kind=transition_kind,
            from_episode_ref=from_episode.sample_ref,
            to_episode_ref=to_episode.sample_ref,
            trigger_ref=trigger_ref,
            replay_ref=replay_ref,
        )
        state.trajectory.transitions.append(transition)

    def _compute_projection_summary(self) -> Dict[str, Any]:
        real_episodes = self.get_real_mainline_episodes()
        real_episode_count = len(real_episodes)
        real_day_count = len({ep.calendar_day for ep in real_episodes if ep.calendar_day})
        session_reset_count = sum(
            1 for transition in self.state.trajectory.transitions if transition.transition_kind == TRANSITION_SESSION_RESET
        )
        calendar_rollover_count = sum(
            1 for transition in self.state.trajectory.transitions if transition.transition_kind == TRANSITION_CALENDAR_ROLLOVER
        )
        governance_checkpoint_count = sum(
            1 for transition in self.state.trajectory.transitions if transition.transition_kind == TRANSITION_GOVERNANCE_CHECKPOINT
        )
        transition_pairs = {
            (transition.transition_kind, transition.from_episode_ref, transition.to_episode_ref)
            for transition in self.state.trajectory.transitions
        }
        real_session_count = 0
        previous_episode: Optional[DevelopmentalEpisode] = None
        for episode in real_episodes:
            if previous_episode is None:
                real_session_count = 1
            else:
                if (
                    episode.session_id != previous_episode.session_id
                    or (
                        TRANSITION_SESSION_RESET,
                        previous_episode.sample_ref,
                        episode.sample_ref,
                    ) in transition_pairs
                ):
                    real_session_count += 1
            previous_episode = episode
        trajectory_refs_present = bool(real_episodes) and all(
            ep.sample_ref
            and ep.ledger_ref
            and self._path_from_ref(ep.sample_ref).exists()
            and self._path_from_ref(ep.ledger_ref).exists()
            for ep in real_episodes
        )
        replay_refs_present = bool(real_episodes) and all(
            ep.replay_ref and self._path_from_ref(ep.replay_ref).exists()
            for ep in real_episodes
        ) and all(
            transition.replay_ref and self._path_from_ref(transition.replay_ref).exists()
            for transition in self.state.trajectory.transitions
        )
        identity_preserved = all(
            bool(ep.invariant_snapshot.get("identity_preserved", False))
            for ep in real_episodes
        ) if real_episodes else True
        governance_preserved = all(
            bool(ep.governance_snapshot.get("outbox_success", False))
            for ep in real_episodes
        ) if real_episodes else False

        continuity_score = (
            min(real_episode_count / 3.0, 1.0) * 0.5
            + min(real_session_count / 2.0, 1.0) * 0.25
            + min(real_day_count / 2.0, 1.0) * 0.25
        ) if real_episodes else 0.0
        growth_rate = min(real_episode_count / 5.0, 1.0)
        identity_value = 1.0 if identity_preserved else 0.0
        governance_value = 1.0 if governance_preserved else 0.0

        has_real_data = real_episode_count >= 1 and trajectory_refs_present
        admission_inputs_present = (
            real_episode_count >= 3
            and real_session_count >= 2
            and real_day_count >= 2
            and session_reset_count >= 1
            and calendar_rollover_count >= 1
            and trajectory_refs_present
            and replay_refs_present
            and identity_preserved
            and governance_preserved
        )
        return {
            "current_phase": self.state.trajectory.current_phase,
            "episodes": real_episode_count,
            "transitions": len(self.state.trajectory.transitions),
            "identity_preserved": identity_preserved,
            "continuity_score": round(continuity_score, 3),
            "persisted": self.has_persisted_state(),
            "has_real_data": has_real_data,
            "real_episode_count": real_episode_count,
            "real_session_count": real_session_count,
            "real_day_count": real_day_count,
            "trajectory_refs_present": trajectory_refs_present,
            "replay_refs_present": replay_refs_present,
            "admission_inputs_present": admission_inputs_present,
            "session_reset_transition_count": session_reset_count,
            "calendar_rollover_transition_count": calendar_rollover_count,
            "governance_checkpoint_transition_count": governance_checkpoint_count,
            "governance_preserved": governance_preserved,
            "projection_metric_values": {
                "continuity_score": round(continuity_score, 3),
                "growth_rate": round(growth_rate, 3),
                "identity_stability": identity_value,
                "governance_compliance": governance_value,
            },
        }

    def _refresh_projection_state(self) -> Dict[str, Any]:
        summary = self._compute_projection_summary()
        metric_values = summary["projection_metric_values"]
        self._set_metric_value("continuity_score", metric_values["continuity_score"], target=1.0)
        self._set_metric_value("growth_rate", metric_values["growth_rate"], target=1.0)
        self._set_metric_value("identity_stability", metric_values["identity_stability"], target=1.0)
        self._set_metric_value("governance_compliance", metric_values["governance_compliance"], target=1.0)
        self.state.trajectory.identity_preserved = bool(summary["identity_preserved"])
        self.state.trajectory.current_phase = "MVP16"
        self.state.update_timestamp()
        return summary

    def get_real_mainline_episodes(self) -> List[DevelopmentalEpisode]:
        return [episode for episode in self.state.trajectory.episodes if episode.real_mainline]

    def record_episode(
        self,
        episode_type: str,
        phase: str,
        description: str = "",
    ) -> DevelopmentalEpisode:
        episode = DevelopmentalEpisode(
            episode_id=f"ep_{int(time.time())}_{uuid.uuid4().hex[:8]}",
            episode_type=episode_type,
            phase=phase,
            description=description,
            real_mainline=False,
        )
        self.state.trajectory.episodes.append(episode)
        self.state.update_timestamp()
        self.save()
        return episode

    def complete_episode(self, episode_id: str, achievements: List[str]) -> bool:
        for episode in self.state.trajectory.episodes:
            if episode.episode_id == episode_id:
                episode.completed_at = time.time()
                episode.achievements = achievements
                self.state.update_timestamp()
                self.save()
                return True
        return False

    def record_transition(
        self,
        from_phase: str,
        to_phase: str,
        approved: bool = False,
        approver: Optional[str] = None,
    ) -> TransitionRecord:
        transition = TransitionRecord(
            transition_id=f"tr_{int(time.time())}_{uuid.uuid4().hex[:8]}",
            from_phase=from_phase,
            to_phase=to_phase,
            approved=approved,
            approver=approver,
        )
        self.state.trajectory.transitions.append(transition)
        self.state.trajectory.current_phase = to_phase
        self.state.update_timestamp()
        self.save()
        return transition

    def update_metric(self, name: str, value: float) -> GrowthMetric:
        metric = self._set_metric_value(name, value)
        self.state.update_timestamp()
        self.save()
        return metric

    def record_real_mainline_episode(self, event: DevelopmentalWritebackEvent) -> DevelopmentalEpisode:
        if event.source_type != REAL_CHANNEL:
            raise ValueError("Admission-grade developmental writeback requires source_type=real_channel")
        if event.user_turn_kind != "natural_language":
            raise ValueError("Admission-grade developmental writeback only accepts natural_language turns")
        if not event.sample_ref or not event.ledger_ref:
            raise ValueError("Admission-grade developmental writeback requires sample_ref and ledger_ref")
        if not self._path_from_ref(event.sample_ref).exists() or not self._path_from_ref(event.ledger_ref).exists():
            raise ValueError("Admission-grade developmental writeback requires real persisted sample_ref + ledger_ref")
        if (
            event.proto_self_output_schema_version != REAL_OUTPUT_SCHEMA_VERSION
            or event.proto_self_trace_schema_version != REAL_TRACE_SCHEMA_VERSION
        ):
            raise ValueError("Admission-grade developmental writeback requires proto_self.output.v2 + proto_self.trace.v2")

        episode = self._record_episode_into_state(self.state, event)
        self._refresh_projection_state()
        self.save()
        return episode

    def sync_real_projection_from_sample_artifacts(
        self,
        sample_artifacts_dir: Optional[Path] = None,
        observation_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        sample_root = self._resolve_sample_artifacts_dir(sample_artifacts_dir)
        if not sample_root.exists():
            summary = self.get_summary()
            summary.update(
                {
                    "sync_status": "sample_artifacts_missing",
                    "sample_artifacts_dir": str(sample_root),
                }
            )
            return summary

        projected_state = self._new_projection_state()
        last_real_episode: Optional[DevelopmentalEpisode] = None
        pending_reset_trigger_ref: Optional[str] = None
        imported_real_episode_count = 0
        eligible_samples_found = 0

        for sample_dir, sample, ledger in self._iter_sample_records(sample_root):
            sample_ref_path = sample_dir / "sample.json"
            ledger_ref_path = sample_dir / "ledger.json"
            command_trigger_ref = self._repo_relative_ref(sample_ref_path if sample_ref_path.exists() else ledger_ref_path)

            if self._is_session_reset_anchor(sample, ledger):
                pending_reset_trigger_ref = command_trigger_ref
                continue

            event = self._build_writeback_event_from_sample(sample_dir=sample_dir, sample=sample, ledger=ledger)
            if event is None:
                continue

            eligible_samples_found += 1
            episode = self._record_episode_into_state(projected_state, event)
            if episode is last_real_episode:
                continue

            imported_real_episode_count += 1
            if last_real_episode is not None:
                if pending_reset_trigger_ref:
                    self._append_transition(
                        projected_state,
                        transition_kind=TRANSITION_SESSION_RESET,
                        from_episode=last_real_episode,
                        to_episode=episode,
                        trigger_ref=pending_reset_trigger_ref,
                        replay_ref=episode.replay_ref,
                        approver="telegram_session_reset",
                    )
                    pending_reset_trigger_ref = None

                if (
                    last_real_episode.calendar_day
                    and episode.calendar_day
                    and last_real_episode.calendar_day != episode.calendar_day
                ):
                    self._append_transition(
                        projected_state,
                        transition_kind=TRANSITION_CALENDAR_ROLLOVER,
                        from_episode=last_real_episode,
                        to_episode=episode,
                        trigger_ref=episode.sample_ref,
                        replay_ref=episode.replay_ref,
                        approver="calendar_rollover",
                    )
            else:
                # A leading /new anchor before the first real episode must not
                # fabricate a session_reset transition inside the same session.
                pending_reset_trigger_ref = None

            last_real_episode = episode

        self.state = projected_state
        summary = self._refresh_projection_state()
        self.save()

        artifact_paths: Dict[str, str] = {}
        if observation_dir is not None:
            artifact_paths = self.write_admission_artifacts(
                observation_dir=observation_dir,
                sample_artifacts_dir=sample_root,
            )

        summary.update(
            {
                "sync_status": "synced",
                "sample_artifacts_dir": str(sample_root),
                "imported_real_episode_count": imported_real_episode_count,
                "eligible_samples_found": eligible_samples_found,
                "artifact_paths": artifact_paths,
            }
        )
        return summary

    def check_identity_preservation(self) -> bool:
        return self.state.trajectory.identity_preserved

    def get_continuity_score(self) -> float:
        return self.state.get_long_horizon_score()

    def build_real_trajectory_index(self, sample_artifacts_dir: Optional[Path] = None) -> Dict[str, Any]:
        summary = self.get_summary()
        real_episodes = self.get_real_mainline_episodes()
        first_episode = real_episodes[0] if real_episodes else None
        latest_episode = real_episodes[-1] if real_episodes else None
        sample_root = self._resolve_sample_artifacts_dir(sample_artifacts_dir)
        return {
            "schema_version": "mvp16.real_trajectory_index.v1",
            "generated_at": datetime.now().isoformat(),
            "state_path": self._repo_relative_ref(self._state_path),
            "sample_artifacts_dir": self._repo_relative_ref(sample_root),
            "summary": summary,
            "first_real_episode_ref": first_episode.sample_ref if first_episode else None,
            "latest_real_episode_ref": latest_episode.sample_ref if latest_episode else None,
            "episodes": [
                {
                    "episode_id": ep.episode_id,
                    "sample_ref": ep.sample_ref,
                    "ledger_ref": ep.ledger_ref,
                    "replay_ref": ep.replay_ref,
                    "session_id": ep.session_id,
                    "calendar_day": ep.calendar_day,
                    "final_action": ep.final_action,
                    "real_mainline": ep.real_mainline,
                    "proto_self_output_schema_version": ep.proto_self_output_schema_version,
                    "proto_self_trace_schema_version": ep.proto_self_trace_schema_version,
                    "governance_snapshot": ep.governance_snapshot,
                    "invariant_snapshot": ep.invariant_snapshot,
                }
                for ep in real_episodes
            ],
            "transitions": [
                {
                    "transition_id": transition.transition_id,
                    "transition_kind": transition.transition_kind,
                    "from_episode_ref": transition.from_episode_ref,
                    "to_episode_ref": transition.to_episode_ref,
                    "trigger_ref": transition.trigger_ref,
                    "replay_ref": transition.replay_ref,
                    "approved": transition.approved,
                    "approver": transition.approver,
                }
                for transition in self.state.trajectory.transitions
            ],
        }

    def build_real_trajectory_replay_audit(self) -> Dict[str, Any]:
        real_episodes = self.get_real_mainline_episodes()
        first_episode = real_episodes[0] if real_episodes else None
        latest_episode = real_episodes[-1] if real_episodes else None

        refs_to_check = []
        if first_episode:
            refs_to_check.extend([first_episode.sample_ref, first_episode.ledger_ref, first_episode.replay_ref])
        if latest_episode and latest_episode is not first_episode:
            refs_to_check.extend([latest_episode.sample_ref, latest_episode.ledger_ref, latest_episode.replay_ref])
        source_refs_intact = all(ref and self._path_from_ref(ref).exists() for ref in refs_to_check) if refs_to_check else False

        identity_preserved = bool(self.get_summary().get("identity_preserved", False))
        governance_preserved = bool(self.get_summary().get("governance_preserved", False))

        return {
            "schema_version": "mvp16.real_trajectory_replay_audit.v1",
            "generated_at": datetime.now().isoformat(),
            "first_real_episode_ref": first_episode.sample_ref if first_episode else None,
            "latest_real_episode_ref": latest_episode.sample_ref if latest_episode else None,
            "first_real_ledger_ref": first_episode.ledger_ref if first_episode else None,
            "latest_real_ledger_ref": latest_episode.ledger_ref if latest_episode else None,
            "first_real_replay_ref": first_episode.replay_ref if first_episode else None,
            "latest_real_replay_ref": latest_episode.replay_ref if latest_episode else None,
            "identity_preserved": identity_preserved,
            "governance_preserved": governance_preserved,
            "source_refs_intact": source_refs_intact,
            "transition_chain": [
                {
                    "transition_kind": transition.transition_kind,
                    "from_episode_ref": transition.from_episode_ref,
                    "to_episode_ref": transition.to_episode_ref,
                    "trigger_ref": transition.trigger_ref,
                    "replay_ref": transition.replay_ref,
                }
                for transition in self.state.trajectory.transitions
            ],
            "evidence_boundary": {
                "proves": [
                    "real_mainline_episodes are persisted with sample/ledger refs",
                    "first/latest real episodes can be replay-audited via refs",
                    "identity/governance snapshots remain attached to the real trajectory",
                ],
                "does_not_prove": [
                    "MVP16 passed",
                    "Stage 7 admitted",
                    "Open Developmental Self established",
                ],
            },
        }

    def write_admission_artifacts(
        self,
        *,
        observation_dir: Optional[Path] = None,
        sample_artifacts_dir: Optional[Path] = None,
    ) -> Dict[str, str]:
        output_dir = Path(observation_dir or DEFAULT_OBSERVATION_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)

        index_path = output_dir / "real_trajectory_index.json"
        audit_path = output_dir / "real_trajectory_replay_audit.json"

        index_payload = self.build_real_trajectory_index(sample_artifacts_dir=sample_artifacts_dir)
        audit_payload = self.build_real_trajectory_replay_audit()

        index_path.write_text(json.dumps(index_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        audit_path.write_text(json.dumps(audit_payload, indent=2, ensure_ascii=False), encoding="utf-8")

        return {
            "real_trajectory_index": self._repo_relative_ref(index_path),
            "real_trajectory_replay_audit": self._repo_relative_ref(audit_path),
        }

    def get_summary(self) -> Dict[str, Any]:
        return self._compute_projection_summary()


def get_developmental_manager(state_path: Optional[Path] = None) -> DevelopmentalManager:
    return DevelopmentalManager.get_instance(state_path=state_path)


def reset_developmental_manager(
    clear_persistence: bool = False,
    state_path: Optional[Path] = None,
) -> None:
    DevelopmentalManager.reset(clear_persistence=clear_persistence, state_path=state_path)
