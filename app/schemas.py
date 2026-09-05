"""
app/schemas.py

Pydantic models for request validation and response serialisation.
These are NOT the database tables — they define the shape of data
coming IN (request bodies) and going OUT (JSON responses) via the API.

Naming convention:
  - *Create  → shape of POST request body
  - *Out     → shape of JSON response
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ── Prompt ────────────────────────────────────────────────────────

class PromptCreate(BaseModel):
    """POST /prompts — required: name, optional: description."""
    name: str
    description: Optional[str] = None


class PromptOut(BaseModel):
    """Single prompt in a response — no versions list (use PromptDetailOut for that)."""
    id: int
    name: str
    description: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}  # allows building from SQLAlchemy ORM objects


# ── Prompt Version ────────────────────────────────────────────────

class PromptVersionCreate(BaseModel):
    """POST /prompts/{id}/versions — the new prompt text + optional commit message."""
    content: str
    commit_message: Optional[str] = None


class PromptVersionOut(BaseModel):
    id: int
    prompt_id: int
    version_number: int
    content: str
    commit_message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Prompt Detail (prompt + all its versions) ─────────────────────

class PromptDetailOut(BaseModel):
    """GET /prompts/{id} — full prompt with its version history."""
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    versions: list[PromptVersionOut] = []

    model_config = {"from_attributes": True}


# ── Test Case ─────────────────────────────────────────────────────

class TestCaseCreate(BaseModel):
    """
    POST /prompts/{id}/test-cases
    input_variables: JSON string — e.g. '{"article": "...", "lang": "EN"}'
    """
    input_variables: Optional[str] = None
    expected_output: Optional[str] = None


class TestCaseOut(BaseModel):
    id: int
    prompt_id: int
    input_variables: Optional[str]
    expected_output: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Test Run ──────────────────────────────────────────────────────

class TestRunOut(BaseModel):
    """
    Response for a single test run result.
    test_case_id links back to the input used; actual_output is what the LLM returned.
    """
    id: int
    prompt_version_id: int
    test_case_id: int
    actual_output: Optional[str]
    status: str          # "success" | "error"
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Diff ──────────────────────────────────────────────────────────

class DiffOut(BaseModel):
    """
    GET /prompts/{id}/versions/{v1}/diff/{v2}
    Returns the two version numbers compared and the unified diff as a string.
    """
    version_a: int
    version_b: int
    diff: str            # unified diff output from difflib
