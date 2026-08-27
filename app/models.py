from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    """Returns current UTC time — used as default for all created_at columns."""
    return datetime.now(timezone.utc)


class Prompt(Base):
    """Top-level entity. One prompt has many versions and many test cases."""
    __tablename__ = "prompts"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=utcnow)

    # cascade="all, delete-orphan" — deleting a Prompt removes all child rows automatically
    versions = relationship(
        "PromptVersion",
        back_populates="prompt",
        cascade="all, delete-orphan",
        order_by="PromptVersion.version_number",  # always sorted ascending
    )
    test_cases = relationship(
        "TestCase",
        back_populates="prompt",
        cascade="all, delete-orphan",
    )


class PromptVersion(Base):
    """
    Append-only — rows are never updated. Every save = new row.
    This IS the version history (no git binary involved).
    """
    __tablename__ = "prompt_versions"

    id             = Column(Integer, primary_key=True, index=True)
    prompt_id      = Column(Integer, ForeignKey("prompts.id"), nullable=False)
    version_number = Column(Integer, nullable=False)  # calculated in route: max(existing) + 1
    content        = Column(Text, nullable=False)
    commit_message = Column(Text, nullable=True)
    created_at     = Column(DateTime, default=utcnow)

    prompt = relationship("Prompt", back_populates="versions")
    runs   = relationship("TestRun", back_populates="prompt_version", cascade="all, delete-orphan")


class TestCase(Base):
    """
    Belongs to a Prompt, not a specific version.
    Same test cases are reused across all versions — enables fair comparison.
    """
    __tablename__ = "test_cases"

    id              = Column(Integer, primary_key=True, index=True)
    prompt_id       = Column(Integer, ForeignKey("prompts.id"), nullable=False)
    input_variables = Column(Text, nullable=True)   # stored as JSON string, parsed in route
    expected_output = Column(Text, nullable=True)   # reference only — no auto-grading in v1
    created_at      = Column(DateTime, default=utcnow)

    prompt = relationship("Prompt", back_populates="test_cases")
    runs   = relationship("TestRun", back_populates="test_case", cascade="all, delete-orphan")


class TestRun(Base):
    """One row per (prompt_version × test_case) execution. Records LLM output + status."""
    __tablename__ = "test_runs"

    id                = Column(Integer, primary_key=True, index=True)
    prompt_version_id = Column(Integer, ForeignKey("prompt_versions.id"), nullable=False)
    test_case_id      = Column(Integer, ForeignKey("test_cases.id"), nullable=False)
    actual_output     = Column(Text, nullable=True)
    status            = Column(Text, nullable=False, default="success")  # "success" | "error"
    created_at        = Column(DateTime, default=utcnow)

    prompt_version = relationship("PromptVersion", back_populates="runs")
    test_case      = relationship("TestCase", back_populates="runs")
