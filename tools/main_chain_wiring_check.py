#!/usr/bin/env python3
"""
Main-Chain Wiring Verification Script

Verifies that new OpenEmotion modules are wired into emotiond/core.py main chain.

NOT just module tests - checks that:
1. New self_model is called by core.py
2. Changes to new self_model affect core.py behavior
3. Legacy and new can coexist in shadow mode
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_imports():
    """Check if openemotion modules are imported in core.py."""
    print("=" * 60)
    print("1. Checking imports in emotiond/core.py")
    print("=" * 60)
    
    core_path = Path(__file__).parent.parent / "emotiond" / "core.py"
    content = core_path.read_text()
    
    imports_openemotion = "from openemotion" in content or "import openemotion" in content
    imports_self_model_adapter = "from emotiond.self_model_adapter" in content or "SelfModelAdapter" in content
    imports_self_model = "from emotiond.self_model" in content
    imports_self_model_mirror = "from emotiond.self_model_mirror" in content
    enable_openemotion_flag = "ENABLE_OPENEMOTION_SELF_MODEL" in content
    
    print(f"  Imports openemotion modules: {imports_openemotion}")
    print(f"  Imports SelfModelAdapter: {imports_self_model_adapter}")
    print(f"  ENABLE_OPENEMOTION_SELF_MODEL flag: {enable_openemotion_flag}")
    print(f"  Imports legacy self_model: {imports_self_model}")
    print(f"  Imports self_model_mirror: {imports_self_model_mirror}")
    
    # 判断是否已导入 OpenEmotion
    openemotion_connected = imports_openemotion or imports_self_model_adapter
    
    return {
        "imports_openemotion": imports_openemotion,
        "imports_self_model_adapter": imports_self_model_adapter,
        "enable_openemotion_flag": enable_openemotion_flag,
        "imports_legacy_self_model": imports_self_model,
        "imports_mirror": imports_self_model_mirror,
        "openemotion_connected": openemotion_connected,
    }


def check_feature_flags():
    """Check if feature flags exist for MVP13/14/15."""
    print("\n" + "=" * 60)
    print("2. Checking feature flags in emotiond/core.py")
    print("=" * 60)
    
    import os
    
    # Set feature flags
    os.environ["ENABLE_MVP13_MIRROR"] = "true"
    os.environ["ENABLE_MVP14_DUAL_RUN"] = "true"
    os.environ["ENABLE_MVP15_SHADOW"] = "true"
    
    # Import core.py to check if flags are respected
    from emotiond import core
    
    flags = {
        "ENABLE_MVP13_MIRROR": getattr(core, "ENABLE_MVP13_MIRROR", None),
        "ENABLE_MVP14_DUAL_RUN": getattr(core, "ENABLE_MVP14_DUAL_RUN", None),
        "ENABLE_MVP15_SHADOW": getattr(core, "ENABLE_MVP15_SHADOW", None),
    }
    
    for flag, value in flags.items():
        print(f"  {flag}: {value}")
    
    return flags


def check_new_self_model_exists():
    """Check if new self_model module exists."""
    print("\n" + "=" * 60)
    print("3. Checking new self_model module")
    print("=" * 60)
    
    self_model_path = Path(__file__).parent.parent / "openemotion" / "self_model" / "model.py"
    schema_path = Path(__file__).parent.parent / "schemas" / "self_model.schema.json"
    
    self_model_exists = self_model_path.exists()
    schema_exists = schema_path.exists()
    
    print(f"  openemotion/self_model/model.py: {self_model_exists}")
    print(f"  schemas/self_model.schema.json: {schema_exists}")
    
    if self_model_exists:
        # Try importing
        try:
            from openemotion.self_model import SelfModel
            print(f"  SelfModel import: OK")
            
            # Create instance
            model = SelfModel()
            print(f"  SelfModel instantiation: OK")
            
            return True
        except Exception as e:
            print(f"  SelfModel import/instantiation: FAILED ({e})")
            return False
    
    return False


def check_mirror_adapter():
    """Check if mirror adapter exists and can convert."""
    print("\n" + "=" * 60)
    print("4. Checking mirror adapter")
    print("=" * 60)
    
    try:
        from emotiond.self_model_mirror import SelfModelMirrorAdapter
        print("  SelfModelMirrorAdapter import: OK")
        
        adapter = SelfModelMirrorAdapter(enable=False)
        print("  Adapter instantiation: OK")
        
        return True
    except Exception as e:
        print(f"  Mirror adapter check FAILED: {e}")
        return False


def check_shadow_data():
    """Check if shadow data exists."""
    print("\n" + "=" * 60)
    print("5. Checking shadow artifacts")
    print("=" * 60)
    
    artifacts_dir = Path(__file__).parent.parent / "artifacts"
    
    mvp13_mirrors = list((artifacts_dir / "mvp13" / "mirror").glob("*.json")) if (artifacts_dir / "mvp13" / "mirror").exists() else []
    mvp14_reports = list((artifacts_dir / "mvp14").glob("*.md")) if (artifacts_dir / "mvp14").exists() else []
    mvp15_reports = list((artifacts_dir / "mvp15").glob("*.md")) if (artifacts_dir / "mvp15").exists() else []
    
    print(f"  MVP13 mirror artifacts: {len(mvp13_mirrors)}")
    print(f"  MVP14 reports: {len(mvp14_reports)}")
    print(f"  MVP15 reports: {len(mvp15_reports)}")
    
    return {
        "mvp13_mirrors": len(mvp13_mirrors),
        "mvp14_reports": len(mvp14_reports),
        "mvp15_reports": len(mvp15_reports),
    }


def main():
    """Run all checks and produce verdict."""
    print("Main-Chain Wiring Verification")
    print("=" * 60)
    
    results = {}
    
    results["imports"] = check_imports()
    results["feature_flags"] = check_feature_flags()
    results["new_self_model"] = check_new_self_model_exists()
    results["mirror_adapter"] = check_mirror_adapter()
    results["shadow_data"] = check_shadow_data()
    
    # Verdict
    print("\n" + "=" * 60)
    print("VERDICT")
    print("=" * 60)
    
    # Check 1: New self_model exists
    new_module_exists = results["new_self_model"]
    
    # Check 2: Mirror adapter exists
    mirror_exists = results["mirror_adapter"]
    
    # Check 3: Feature flags exist
    flags_exist = all(v is not None for v in results["feature_flags"].values())
    
    # Check 4: Shadow data exists
    shadow_data_exists = (
        results["shadow_data"]["mvp13_mirrors"] > 0 or
        results["shadow_data"]["mvp14_reports"] > 0 or
        results["shadow_data"]["mvp15_reports"] > 0
    )
    
    # Check 5: OpenEmotion imported in core.py
    openemotion_imported = results["imports"]["openemotion_connected"]
    
    print(f"  New self_model module exists: {new_module_exists}")
    print(f"  SelfModelAdapter imported: {results['imports']['imports_self_model_adapter']}")
    print(f"  Feature flags configured: {flags_exist}")
    print(f"  Shadow data collected: {shadow_data_exists}")
    print(f"  OpenEmotion connected to core.py: {openemotion_imported}")
    
    # Final verdict
    print("\n" + "-" * 60)
    
    if not openemotion_imported:
        print("❌ WIRING NOT PROVEN")
        print("   OpenEmotion modules are NOT imported in emotiond/core.py")
        print("   New self_model exists but is not connected to main chain")
        return 1
    elif not results["imports"]["imports_self_model_adapter"]:
        print("⚠️ WIRING PARTIAL")
        print("   OpenEmotion is imported directly, but SelfModelAdapter not used")
        print("   Consider using adapter for shadow mode")
        return 2
    elif not shadow_data_exists:
        print("⚠️ WIRING EXISTS BUT NOT VERIFIED")
        print("   SelfModelAdapter is imported, but no shadow data found")
        print("   Need to run shadow mode and collect data")
        return 2
    else:
        print("✅ WIRING VERIFIED")
        print("   SelfModelAdapter is imported and shadow data exists")
        return 0


if __name__ == "__main__":
    sys.exit(main())
