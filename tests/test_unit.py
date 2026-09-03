"""
Unit tests for NexusForge AI core components.
These tests run without external network dependencies during CI.
"""
from backend.core.config import settings
from backend.core.security import hash_password, verify_password, create_access_token
from evaluation.benchmark_suite import GOLDEN_TEST_CASES, BenchmarkSuite


def test_settings_configuration():
    """Verify application configuration defaults."""
    assert settings.APP_NAME == "NexusForge AI"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0


def test_password_hashing():
    """Verify password hashing and verification."""
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_generation():
    """Verify JWT access token generation."""
    token = create_access_token("user-test-id-1234")
    assert isinstance(token, str)
    assert len(token) > 20


def test_golden_benchmark_cases():
    """Verify golden test cases are properly registered with rubrics and keywords."""
    assert len(GOLDEN_TEST_CASES) >= 5
    case_ids = {c.id for c in GOLDEN_TEST_CASES}
    assert "readme-001" in case_ids
    assert "bugfix-001" in case_ids
    assert "review-001" in case_ids
    assert "arch-001" in case_ids
    assert "sysdesign-001" in case_ids

    for case in GOLDEN_TEST_CASES:
        assert case.rubric_name in ["README_RUBRIC", "BUG_FIX_RUBRIC", "CODE_REVIEW_RUBRIC", "ARCHITECTURE_RUBRIC"]
        assert len(case.expected_keywords) > 0
        assert case.timeout_seconds > 0


def test_benchmark_suite_initialization():
    """Verify BenchmarkSuite initializes with golden cases."""
    suite = BenchmarkSuite()
    assert suite.PASS_THRESHOLD == 70.0
