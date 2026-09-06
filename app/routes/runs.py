"""
app/routes/runs.py

Endpoints for running a prompt version against its test cases:
  POST /versions/{version_id}/run   — run this version against all test cases for its prompt
  GET  /versions/{version_id}/runs  — list all past run results for a version
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PromptVersion, TestCase, TestRun
from app.schemas import TestRunOut
from app.services.llm_service import call_llm

# Note: prefix is /versions here, not /prompts — matches the API contract in the kickstart doc
router = APIRouter(prefix="/versions", tags=["runs"])


@router.post("/{version_id}/run", response_model=list[TestRunOut], status_code=201)
def run_version(version_id: int, db: Session = Depends(get_db)):
    """
    Runs the given prompt version against every test case that belongs to its parent prompt.
    Creates one TestRun row per test case.
    Returns the list of all run results from this execution.
    """
    # Fetch the version — also loads version.prompt via relationship
    version = db.query(PromptVersion).filter(PromptVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail=f"Version {version_id} not found")

    # Get all test cases for the parent prompt
    test_cases = (
        db.query(TestCase)
        .filter(TestCase.prompt_id == version.prompt_id)
        .all()
    )

    if not test_cases:
        raise HTTPException(
            status_code=400,
            detail="No test cases found for this prompt. Add at least one before running.",
        )

    results = []

    for test_case in test_cases:
        # Build the final prompt text by substituting input_variables into the template.
        # e.g. content = "Classify: {ticket}" + input_variables = '{"ticket": "Help!"}'
        # → final_prompt = "Classify: Help!"
        final_prompt = _render_prompt(version.content, test_case.input_variables)

        try:
            output = call_llm(final_prompt)
            status = "success"
        except Exception as e:
            # Capture the error message as output so we can show it in the UI
            output = f"ERROR: {str(e)}"
            status = "error"

        run = TestRun(
            prompt_version_id=version_id,
            test_case_id=test_case.id,
            actual_output=output,
            status=status,
        )
        db.add(run)
        results.append(run)

    db.commit()

    # Refresh all run objects so their IDs and created_at are populated
    for run in results:
        db.refresh(run)

    return results


@router.get("/{version_id}/runs", response_model=list[TestRunOut])
def list_runs(version_id: int, db: Session = Depends(get_db)):
    """Returns all past test run results for a version, newest-first."""
    version = db.query(PromptVersion).filter(PromptVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail=f"Version {version_id} not found")

    return (
        db.query(TestRun)
        .filter(TestRun.prompt_version_id == version_id)
        .order_by(TestRun.created_at.desc())
        .all()
    )


# ── Helper ────────────────────────────────────────────────────────

def _render_prompt(content: str, input_variables_json: str | None) -> str:
    """
    Substitutes {variable} placeholders in the prompt content with values
    from the JSON string stored in test_case.input_variables.

    Example:
      content           = "Classify this ticket: {ticket_text}"
      input_variables   = '{"ticket_text": "My payment failed"}'
      result            = "Classify this ticket: My payment failed"

    If input_variables is empty/None, returns content unchanged.
    Uses str.format_map() which silently ignores missing keys (won't raise KeyError
    if the prompt has a {placeholder} that isn't in the test case variables).
    """
    if not input_variables_json:
        return content

    import json
    try:
        variables = json.loads(input_variables_json)
        return content.format_map(variables)
    except (json.JSONDecodeError, KeyError, ValueError):
        # If JSON is malformed or substitution fails, run the raw prompt as-is
        return content
