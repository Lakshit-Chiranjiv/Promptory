"""
app/routes/ui.py

Browser-facing routes — renders HTML pages via Jinja2 templates.
DB operations happen directly here; these routes do NOT call the JSON API routes.

URL scheme (chosen to avoid conflicts with /prompts and /versions API routes):
  GET  /             → index (all prompts)
  POST /             → create prompt → redirect to /p/{id}
  GET  /p/{id}       → prompt detail page
  POST /p/{id}/v     → save new version → redirect to /p/{id}
  POST /p/{id}/tc    → add test case   → redirect to /p/{id}
  GET  /p/{id}/diff  → diff view (?v1=N&v2=M query params)
  POST /v/{id}/run   → run version; returns HTML fragment (HTMX)
  GET  /v/{id}/runs  → full run history page
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Prompt, PromptVersion, TestCase, TestRun
from app.services.diff_service import compute_diff
from app.services.llm_service import call_llm

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# ── Index ──────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    prompts = db.query(Prompt).order_by(Prompt.created_at.desc()).all()
    return templates.TemplateResponse(request, "index.html", {"prompts": prompts})


@router.post("/")
def create_prompt_ui(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Form POST handler — creates the prompt and redirects to its detail page.
    status_code=303 (See Other) tells the browser to GET the redirect URL,
    preventing form re-submission on page refresh.
    """
    prompt = Prompt(name=name, description=description or None)
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return RedirectResponse(url=f"/p/{prompt.id}", status_code=303)


# ── Prompt detail ──────────────────────────────────────────────────

@router.get("/p/{prompt_id}", response_class=HTMLResponse)
def prompt_detail(request: Request, prompt_id: int, db: Session = Depends(get_db)):
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        return HTMLResponse("<h2>Prompt not found</h2>", status_code=404)
    test_cases = (
        db.query(TestCase)
        .filter(TestCase.prompt_id == prompt_id)
        .order_by(TestCase.id.asc())
        .all()
    )
    return templates.TemplateResponse(request, "prompt_detail.html", {
        "prompt": prompt,
        "test_cases": test_cases,
    })


@router.post("/p/{prompt_id}/v")
def add_version_ui(
    prompt_id: int,
    content: str = Form(...),
    commit_message: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    max_ver = db.query(func.max(PromptVersion.version_number)).filter(
        PromptVersion.prompt_id == prompt_id
    ).scalar()
    version = PromptVersion(
        prompt_id=prompt_id,
        version_number=(max_ver or 0) + 1,
        content=content,
        commit_message=commit_message or None,
    )
    db.add(version)
    db.commit()
    return RedirectResponse(url=f"/p/{prompt_id}", status_code=303)


@router.post("/p/{prompt_id}/tc")
def add_test_case_ui(
    prompt_id: int,
    input_variables: Optional[str] = Form(None),
    expected_output: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    tc = TestCase(
        prompt_id=prompt_id,
        input_variables=input_variables or None,
        expected_output=expected_output or None,
    )
    db.add(tc)
    db.commit()
    return RedirectResponse(url=f"/p/{prompt_id}", status_code=303)


# ── Diff view ──────────────────────────────────────────────────────

@router.get("/p/{prompt_id}/diff", response_class=HTMLResponse)
def diff_view(request: Request, prompt_id: int, v1: int, v2: int, db: Session = Depends(get_db)):
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        return HTMLResponse("<h2>Prompt not found</h2>", status_code=404)

    def get_ver(vnum: int):
        return db.query(PromptVersion).filter(
            PromptVersion.prompt_id == prompt_id,
            PromptVersion.version_number == vnum,
        ).first()

    version_a, version_b = get_ver(v1), get_ver(v2)
    if not version_a or not version_b:
        return HTMLResponse("<h2>Version not found</h2>", status_code=404)

    diff = compute_diff(version_a.content, version_b.content, label_a=f"v{v1}", label_b=f"v{v2}")
    return templates.TemplateResponse(request, "diff_view.html", {
        "prompt": prompt,
        "v1": v1, "v2": v2,
        "version_a": version_a, "version_b": version_b,
        "diff": diff,
    })


# ── Run (HTMX) ─────────────────────────────────────────────────────

@router.post("/v/{version_id}/run", response_class=HTMLResponse)
def run_version_ui(request: Request, version_id: int, db: Session = Depends(get_db)):
    """
    Called by the HTMX Run button — returns an HTML fragment (not a full page).
    The fragment is injected inline into #run-results-{version_id} on the detail page.
    """
    version = db.query(PromptVersion).filter(PromptVersion.id == version_id).first()
    if not version:
        return HTMLResponse("<p style='color:#f43f5e'>Version not found.</p>", status_code=404)

    test_cases = (
        db.query(TestCase)
        .filter(TestCase.prompt_id == version.prompt_id)
        .order_by(TestCase.id.asc())
        .all()
    )
    tc_index = {tc.id: i + 1 for i, tc in enumerate(test_cases)}

    runs_with_tc = []
    for tc in test_cases:
        final_prompt = _render_prompt(version.content, tc.input_variables)
        try:
            output = call_llm(final_prompt)
            status = "success"
        except Exception as e:
            output = f"ERROR: {e}"
            status = "error"

        run = TestRun(
            prompt_version_id=version_id,
            test_case_id=tc.id,
            actual_output=output,
            status=status,
        )
        db.add(run)
        runs_with_tc.append((tc, run))

    db.commit()
    for _, run in runs_with_tc:
        db.refresh(run)

    return templates.TemplateResponse(request, "partials/run_result_rows.html", {
        "runs_with_tc": runs_with_tc,
        "version_id": version_id,
        "tc_index": tc_index,
    })


# ── Run history (full page) ────────────────────────────────────────

@router.get("/v/{version_id}/runs", response_class=HTMLResponse)
def run_history(request: Request, version_id: int, db: Session = Depends(get_db)):
    version = db.query(PromptVersion).filter(PromptVersion.id == version_id).first()
    if not version:
        return HTMLResponse("<h2>Version not found</h2>", status_code=404)

    runs = (
        db.query(TestRun)
        .filter(TestRun.prompt_version_id == version_id)
        .order_by(TestRun.created_at.desc())
        .all()
    )

    # Build relative index: global test_case_id → position within this prompt (1-based)
    ordered_tcs = (
        db.query(TestCase)
        .filter(TestCase.prompt_id == version.prompt_id)
        .order_by(TestCase.id)
        .all()
    )
    tc_index = {tc.id: i + 1 for i, tc in enumerate(ordered_tcs)}

    return templates.TemplateResponse(request, "run_results.html", {
        "version": version, "runs": runs, "tc_index": tc_index,
    })


# ── Helper ─────────────────────────────────────────────────────────

def _render_prompt(content: str, input_variables_json: str | None) -> str:
    """Substitutes {placeholder} variables in the prompt content from the JSON string."""
    if not input_variables_json:
        return content
    try:
        return content.format_map(json.loads(input_variables_json))
    except (json.JSONDecodeError, KeyError, ValueError):
        return content  # fall back to unsubstituted content
