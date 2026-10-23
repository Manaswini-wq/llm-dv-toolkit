"""Configuration for LLM DV Toolkit."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LLMConfig:
    """LLM provider configuration."""
    provider: str = "openai"  # openai, anthropic
    model: str = "gpt-4"
    api_key: str = ""
    temperature: float = 0.2
    max_tokens: int = 4096
    timeout: float = 60.0


@dataclass
class Config:
    """Global configuration."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    project_root: Path = field(default_factory=lambda: Path.cwd())
    coverage_db_path: Path = field(default_factory=lambda: Path("coverage.db"))
    regression_dir: Path = field(default_factory=lambda: Path("regression_results"))
    log_level: str = "INFO"

    @staticmethod
    def from_env() -> Config:
        """Load configuration from environment variables."""
        llm_cfg = LLMConfig(
            provider=os.environ.get("LLM_PROVIDER", "openai"),
            model=os.environ.get("LLM_MODEL", "gpt-4"),
            api_key=os.environ.get("OPENAI_API_KEY", os.environ.get("ANTHROPIC_API_KEY", "")),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0.2")),
            max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "4096")),
        )
        return Config(
            llm=llm_cfg,
            project_root=Path(os.environ.get("DV_PROJECT_ROOT", ".")),
            coverage_db_path=Path(os.environ.get("COVERAGE_DB", "coverage.db")),
            regression_dir=Path(os.environ.get("REGRESSION_DIR", "regression_results")),
        )
