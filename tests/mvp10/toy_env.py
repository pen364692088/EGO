"""
T15 - Toy Environment for Testing

A simple toy environment for testing the executor.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from emotiond.executor_mvp10 import ToyEnvironment, ExecutorMVP10, OutcomeStatus, ExecutionOutcome


def demo_toy_env():
    """Demonstrate the toy environment."""
    print("=== Toy Environment Demo ===\n")
    
    env = ToyEnvironment(seed=42)
    
    # Set a problem to solve
    env.set_problem("bug_in_code")
    print(f"Initial state: {env.get_state()}\n")
    
    # Execute seek_info
    print("1. Executing seek_info...")
    outcome = env.execute("seek_info", {"query": "diagnose bug"})
    print(f"   Outcome: {outcome.status.value} - {outcome.reason}")
    print(f"   State: {env.get_state()}\n")
    
    # Execute attempt_solution
    print("2. Executing attempt_solution...")
    outcome = env.execute("attempt_solution", {"approach": "fix_bug"})
    print(f"   Outcome: {outcome.status.value} - {outcome.reason}")
    print(f"   State: {env.get_state()}\n")
    
    # Execute run_check
    print("3. Executing run_check...")
    outcome = env.execute("run_check", {"validation": "full"})
    print(f"   Outcome: {outcome.status.value} - {outcome.reason}")
    print(f"   State: {env.get_state()}\n")
    
    # Execute commit_progress
    print("4. Executing commit_progress...")
    outcome = env.execute("commit_progress", {"update": "bug_fixed"})
    print(f"   Outcome: {outcome.status.value} - {outcome.reason}")
    print(f"   State: {env.get_state()}\n")
    
    print("=== Demo Complete ===")


if __name__ == "__main__":
    demo_toy_env()
