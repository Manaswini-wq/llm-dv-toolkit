"""Tests for log analyzer module."""

from pathlib import Path

import pytest

from llm_dv_toolkit.debug_assistant.log_analyzer import LogParser, ErrorEntry
from llm_dv_toolkit.debug_assistant.failure_classifier import (
    FailureClassifier, FailureCategory, cosine_similarity, simple_embedding,
)


@pytest.fixture
def sample_log(tmp_path: Path) -> Path:
    log = tmp_path / "test.log"
    log.write_text(
        "Info: Simulation started\n"
        "UVM_INFO @ 100ns: Starting test\n"
        "UVM_ERROR @ 500ns [scoreboard]: DATA MISMATCH addr=0x04 expected=0xA5 actual=0x00\n"
        "UVM_INFO @ 600ns: Test finishing\n"
        "UVM_ERROR : 1\n"
        "UVM_FATAL : 0\n"
    )
    return log


@pytest.fixture
def classifier(tmp_path: Path) -> FailureClassifier:
    c = FailureClassifier(tmp_path / "test_kb.db")
    yield c
    c.close()


def test_parse_uvm_error(sample_log: Path):
    parser = LogParser()
    errors = parser.parse(sample_log)
    assert len(errors) >= 1
    assert errors[0].severity == "ERROR"
    assert "MISMATCH" in errors[0].message


def test_parse_missing_log(tmp_path: Path):
    parser = LogParser()
    errors = parser.parse(tmp_path / "nonexistent.log")
    assert len(errors) == 1
    assert errors[0].severity == "ERROR"


def test_error_fingerprint():
    e1 = ErrorEntry(severity="ERROR", message="DATA MISMATCH addr=0x04")
    e2 = ErrorEntry(severity="ERROR", message="DATA MISMATCH addr=0x04")
    assert e1.fingerprint == e2.fingerprint


def test_cosine_similarity():
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    assert abs(cosine_similarity(a, b) - 1.0) < 1e-6

    c = [0.0, 1.0, 0.0]
    assert abs(cosine_similarity(a, c)) < 1e-6


def test_simple_embedding():
    emb = simple_embedding("data mismatch error")
    assert len(emb) == 64
    # Normalized
    norm = sum(x * x for x in emb) ** 0.5
    assert abs(norm - 1.0) < 0.01


def test_classifier_rule_based(classifier: FailureClassifier):
    result = classifier.classify("DATA MISMATCH expected=0xFF actual=0x00")
    assert result.category == FailureCategory.RTL_BUG

    result = classifier.classify("Simulation timeout at 1000us")
    assert result.category == FailureCategory.ENV_ISSUE


def test_classifier_knowledge_base(classifier: FailureClassifier):
    classifier.add_known_failure(
        "DATA MISMATCH on AXI read at addr 0x10",
        FailureCategory.RTL_BUG,
        "Fixed pipeline hazard in read path",
    )
    result = classifier.classify("DATA MISMATCH on AXI read at addr 0x14")
    # Should find similar
    assert result.category == FailureCategory.RTL_BUG
