"""
app/routes/test_cases.py

Endpoints for test case management:
  POST /prompts/{prompt_id}/test-cases  — add a test case to a prompt
  GET  /prompts/{prompt_id}/test-cases  — list all test cases for a prompt
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Prompt, TestCase
from app.schemas import TestCaseCreate, TestCaseOut

router = APIRouter(prefix="/prompts", tags=["test-cases"])


@router.post("/{prompt_id}/test-cases", response_model=TestCaseOut, status_code=201)
def add_test_case(prompt_id: int, payload: TestCaseCreate, db: Session = Depends(get_db)):
    """
    Adds a test case to a prompt.
    Test cases are prompt-scoped (not version-scoped) so they can be reused
    when running different versions for fair comparison.
    """
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt {prompt_id} not found")

    test_case = TestCase(
        prompt_id=prompt_id,
        input_variables=payload.input_variables,   # stored as raw JSON string
        expected_output=payload.expected_output,
    )
    db.add(test_case)
    db.commit()
    db.refresh(test_case)
    return test_case


@router.get("/{prompt_id}/test-cases", response_model=list[TestCaseOut])
def list_test_cases(prompt_id: int, db: Session = Depends(get_db)):
    """Returns all test cases for a prompt, ordered by creation time."""
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt {prompt_id} not found")

    return (
        db.query(TestCase)
        .filter(TestCase.prompt_id == prompt_id)
        .order_by(TestCase.created_at)
        .all()
    )
