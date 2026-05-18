#!/usr/bin/env python3
"""
Dual-Repo Artifact Comparison Script

对比 EgoCore 和 OpenEmotion 双边的 artifacts，验证 trace 对账和字段一致性。
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class ComparisonResult:
    """对比结果"""
    event_id: str
    case_id: str
    trace_id: str
    egocore_artifact_exists: bool
    openemotion_artifact_exists: bool
    trace_aligned: bool
    fields_aligned: bool
    mismatches: List[str]
    details: Dict[str, Any]


class DualRepoArtifactComparator:
    """双边 artifact 对账器"""
    
    def __init__(
        self,
        egocore_artifact_dir: Path,
        openemotion_artifact_dir: Path,
    ):
        self.egocore_artifact_dir = egocore_artifact_dir
        self.openemotion_artifact_dir = openemotion_artifact_dir
        
        self.results: List[ComparisonResult] = []
        self.stats = {
            "total_events": 0,
            "aligned_events": 0,
            "mismatched_events": 0,
            "missing_egocore": 0,
            "missing_openemotion": 0,
        }
    
    def compare_event(self, event_id: str) -> ComparisonResult:
        """对比单个事件的 artifacts"""
        result = ComparisonResult(
            event_id=event_id,
            case_id="",
            trace_id="",
            egocore_artifact_exists=False,
            openemotion_artifact_exists=False,
            trace_aligned=False,
            fields_aligned=False,
            mismatches=[],
            details={},
        )
        
        # 读取 EgoCore shadow artifact
        egocore_shadow_path = self.egocore_artifact_dir / "openemotion_shadow" / f"{event_id}.json"
        if egocore_shadow_path.exists():
            result.egocore_artifact_exists = True
            with open(egocore_shadow_path) as f:
                egocore_data = json.load(f)
            result.case_id = egocore_data.get("case_id", "")
            result.trace_id = egocore_data.get("trace_id", "")
            result.details["egocore"] = egocore_data
        else:
            result.mismatches.append(f"EgoCore shadow artifact not found: {egocore_shadow_path}")
        
        # 读取 OpenEmotion shadow artifact
        openemotion_shadow_path = self.openemotion_artifact_dir / "shadow" / f"{event_id}.json"
        if openemotion_shadow_path.exists():
            result.openemotion_artifact_exists = True
            with open(openemotion_shadow_path) as f:
                openemotion_data = json.load(f)
            result.details["openemotion"] = openemotion_data
        else:
            result.mismatches.append(f"OpenEmotion shadow artifact not found: {openemotion_shadow_path}")
        
        # 对比 trace_id
        if result.egocore_artifact_exists and result.openemotion_artifact_exists:
            egocore_trace = result.details.get("egocore", {}).get("trace_id", "")
            openemotion_trace = result.details.get("openemotion", {}).get("trace_id", "")
            
            if egocore_trace == openemotion_trace and egocore_trace:
                result.trace_aligned = True
            else:
                result.mismatches.append(f"Trace mismatch: EgoCore={egocore_trace}, OpenEmotion={openemotion_trace}")
            
            # 对比 case_id
            egocore_case = result.details.get("egocore", {}).get("case_id", "")
            openemotion_case = result.details.get("openemotion", {}).get("case_id", "")
            
            if egocore_case != openemotion_case:
                result.mismatches.append(f"Case ID mismatch: EgoCore={egocore_case}, OpenEmotion={openemotion_case}")
            
            # 对比关键字段
            egocore_result = result.details.get("egocore", {}).get("openemotion_result", {})
            openemotion_result = result.details.get("openemotion", {}).get("openemotion_result", {})
            
            field_mismatches = self._compare_fields(egocore_result, openemotion_result)
            if field_mismatches:
                result.mismatches.extend(field_mismatches)
            else:
                result.fields_aligned = True
        
        # 更新统计
        self.stats["total_events"] += 1
        if result.egocore_artifact_exists and result.openemotion_artifact_exists and result.trace_aligned:
            self.stats["aligned_events"] += 1
        else:
            self.stats["mismatched_events"] += 1
        
        if not result.egocore_artifact_exists:
            self.stats["missing_egocore"] += 1
        if not result.openemotion_artifact_exists:
            self.stats["missing_openemotion"] += 1
        
        return result
    
    def _compare_fields(self, egocore_result: Dict, openemotion_result: Dict) -> List[str]:
        """对比关键字段"""
        mismatches = []
        
        # 检查关键字段存在性
        key_fields = ["valence", "arousal", "status"]
        
        for field in key_fields:
            egocore_val = egocore_result.get(field)
            openemotion_val = openemotion_result.get(field)
            
            if egocore_val is not None and openemotion_val is not None:
                # 数值类型允许小误差
                if isinstance(egocore_val, (int, float)) and isinstance(openemotion_val, (int, float)):
                    if abs(egocore_val - openemotion_val) > 0.01:
                        mismatches.append(f"{field}: EgoCore={egocore_val}, OpenEmotion={openemotion_val}")
                elif egocore_val != openemotion_val:
                    mismatches.append(f"{field}: EgoCore={egocore_val}, OpenEmotion={openemotion_val}")
        
        return mismatches
    
    def compare_all(self, event_ids: List[str]) -> List[ComparisonResult]:
        """对比所有事件"""
        for event_id in event_ids:
            result = self.compare_event(event_id)
            self.results.append(result)
        
        return self.results
    
    def generate_summary(self) -> Dict[str, Any]:
        """生成对比摘要"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "stats": self.stats,
            "results": [asdict(r) for r in self.results],
            "verdict": {
                "all_aligned": self.stats["aligned_events"] == self.stats["total_events"],
                "alignment_rate": f"{self.stats['aligned_events']}/{self.stats['total_events']}",
            },
        }
    
    def save_summary(self, output_path: Path) -> None:
        """保存摘要"""
        summary = self.generate_summary()
        output_path.write_text(json.dumps(summary, indent=2, default=str))


def main():
    """主函数"""
    egocore_root = Path("/home/moonlight/Project/Github/MyProject/EgoCore")
    openemotion_root = Path("/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion")
    
    egocore_artifact_dir = egocore_root / "artifacts" / "dual_repo_closed_loop_v2"
    openemotion_artifact_dir = openemotion_root / "artifacts" / "dual_repo_closed_loop_v2"
    
    # 获取所有事件 ID
    egocore_ingress_dir = egocore_artifact_dir / "egocore_ingress"
    event_files = list(egocore_ingress_dir.glob("*.json"))
    event_ids = [f.stem for f in event_files]
    
    print("=" * 60)
    print("Dual-Repo Artifact Comparison")
    print("=" * 60)
    print(f"\nEgoCore artifact dir: {egocore_artifact_dir}")
    print(f"OpenEmotion artifact dir: {openemotion_artifact_dir}")
    print(f"Events to compare: {len(event_ids)}")
    
    # 执行对比
    comparator = DualRepoArtifactComparator(egocore_artifact_dir, openemotion_artifact_dir)
    results = comparator.compare_all(event_ids)
    
    # 打印结果
    print("\n" + "-" * 60)
    print("Comparison Results:")
    print("-" * 60)
    
    for result in results:
        status = "✅ ALIGNED" if result.trace_aligned and result.fields_aligned else "❌ MISMATCH"
        print(f"\n  {result.event_id}: {status}")
        print(f"    Case: {result.case_id}")
        print(f"    Trace: {result.trace_id}")
        print(f"    EgoCore artifact: {'✅' if result.egocore_artifact_exists else '❌'}")
        print(f"    OpenEmotion artifact: {'✅' if result.openemotion_artifact_exists else '❌'}")
        print(f"    Trace aligned: {'✅' if result.trace_aligned else '❌'}")
        print(f"    Fields aligned: {'✅' if result.fields_aligned else '❌'}")
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
    summary_path = egocore_artifact_dir / "compare_summary.json"
    comparator.save_summary(summary_path)
    print(f"\nSummary saved to: {summary_path}")
    
    # 返回状态
    if comparator.stats["aligned_events"] == comparator.stats["total_events"]:
        print("\n✅ ALL ARTIFACTS ALIGNED")
        return 0
    else:
        print("\n❌ SOME ARTIFACTS NOT ALIGNED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
