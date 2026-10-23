"""Tests for test generator module."""

import asyncio

import pytest

from llm_dv_toolkit.test_generator.generator import TestGenerator, GenerationResult
from llm_dv_toolkit.test_generator.sv_parser import SVValidator
from llm_dv_toolkit.test_generator.prompt_templates import PromptTemplates
from llm_dv_toolkit.utils.config import Config, LLMConfig


@pytest.fixture
def config() -> Config:
    return Config(llm=LLMConfig(provider="openai", api_key="test-key"))


@pytest.fixture
def validator() -> SVValidator:
    return SVValidator()


def test_sv_validator_balanced(validator: SVValidator):
    code = "class foo extends uvm_sequence;\n`uvm_object_utils(foo)\nendclass"
    issues = validator.validate(code)
    assert not any("Unbalanced" in i for i in issues)


def test_sv_validator_unbalanced(validator: SVValidator):
    code = "class foo extends uvm_sequence;\nfunction new();\nendclass"
    issues = validator.validate(code)
    assert any("endfunction" in i for i in issues)


def test_sv_validator_missing_utils(validator: SVValidator):
    code = "class foo extends uvm_sequence #(item);\nendclass"
    issues = validator.validate(code)
    assert any("uvm_object_utils" in i or "uvm_component_utils" in i for i in issues)


def test_sv_validator_python_detection(validator: SVValidator):
    code = "def my_function():\n    self.value = 10\n    print('hello')"
    issues = validator.validate(code)
    assert any("Python" in i or "self" in i or "print" in i for i in issues)


def test_extract_classes(validator: SVValidator):
    code = "class alpha extends uvm_test;\nendclass\nclass beta;\nendclass"
    classes = validator.extract_classes(code)
    assert "alpha" in classes
    assert "beta" in classes


def test_prompt_templates():
    templates = PromptTemplates()
    system = templates.system_prompt()
    assert "UVM" in system
    assert "SystemVerilog" in system

    seq_prompt = templates.sequence_generation("read all registers")
    assert "read all registers" in seq_prompt


async def test_generator_produces_result(config: Config):
    gen = TestGenerator(config)
    result = await gen.generate("Write a basic read test")
    assert isinstance(result, GenerationResult)
    assert result.code  # Should have some code (from mock)
    assert result.tokens_used > 0
