#!/usr/bin/env python3
"""
Dual-Repo Transport Artifact Comparison Script v3

对比 EgoCore 和 OpenEmotion 双边的传输层 artifacts，验证 trace 对账和字段一致性。
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass, asdict


@dataclass
class TransportComparisonResult:
    """传输层对比结果"""
    event_id: str
    case_id: str
    trace_id: str
    request_artifact_exists: bool
    response_artifact_exists: bool
    openemotion_shadow_exists: bool
    trace_aligned: bool
    http_status: int
    duration_ms: float
    valence_match: bool
    mismatches: List[str]
    details: Dict[str, Any]


class DualRepoTransportComparator:
    """传输层 artifact 对账器"""
    
    def __init__(
        self,
        egocore_artifact_dir: Path,
        openemotion_artifact_dir: Path,
    ):
        self.egocore_artifact_dir = egocore_artifact_dir
        self.openemotion_artifact_dir = openemotion_artifact_dir
        
        self.results: List[TransportComparisonResult] = []
        self.stats = {
            "total_events": 0,
            "aligned_events": 0,
            "http_success": 0,
            "http_failure": 0,
            "missing_request": 0,
            "missing_response": 0,
            "missing_shadow": 0,
        }
    
    def compare_event(self, event_id: str) -> TransportComparisonResult:
        """对比单个事件的传输层 artifacts"""
        result = TransportComparisonResult(
            event_id=event_id,
            case_id="",
            trace_id="",
            request_artifact_exists=False,
            response_artifact_exists=False,
            openemotion_shadow_exists=False,
            trace_aligned=False,
            http_status=0,
            duration_ms=0.0,
            valence_match=False,
            mismatches=[],
            details={},
        )
        
        # 读取请求 artifact
        request_path = self.egocore_artifact_dir / "transport_requests" / f"{event_id}.json"
        if request_path.exists():
            result.request_artifact_exists = True
            with open(request_path) as f:
                request_data = json.load(f)
            result.case_id = request_data.get("case_id", "")
            result.trace_id = request_data.get("trace_id", "")
            result.details["request"] = request_data
        else:
            result.mismatches.append(f"Request artifact not found: {request_path}")
        
        # 读取响应 artifact
        response_path = self.egocore_artifact_dir / "transport_responses" / f"{event_id}.json"
        if response_path.exists():
            result.response_artifact_exists = True
            with open(response_path) as f:
                response_data = json.load(f)
            result.http_status = response_data.get("status_code", 0)
            result.duration_ms = response_data.get("duration_ms", 0.0)
            result.details["response"] = response_data
            
            # 检查 HTTP 状态
            if result.http_status == 200:
                response_body = response_data.get("response", {})
                result.details["valence"] = response_body.get("valence")
                result.details["arousal"] = response_body.get("arousal")
            else:
                result.mismatches.append(f"HTTP status not 200: {result.http_status}")
        else:
            result.mismatches.append(f"Response artifact not found: {response_path}")
        
        # 读取 OpenEmotion shadow artifact
        shadow_path = self.egocore_artifact_dir / "openemotion_shadow" / f"{event_id}.json"
        if shadow_path.exists():
            result.openemotion_shadow_exists = True
            with open(shadow_path) as f:
                shadow_data = json.load(f)
            result.details["shadow"] = shadow_data
            
            # 对比 trace_id
            shadow_trace = shadow_data.get("trace_id", "")
            if shadow_trace == result.trace_id and result.trace_id:
                result.trace_aligned = True
            else:
                result.mismatches.append(f"Trace mismatch: request={result.trace_id}, shadow={shadow_trace}")
            
            # 对比 valence
            shadow_result = shadow_data.get("openemotion_result", {})
            shadow_valence = shadow_result.get("valence")
            response_valence = result.details.get("valence")
            
            if shadow_valence is not None and response_valence is not None:
                if abs(shadow_valence - response_valence) < 0.01:
                    result.valence_match = True
                else:
                    result.mismatches.append(f"Valence mismatch: response={response_valence}, shadow={shadow_valence}")
        else:
            result.mismatches.append(f"Shadow artifact not found: {shadow_path}")
        
        # 更新统计
        self.stats["total_events"] += 1
        
        if result.request_artifact_exists:
            pass
        else:
            self.stats["missing_request"] += 1
        
        if result.response_artifact_exists:
            if result.http_status == 200:
                self.stats["http_success"] += 1
            else:
                self.stats["http_failure"] += 1
        else:
            self.stats["missing_response"] += 1
        
        if not result.openemotion_shadow_exists:
            self.stats["missing_shadow"] += 1
        
        if result.trace_aligned and result.valence_match:
            self.stats["aligned_events"] += 1
        
        return result
    
    def compare_all(self, event_ids: List[str]) -> List[TransportComparisonResult]:
        """对比所有事件"""
        for event_id in event_ids:
            result = self.compare_event(event_id)
            self.results.append(result)
        
        return self.results
    
    def generate_summary(self) -> Dict[str, Any]:
        """生成对比摘要"""
        return {
            "timestamp": datetime.now().isoformat(),
            "stats": self.stats,
            "results": [asdict(r) for r in self.results],
            "verdict": {
                "all_aligned": self.stats["aligned_events"] == self.stats["total_events"],
                "alignment_rate": f"{self.stats['aligned_events']}/{self.stats['total_events']}",
                "http_success_rate": f"{self.stats['http_success']}/{self.stats['total_events']}",
            },
        }
    
    def save_summary(self, output_path: Path) -> None:
        """保存摘要"""
        summary = self.generate_summary()
        output_path.write_text(json.dumps(summary, indent=2, default=str))


def main():
    """主函数"""
    egocore_root = Path("/home/moonlight/Project/Github/MyProject/EgoCore")
    
    egocore_artifact_dir = egocore_root / "artifacts" / "dual_repo_closed_loop_v3"
    
    # 获取所有事件 ID
    request_dir = egocore_artifact_dir / "transport_requests"
    event_files = list(request_dir.glob("*.json"))
    event_ids = [f.stem for f in event_files]
    
    print("=" * 60)
    print("Dual-Repo Transport Artifact Comparison v3")
    print("=" * 60)
    print(f"\nArtifact dir: {egocore_artifact_dir}")
    print(f"Events to compare: {len(event_ids)}")
    
    # 执行对比
    comparator = DualRepoTransportComparator(
        egocore_artifact_dir,
        egocore_artifact_dir,  # shadow 也在同一目录
    )
    results = comparator.compare_all(event_ids)
    
    # 打印结果
    print("\n" + "-" * 60)
    print("Comparison Results:")
    print("-" * 60)
    
    for result in results:
        status = "✅ ALIGNED" if result.trace_aligned and result.valence_match else "❌ MISMATCH"
        print(f"\n  {result.event_id}: {status}")
        print(f"    Case: {result.case_id}")
        print(f"    Trace: {result.trace_id}")
        print(f"    HTTP Status: {result.http_status}")
        print(f"    Duration: {result.duration_ms:.1f}ms")
        print(f"    Request artifact: {'✅' if result.request_artifact_exists else '❌'}")
        print(f"    Response artifact: {'✅' if result.response_artifact_exists else '❌'}")
        print(f"    Shadow artifact: {'✅' if result.openemotion_shadow_exists else '❌'}")
        print(f"    Trace aligned: {'✅' if result.trace_aligned else '❌'}")
        print(f"    Valence match: {'✅' if result.valence_match else '❌'}")
        if result.mismatches:
            print(f"    Mismatches:")
            for m in result.mismatches:
                print(f"      - {m}")
    
    # 打印统计
    print("\n" + "-" * 60)
    print("Summary:")
    print("-" * 60)
    for key, value in comparator.stats.items():
        print(f"  {key}: {value}")
    
    # 保存摘要
    summary_path = egocore_artifact_dir / "transport_compare_summary.json"
    comparator.save_summary(summary_path)
    print(f"\nSummary saved to: {summary_path}")
    
    # 返回状态
    if comparator.stats["aligned_events"] == comparator.stats["total_events"]:
        print("\n✅ ALL TRANSPORT ARTIFACTS ALIGNED")
        return 0
    else:
        print("\n❌ SOME TRANSPORT ARTIFACTS NOT ALIGNED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
