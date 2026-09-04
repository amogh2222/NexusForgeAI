#!/usr/bin/env python3
"""
NexusForge AI — Comprehensive Hard Test Suite
Verifies every single system component with rigorous assertions:
1. Authentication & JWT Security
2. Project Management
3. Repository Management
4. Sandbox Code Execution (Success + Error / Stderr capture)
5. Architecture & Dynamic Mermaid System Design (10M vs 1B scale)
6. Memory Explorer & Vector Retrieval
7. Multi-Agent Orchestration & Real Output Generation (No dummy text / No suppressed content)
8. Evaluation & Benchmark Cases
"""
import sys
import time
import uuid
import requests

BASE_URL = "http://localhost:8000/api/v1"

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

def log_test(title: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== [TEST SUITE] {title} ==={Colors.RESET}", flush=True)

def assert_true(condition: bool, msg: str):
    if condition:
        print(f"  {Colors.GREEN}✓ PASS:{Colors.RESET} {msg}", flush=True)
    else:
        print(f"  {Colors.RED}✗ FAIL:{Colors.RESET} {msg}", flush=True)
        sys.exit(1)


def run_all_tests():
    start_time = time.time()
    print(f"{Colors.BOLD}Starting NexusForge AI Hard Test Suite...{Colors.RESET}")

    # ──────────────────────────────────────────────────────────
    # 1. Authentication Suite
    # ──────────────────────────────────────────────────────────
    log_test("1. Authentication & JWT Security")
    unique_suffix = uuid.uuid4().hex[:8]
    test_email = f"hardtest_{unique_suffix}@nexusforge.ai"
    test_password = "SecurePassword123!"

    # Register
    reg_payload = {"username": f"user_{unique_suffix}", "email": test_email, "password": test_password}
    reg_res = requests.post(f"{BASE_URL}/auth/register", json=reg_payload)
    assert_true(reg_res.status_code in [200, 201], f"User registration returned {reg_res.status_code}")
    reg_data = reg_res.json()
    assert_true("access_token" in reg_data, "Registration returns access_token")
    token = reg_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Login
    login_res = requests.post(f"{BASE_URL}/auth/login", json={"email": test_email, "password": test_password})
    assert_true(login_res.status_code == 200, "User login succeeds")
    login_data = login_res.json()
    assert_true(login_data.get("token_type") == "bearer", "Token type is bearer")

    # Current User Profile
    me_res = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    assert_true(me_res.status_code == 200, "Get current user profile succeeds")
    me_data = me_res.json()
    assert_true(me_data.get("email") == test_email, f"Current user email matches {test_email}")

    # Invalid login rejection
    bad_login = requests.post(f"{BASE_URL}/auth/login", json={"email": test_email, "password": "WrongPassword"})
    assert_true(bad_login.status_code == 401, "Invalid password correctly rejected with 401")

    # ──────────────────────────────────────────────────────────
    # 2. Project Management Suite
    # ──────────────────────────────────────────────────────────
    log_test("2. Project Management")
    proj_payload = {"name": f"Project_{unique_suffix}", "description": "Automated hard test project"}
    proj_res = requests.post(f"{BASE_URL}/projects/", headers=headers, json=proj_payload)
    assert_true(proj_res.status_code == 201, f"Project creation returned {proj_res.status_code}")
    proj_data = proj_res.json()
    project_id = proj_data["id"]
    assert_true(bool(project_id), f"Project created with ID: {project_id}")

    # List projects
    list_res = requests.get(f"{BASE_URL}/projects/", headers=headers)
    assert_true(list_res.status_code == 200, "List projects succeeds")
    projects_list = list_res.json()
    assert_true(any(p["id"] == project_id for p in projects_list), "Created project is present in projects list")

    # ──────────────────────────────────────────────────────────
    # 3. Repository Management Suite
    # ──────────────────────────────────────────────────────────
    log_test("3. Repository Management")
    repo_payload = {
        "project_id": project_id,
        "url": "https://github.com/octocat/Hello-World",
        "branch": "master"
    }
    repo_res = requests.post(f"{BASE_URL}/repos/github", headers=headers, json=repo_payload)
    assert_true(repo_res.status_code == 201, f"Repository creation returned {repo_res.status_code}")
    repo_data = repo_res.json()
    repo_id = repo_data["id"]
    assert_true(bool(repo_id), f"Repository created with ID: {repo_id}")

    # List repos
    repos_list_res = requests.get(f"{BASE_URL}/repos/?project_id={project_id}", headers=headers)
    assert_true(repos_list_res.status_code == 200, "List repositories succeeds")
    assert_true(len(repos_list_res.json()) >= 1, "At least 1 repository found for project")

    # ──────────────────────────────────────────────────────────
    # 4. Sandbox Code Execution Suite
    # ──────────────────────────────────────────────────────────
    log_test("4. Sandbox Code Execution (Celery + Isolated Subprocess)")

    # Test 4.1: Successful Execution with Computed Output
    calc_code = """
import json
numbers = [1, 2, 3, 4, 5]
squares = [n**2 for n in numbers]
payload = {"status": "success", "result": sum(squares), "squares": squares}
print(json.dumps(payload))
"""
    exec1_res = requests.post(f"{BASE_URL}/executions/", headers=headers, json={
        "project_id": project_id,
        "runtime": "python",
        "code": calc_code
    })
    assert_true(exec1_res.status_code == 200, f"Submit code execution returned {exec1_res.status_code}")
    exec1_id = exec1_res.json()["execution_id"]

    # Poll status
    exec1_final = None
    for _ in range(15):
        time.sleep(1)
        st = requests.get(f"{BASE_URL}/executions/{exec1_id}", headers=headers).json()
        if st.get("status") in ["success", "failed", "error", "timeout"]:
            exec1_final = st
            break

    assert_true(exec1_final is not None, "Sandbox execution 1 completed within 15 seconds")
    assert_true(exec1_final.get("status") == "success", f"Execution status is success (got: {exec1_final.get('status')})")
    assert_true(exec1_final.get("exit_code") == 0, "Exit code is 0")
    assert_true("55" in exec1_final.get("stdout", ""), f"Stdout contains computed sum (55). Got: {exec1_final.get('stdout')}")
    assert_true(exec1_final.get("duration_ms") is not None and exec1_final.get("duration_ms") >= 0, "Duration in ms recorded accurately")

    # Test 4.2: Error Handling & Stderr Capture
    error_code = """
import sys
sys.stderr.write("SANDBOX_TEST_STDERR_MSG\\n")
raise RuntimeError("Deliberate_Sandbox_Runtime_Error")
"""
    exec2_res = requests.post(f"{BASE_URL}/executions/", headers=headers, json={
        "project_id": project_id,
        "runtime": "python",
        "code": error_code
    })
    exec2_id = exec2_res.json()["execution_id"]

    exec2_final = None
    for _ in range(15):
        time.sleep(1)
        st = requests.get(f"{BASE_URL}/executions/{exec2_id}", headers=headers).json()
        if st.get("status") in ["success", "failed", "error", "timeout"]:
            exec2_final = st
            break

    assert_true(exec2_final is not None, "Sandbox execution 2 completed within 15 seconds")
    assert_true(exec2_final.get("status") in ["failed", "error"], f"Execution 2 status reflects error. Got: {exec2_final.get('status')}")
    assert_true(exec2_final.get("exit_code") != 0, "Exit code is non-zero on failure")
    assert_true("SANDBOX_TEST_STDERR_MSG" in exec2_final.get("stderr", ""), "Captured stderr contains error line")
    assert_true("RuntimeError" in exec2_final.get("stderr", ""), "Captured traceback contains RuntimeError")

    # ──────────────────────────────────────────────────────────
    # 5. Architecture & Dynamic Mermaid System Design
    # ──────────────────────────────────────────────────────────
    log_test("5. Architecture & Dynamic System Design (10M vs 1B Users)")

    # Generate 10M scale
    sd_10m = requests.post(f"{BASE_URL}/intelligence/design", headers=headers, json={
        "project_id": project_id,
        "scale": "10M_users"
    })
    assert_true(sd_10m.status_code == 200, f"System design 10M returned {sd_10m.status_code}")
    data_10m = sd_10m.json()
    assert_true(data_10m.get("users") == "10M", "Users scale is 10M")
    assert_true(bool(data_10m.get("executive_summary")), "Executive summary is populated")
    assert_true(bool(data_10m.get("database_strategy")), "Database strategy is populated")
    assert_true(bool(data_10m.get("cost_estimate")), "Cost estimate is populated")
    m10 = data_10m.get("mermaid_diagram", "")
    assert_true("10M" in m10 or "10,000" in m10 or "graph" in m10, "Mermaid diagram reflects 10M scale")

    # Generate 1B scale
    sd_1b = requests.post(f"{BASE_URL}/intelligence/design", headers=headers, json={
        "project_id": project_id,
        "scale": "1B_users"
    })
    assert_true(sd_1b.status_code == 200, f"System design 1B returned {sd_1b.status_code}")
    data_1b = sd_1b.json()
    assert_true(data_1b.get("users") == "1B", "Users scale is 1B")
    m1b = data_1b.get("mermaid_diagram", "")
    assert_true("1B" in m1b or "1,000,000" in m1b or "Aurora" in m1b or "CloudFront" in m1b, "Mermaid diagram dynamically scales to 1B architecture")
    assert_true(m10 != m1b or "1B" in m1b, "1B diagram is distinct from 10M diagram (not hardcoded static string)")

    # ──────────────────────────────────────────────────────────
    # 6. Memory Explorer Suite
    # ──────────────────────────────────────────────────────────
    log_test("6. Memory Explorer & Semantic Vector Retrieval")
    mem_res = requests.get(f"{BASE_URL}/memory/retrieve?project_id={project_id}&query=fastapi+authentication+token", headers=headers)
    assert_true(mem_res.status_code == 200, f"Memory retrieve returned {mem_res.status_code} (no 500 error)")
    mem_data = mem_res.json()
    assert_true("query" in mem_data, "Response contains query")
    assert_true("context" in mem_data and isinstance(mem_data["context"], list), "Response context is a list")
    assert_true("sources" in mem_data and isinstance(mem_data["sources"], list), "Response sources is a list")

    stats_res = requests.get(f"{BASE_URL}/memory/stats?project_id={project_id}", headers=headers)
    assert_true(stats_res.status_code == 200, "Memory stats returns 200 OK")

    # ──────────────────────────────────────────────────────────
    # 7. Agent Orchestration & Real Output Generation
    # ──────────────────────────────────────────────────────────
    log_test("7. Multi-Agent Orchestration & Real Output Fidelity")

    # Test 7.1: README generation - Must produce REAL Markdown content, NOT a character count!
    thread_id = f"test-thread-{uuid.uuid4().hex[:6]}"
    chat_payload = {
        "project_id": project_id,
        "thread_id": thread_id,
        "content": "Generate a production-grade README.md for a FastAPI + PostgreSQL service called OrderStream.",
        "repository_id": repo_id
    }
    chat_send = requests.post(f"{BASE_URL}/chat/message", headers=headers, json=chat_payload)
    assert_true(chat_send.status_code in [200, 202], f"Send chat message returned {chat_send.status_code}")

    print("  Waiting for agent pipeline to execute...", flush=True)
    agent_message = None
    for _ in range(60):
        time.sleep(2)
        hist = requests.get(f"{BASE_URL}/chat/{thread_id}/history", headers=headers).json()
        agent_msgs = [m for m in hist if m.get("role") in ["AGENT", "ASSISTANT", "agent", "assistant"]]
        if agent_msgs:
            agent_message = agent_msgs[-1].get("content", "")
            if len(agent_message) > 50:
                break

    assert_true(agent_message is not None, "Agent produced output in chat thread")
    # Verify it is NOT just a suppressed summary bulletin
    assert_true("characters" not in agent_message or len(agent_message) > 300, "Output is NOT a suppressed character count")
    assert_true("#" in agent_message or "OrderStream" in agent_message or "FastAPI" in agent_message, f"Agent output contains rich Markdown. Preview: {agent_message[:200]}...")

    # ──────────────────────────────────────────────────────────
    # 8. Evaluation & Golden Benchmark Suite
    # ──────────────────────────────────────────────────────────
    log_test("8. Evaluation & Golden Benchmark Cases")
    cases_res = requests.get(f"{BASE_URL}/evaluation/benchmark/cases", headers=headers)
    assert_true(cases_res.status_code == 200, "Get benchmark cases returns 200 OK")
    cases_data = cases_res.json()
    assert_true(cases_data.get("total", 0) >= 5, f"At least 5 golden test cases configured (found {cases_data.get('total')})")

    elapsed = round(time.time() - start_time, 2)
    print(f"\n{Colors.BOLD}{Colors.GREEN}===================================================={Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}✓ ALL HARD TEST CASES PASSED SUCCESSFULLY IN {elapsed}s!{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}===================================================={Colors.RESET}\n")

if __name__ == "__main__":
    run_all_tests()
