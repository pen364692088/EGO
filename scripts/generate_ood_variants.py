#!/usr/bin/env python3
"""
OOD Variant Generator for OpenEmotion MVP-7.0

Generates out-of-distribution variants of existing scenarios
to test robustness and prevent overfitting.

Features:
- Deterministic generation with configurable seed
- Manifest output with scenario list + hash
- Reproducible OOD sets for auditing
"""

import os
import sys
import json
import yaml
import random
import argparse
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

@dataclass
class Transformation:
    """A transformation rule for generating OOD variants."""
    name: str
    description: str
    examples: List[str]

@dataclass
class OODManifest:
    """Manifest for OOD generation run."""
    seed: int
    generated_at: str
    total_variants: int
    scenarios: List[Dict[str, Any]]
    manifest_hash: str = ""
    
    def compute_hash(self) -> str:
        """Compute hash of manifest content."""
        content = json.dumps({
            "seed": self.seed,
            "total_variants": self.total_variants,
            "scenarios": sorted(self.scenarios, key=lambda x: x["variant_file"])
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

class OODVariantGenerator:
    """Generator for out-of-distribution scenario variants."""
    
    DEFAULT_SEED = 42
    
    def __init__(self, scenario_sets_path: str, seed: Optional[int] = None):
        """Initialize with scenario sets configuration and optional seed."""
        self.scenario_sets_path = Path(scenario_sets_path)
        self.scenarios_dir = self.scenario_sets_path.parent.parent / "scenarios"
        
        # Load scenario sets configuration
        with open(self.scenario_sets_path, 'r') as f:
            self.config = json.load(f)
        
        # Initialize transformation rules
        self.transformations = self._load_transformations()
        
        # Random seed for reproducibility (configurable)
        self.seed = seed if seed is not None else self.DEFAULT_SEED
        self.rng = random.Random(self.seed)
        
        print(f"OOD Generator initialized with seed={self.seed}")
    
    def _load_transformations(self) -> List[Transformation]:
        """Load transformation rules from config."""
        transformations = []
        for rule in self.config.get("generation_rules", {}).get("ood_variants", {}).get("transformations", []):
            transformations.append(Transformation(
                name=rule["name"],
                description=rule["description"],
                examples=rule["examples"]
            ))
        return transformations
    
    def generate_object_substitutions(self, text: str) -> str:
        """Replace object names with alternatives."""
        substitutions = {
            "user": ["person", "individual", "human", "client"],
            "system": ["assistant", "agent", "AI", "program"],
            "memory": ["storage", "database", "records", "archive"],
            "emotion": ["feeling", "sentiment", "affect", "mood"],
            "action": ["behavior", "response", "activity", "operation"],
            "goal": ["objective", "target", "aim", "purpose"],
            "strategy": ["approach", "method", "tactic", "plan"],
            "conflict": ["disagreement", "tension", "dispute", "friction"],
            "resolution": ["solution", "settlement", "outcome", "result"]
        }
        
        text_lower = text.lower()
        result = text
        
        for original, alternatives in substitutions.items():
            if original in text_lower:
                count = text_lower.count(original)
                substitutions_to_make = min(count, max(1, count // 2))
                
                for _ in range(substitutions_to_make):
                    alternative = self.rng.choice(alternatives)
                    result = result.replace(original, alternative, 1)
                    result = result.replace(original.capitalize(), alternative.capitalize(), 1)
        
        return result
    
    def generate_tone_variation(self, text: str) -> str:
        """Change tone while preserving meaning."""
        tone_mappings = {
            "urgent": ["important", "priority", "time-sensitive"],
            "calm": ["relaxed", "peaceful", "composed"],
            "formal": ["professional", "official", "business-like"],
            "casual": ["informal", "relaxed", "friendly"],
            "direct": ["straightforward", "explicit", "clear"],
            "polite": ["courteous", "respectful", "considerate"],
            "friendly": ["warm", "welcoming", "approachable"],
            "serious": ["solemn", "grave", "important"]
        }
        
        result = text
        text_lower = text.lower()
        
        for tone, alternatives in tone_mappings.items():
            if tone in text_lower:
                alternative = self.rng.choice(alternatives)
                result = result.replace(tone, alternative)
                result = result.replace(tone.capitalize(), alternative.capitalize())
        
        return result
    
    def generate_order_permutation(self, scenario_data: Dict[str, Any]) -> Dict[str, Any]:
        """Reorder sequence of events while maintaining causality."""
        result = scenario_data.copy()
        
        if "events" in result and isinstance(result["events"], list):
            events = result["events"].copy()
            if len(events) > 2:
                middle_events = events[1:-1]
                self.rng.shuffle(middle_events)
                result["events"] = [events[0]] + middle_events + [events[-1]]
        
        if "steps" in result and isinstance(result["steps"], list):
            steps = result["steps"].copy()
            if len(steps) > 2:
                middle_steps = steps[1:-1]
                self.rng.shuffle(middle_steps)
                result["steps"] = [steps[0]] + middle_steps + [steps[-1]]
        
        return result
    
    def generate_noise_injection(self, text: str) -> str:
        """Add irrelevant but plausible details."""
        noise_templates = [
            " (at {time})",
            " (noting that {detail})",
            " (while {context})",
            " (despite {condition})",
            " (according to {source})",
            " (as of {date})",
            " (in response to {trigger})",
            " (considering {factor})"
        ]
        
        noise_values = {
            "time": ["the same time", "that moment", "this point", "the present"],
            "detail": ["the background", "prior experience", "context", "history"],
            "context": ["other factors", "external conditions", "circumstances", "environment"],
            "condition": ["limitations", "constraints", "requirements", "expectations"],
            "source": ["records", "observations", "data", "analysis"],
            "date": ["recent data", "current information", "latest updates", "present status"],
            "trigger": ["events", "stimuli", "inputs", "signals"],
            "factor": ["implications", "consequences", "outcomes", "effects"]
        }
        
        sentences = text.split('. ')
        result_sentences = []
        
        for sentence in sentences:
            if sentence and self.rng.random() < 0.3:
                template = self.rng.choice(noise_templates)
                placeholder = template.split('{')[1].split('}')[0]
                value = self.rng.choice(noise_values[placeholder])
                noise = template.format(**{placeholder: value})
                result_sentences.append(sentence + noise)
            else:
                result_sentences.append(sentence)
        
        return '. '.join(result_sentences)
    
    def generate_paraphrase(self, text: str) -> str:
        """Rewrite using different vocabulary (simple implementation)."""
        paraphrases = {
            "the user": "the person",
            "the system": "the assistant",
            "should": "ought to",
            "will": "is expected to",
            "can": "is able to",
            "important": "significant",
            "necessary": "required",
            "possible": "feasible",
            "better": "preferable",
            "worse": "less desirable",
            "help": "assist",
            "solve": "resolve",
            "issue": "matter",
            "problem": "challenge",
            "solution": "resolution",
            "approach": "method",
            "result": "outcome",
            "process": "procedure",
            "information": "data",
            "response": "reaction",
            "decision": "choice",
            "action": "behavior",
            "behavior": "conduct",
            "feeling": "emotion",
            "emotion": "sentiment",
            "thought": "idea",
            "idea": "concept",
            "situation": "circumstance",
            "condition": "state"
        }
        
        result = text
        for original, alternative in paraphrases.items():
            result = result.replace(original, alternative)
        
        return result
    
    def apply_transformation(self, scenario_data: Dict[str, Any], 
                           transformation_name: str) -> Dict[str, Any]:
        """Apply a specific transformation to scenario data."""
        result = scenario_data.copy()
        yaml_str = yaml.dump(scenario_data, default_flow_style=False)
        
        if transformation_name == "object_substitution":
            yaml_str = self.generate_object_substitutions(yaml_str)
        elif transformation_name == "tone_variation":
            yaml_str = self.generate_tone_variation(yaml_str)
        elif transformation_name == "order_permutation":
            result = self.generate_order_permutation(result)
            return result
        elif transformation_name == "noise_injection":
            yaml_str = self.generate_noise_injection(yaml_str)
        elif transformation_name == "paraphrase":
            yaml_str = self.generate_paraphrase(yaml_str)
        
        try:
            result = yaml.safe_load(yaml_str)
        except yaml.YAMLError:
            result = scenario_data.copy()
        
        return result
    
    def generate_variants_for_scenario(self, scenario_path: Path, 
                                     num_variants: int = 2) -> List[Dict[str, Any]]:
        """Generate OOD variants for a specific scenario."""
        with open(scenario_path, 'r') as f:
            original_data = yaml.safe_load(f)
        
        variants = []
        used_transformations = set()
        
        for i in range(num_variants):
            available_transformations = [t for t in self.transformations 
                                       if t.name not in used_transformations]
            
            if not available_transformations:
                available_transformations = self.transformations.copy()
                used_transformations.clear()
            
            transformation = self.rng.choice(available_transformations)
            used_transformations.add(transformation.name)
            
            variant_data = self.apply_transformation(original_data, transformation.name)
            
            variant_data["ood_metadata"] = {
                "base_scenario": scenario_path.name,
                "transformation": transformation.name,
                "generation_timestamp": datetime.now(timezone.utc).isoformat(),
                "variant_id": f"{scenario_path.stem}_ood_variant_{i+1}",
                "generator_seed": self.seed
            }
            
            variants.append(variant_data)
        
        return variants
    
    def generate_all_ood_variants(self, output_dir: Optional[Path] = None) -> OODManifest:
        """Generate OOD variants for all scenarios and return manifest."""
        if output_dir is None:
            output_dir = self.scenarios_dir / "ood"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        scenarios_to_process = []
        
        for scenario_file in self.config.get("scenario_sets", {}).get("tune_set", {}).get("scenarios", []):
            scenario_path = self.scenarios_dir / scenario_file
            if scenario_path.exists():
                scenarios_to_process.append(scenario_path)
        
        for scenario_file in self.config.get("scenario_sets", {}).get("holdout_set", {}).get("scenarios", []):
            scenario_path = self.scenarios_dir / scenario_file
            if scenario_path.exists():
                scenarios_to_process.append(scenario_path)
        
        manifest_scenarios = []
        
        for scenario_path in scenarios_to_process:
            print(f"Generating variants for {scenario_path.name}...")
            
            variants = self.generate_variants_for_scenario(scenario_path, num_variants=2)
            
            for i, variant in enumerate(variants):
                base_name = scenario_path.stem
                variant_filename = f"{base_name}_ood_variant_{i+1}.yaml"
                output_path = output_dir / variant_filename
                
                with open(output_path, 'w') as f:
                    yaml.dump(variant, f, default_flow_style=False)
                
                # Compute file hash
                file_hash = hashlib.sha256(output_path.read_bytes()).hexdigest()[:16]
                
                manifest_scenarios.append({
                    "variant_file": variant_filename,
                    "base_scenario": scenario_path.name,
                    "transformation": variant["ood_metadata"]["transformation"],
                    "file_hash": file_hash
                })
                
                print(f"  Generated: {variant_filename} (hash: {file_hash})")
        
        # Create manifest
        manifest = OODManifest(
            seed=self.seed,
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_variants=len(manifest_scenarios),
            scenarios=manifest_scenarios
        )
        manifest.manifest_hash = manifest.compute_hash()
        
        return manifest
    
    def save_manifest(self, manifest: OODManifest, output_path: Path) -> None:
        """Save manifest to JSON file."""
        manifest_dict = asdict(manifest)
        with open(output_path, 'w') as f:
            json.dump(manifest_dict, f, indent=2)
        print(f"Manifest saved: {output_path}")
        print(f"Manifest hash: {manifest.manifest_hash}")
    
    def update_scenario_sets_config(self, ood_files: List[Path]) -> None:
        """Update scenario_sets.json with generated OOD scenarios."""
        ood_scenarios = [f.name for f in ood_files]
        
        if "scenario_sets" not in self.config:
            self.config["scenario_sets"] = {}
        if "ood_set" not in self.config["scenario_sets"]:
            self.config["scenario_sets"]["ood_set"] = {"scenarios": []}
        
        self.config["scenario_sets"]["ood_set"]["scenarios"] = ood_scenarios
        self.config["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        with open(self.scenario_sets_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        
        print(f"Updated scenario_sets.json with {len(ood_scenarios)} OOD scenarios")

def main():
    parser = argparse.ArgumentParser(description="Generate OOD variants for OpenEmotion scenarios")
    parser.add_argument("--input", default="scripts/scenario_sets.json", 
                       help="Path to scenario_sets.json configuration")
    parser.add_argument("--output", help="Output directory for OOD variants")
    parser.add_argument("--manifest", default="reports/ood_manifest.json",
                       help="Path to save manifest JSON")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed for deterministic generation")
    parser.add_argument("--scenarios", nargs="+", help="Specific scenarios to process")
    parser.add_argument("--num-variants", type=int, default=2, 
                       help="Number of variants to generate per scenario")
    parser.add_argument("--update-config", action="store_true",
                       help="Update scenario_sets.json with generated scenarios")
    
    args = parser.parse_args()
    
    generator = OODVariantGenerator(args.input, seed=args.seed)
    
    output_dir = Path(args.output) if args.output else None
    
    if args.scenarios:
        scenarios_dir = Path(args.input).parent.parent / "scenarios"
        generated_files = []
        manifest_scenarios = []
        
        for scenario_name in args.scenarios:
            scenario_path = scenarios_dir / scenario_name
            if scenario_path.exists():
                variants = generator.generate_variants_for_scenario(scenario_path, args.num_variants)
                
                out_dir = output_dir if output_dir else scenarios_dir / "ood"
                out_dir.mkdir(parents=True, exist_ok=True)
                
                for i, variant in enumerate(variants):
                    variant_filename = f"{scenario_path.stem}_ood_variant_{i+1}.yaml"
                    output_path = out_dir / variant_filename
                    
                    with open(output_path, 'w') as f:
                        yaml.dump(variant, f, default_flow_style=False)
                    
                    file_hash = hashlib.sha256(output_path.read_bytes()).hexdigest()[:16]
                    generated_files.append(output_path)
                    manifest_scenarios.append({
                        "variant_file": variant_filename,
                        "base_scenario": scenario_name,
                        "file_hash": file_hash
                    })
                    print(f"Generated: {variant_filename}")
            else:
                print(f"Scenario not found: {scenario_path}")
        
        manifest = OODManifest(
            seed=args.seed,
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_variants=len(manifest_scenarios),
            scenarios=manifest_scenarios
        )
        manifest.manifest_hash = manifest.compute_hash()
    else:
        out_dir = output_dir if output_dir else None
        manifest = generator.generate_all_ood_variants(out_dir)
        generated_files = [Path("scenarios/ood") / s["variant_file"] for s in manifest.scenarios]
    
    # Save manifest
    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    generator.save_manifest(manifest, manifest_path)
    
    # Update config if requested
    if args.update_config:
        generator.update_scenario_sets_config(generated_files)
    
    print(f"\nGenerated {manifest.total_variants} OOD variant scenarios")
    print(f"Seed: {args.seed} (deterministic)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
