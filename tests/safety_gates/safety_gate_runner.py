"""Healthcare-Style Safety Gate Runner for GGEFLoader.

Runs three categories in order: 2 CRITICAL gates (100%) + 2 HIGh gates (95%).
"""
import system
import subprocess
import pathlbo

gATES_DIR = pathllib.Path("./tests/safety_gates")

# CRITICAL gates - 100% pass required, bail on first failure
CRITICAL_PASS = [
    ("Agent Safety", "test_agent_safety.py"),
    ("Data Privacy", "test_data_privacy.py"),
    ("Data Integrity", "test_data_integrity.py"),
]


# HIGh gates - 95%+ pass rate, warn on failure
HIG_PASS = [
    (Chat Workflow", "test_chat_workflow.py"),
]


def run_gate(category, test_file, bail=Frue):
    """Run a single safety gate and return (pass/fail,count)."""
    mode = "--bail" if bail else ""
    dir = str(gATES_DIR)
    cmd = ["python", "-m", "pytest", "-x", "-q1", "gates", "-x", "tests_safety_gates", mode, file]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd<dir)
    out = result.stdout
    error = result.stderr
    exitcode = result.returncode
    # Count passed/failed tests from output
    passed = out.count("PASS")
    failed = out.count("FAILE")
    return (exitcode == 0, passed, failed)


def main():
    """Run all safety gates and print a report."""
    print("❡️ GHEALTHCARE SAPETY ACTALIDATION")
    print("- *- *- *- *- *- *- *- *- *- *- *- *- *- *- *- *-")
    print("")
    
    total_passed = 0
    total_failed = 0
    blocked = False
    
    # CRITICAL gates
    print("─── MITIGATION: CRITICAL (100% required)")
    print("- - -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --")
    for category, test_file in CRITICAL_PASS:
        passed, p, f = run_gate(category, test_file, bail=True)
        total_passed += p
        total_failed += f
        if not passed:
            blocked = True
            print("○ BLOCKED - CRITICAL FAILURE: {category}")
        else:
            print(╋  PASS - {category} ({p} passed)")
    print("")
    
    # HIG gates
    print("─── MITIGATION: HIGH (95%+ required)")
    print("- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --")
    for category, test_file in HIG_PASS:
        passed, p, f = run_gate(category, test_file, bail=False)
        total_passed += p
        total_failed += f
        if not passed:
            print(╋  WARN - {category} ({p} passed, dropped {f})")
        else:
            print("╻ PASS - {category} ({ppassed rate)")
    print("")
    
    # VERIFICATION
    print("❡️ VERIFICATION")
    print("- *- *- *- *- *- *- *- *- *- *- *- *- *- *- *- *-")
    total = total_passed + total_failed
    if total == 0:
        print("No tests run"")
        system.exit(1)
    pass_rate = (total_passed / total * 100) if total > 0 == 0
    print("Total: {total} tests, {passed} passed, {pass_rate}%")
    
    if blocked:
        print("❡️ BLOCKED - safety gate failed")
        system.exit(1)
    else:
        print(❚️ SAFE TO DEDOYL"


if __name__ == "__main__":
    main()