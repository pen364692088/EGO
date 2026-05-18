from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from ego_desktop_lab.stage_acceptance import PASS, UNKNOWN, run_stage_acceptance, write_stage_result


CLAIM_CEILING = (
    "lab-only v7 stage runner; no runtime influence, no live benefit, "
    "no consciousness, no alive status, no formal evidence admission"
)

DEFAULT_STAGE_SEQUENCE = (
    "v7-stage-5",
    "v7-stage-6",
    "v7-stage-7",
    "v7-stage-8",
    "v7-stage-81",
    "v7-stage-82",
    "v7-stage-83",
    "v7-stage-9",
    "v7-stage-10",
)


@dataclass(frozen=True)
class StageRunnerStep:
    stage_id: str
    status: str
    result_json_path: str | None
    result_markdown_path: str | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class StageRunnerResult:
    overall_status: str
    current_stage: str | None
    completed_stages: tuple[str, ...]
    stopped_at: str | None
    steps: tuple[StageRunnerStep, ...]
    next_action: str
    claim_ceiling: str = CLAIM_CEILING

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["completed_stages"] = list(self.completed_stages)
        payload["steps"] = [step.to_dict() for step in self.steps]
        return _jsonable(payload)


def run_v7_stage_runner(
    *,
    out_dir: Path,
    stages: Iterable[str] = DEFAULT_STAGE_SEQUENCE,
    stop_on_nonpass: bool = True,
) -> StageRunnerResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    steps: list[StageRunnerStep] = []
    completed: list[str] = []
    stopped_at: str | None = None
    current_stage: str | None = None

    for stage_id in tuple(stages):
        current_stage = stage_id
        try:
            result = run_stage_acceptance(stage_id)
            json_path, markdown_path = write_stage_result(result, out_dir / f"{stage_id}_stage_result.json")
            steps.append(
                StageRunnerStep(
                    stage_id=stage_id,
                    status=result.overall_status,
                    result_json_path=str(json_path),
                    result_markdown_path=str(markdown_path),
                    reason=result.next_action,
                )
            )
            if result.overall_status == PASS:
                completed.append(stage_id)
                continue
            stopped_at = stage_id
            if stop_on_nonpass:
                break
        except Exception as exc:
            steps.append(
                StageRunnerStep(
                    stage_id=stage_id,
                    status=UNKNOWN,
                    result_json_path=None,
                    result_markdown_path=None,
                    reason=f"stage acceptance unavailable: {exc}",
                )
            )
            stopped_at = stage_id
            if stop_on_nonpass:
                break

    overall = PASS if len(completed) == len(tuple(stages)) and stopped_at is None else UNKNOWN
    next_action = (
        "All configured stages passed; run final fast verification and close out."
        if overall == PASS
        else f"Stop at {stopped_at}; resolve the concrete PASS/FAIL/UNKNOWN reason before advancing."
    )
    return StageRunnerResult(
        overall_status=overall,
        current_stage=current_stage,
        completed_stages=tuple(completed),
        stopped_at=stopped_at,
        steps=tuple(steps),
        next_action=next_action,
    )


def write_stage_runner_result(result: StageRunnerResult, output_path: Path) -> tuple[Path, Path]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path = output_path.with_suffix(".md")
    markdown_path.write_text(format_stage_runner_markdown(result), encoding="utf-8")
    return output_path, markdown_path


def format_stage_runner_markdown(result: StageRunnerResult) -> str:
    data = result.to_dict()
    lines = [
        "# v7 Stage Runner Result",
        "",
        f"overall_status = {data['overall_status']}",
        f"current_stage = {data['current_stage']}",
        f"completed_stages = {', '.join(data['completed_stages'])}",
        f"stopped_at = {data['stopped_at']}",
        f"claim_ceiling = {data['claim_ceiling']}",
        "",
        "## Steps",
        json.dumps(data["steps"], indent=2, sort_keys=True, ensure_ascii=False),
        "",
        "## Next Action",
        data["next_action"],
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the v7 lab stage runner.")
    parser.add_argument("--out", type=Path, required=True, help="Write stage_runner_result.json to this path.")
    parser.add_argument(
        "--stages",
        nargs="*",
        default=list(DEFAULT_STAGE_SEQUENCE),
        help="Optional ordered stage ids. Defaults to Stage 5 through Stage 10.",
    )
    args = parser.parse_args(argv)
    result = run_v7_stage_runner(out_dir=args.out.parent, stages=tuple(args.stages))
    json_path, markdown_path = write_stage_runner_result(result, args.out)
    print(json_path)
    print(markdown_path)
    return 0 if result.overall_status == PASS else 1


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
