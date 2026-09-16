"""
app/routes/yaml_io.py

YAML export / import endpoints (Step 21).

Export — serialises one prompt (all versions + test cases) to a YAML file the
browser/client can download and store as a plain text snapshot.

Import — accepts that same YAML file, creates a brand-new prompt row, and
re-creates all versions and test cases exactly as they were.  The prompt gets a
fresh ID; existing data is never touched.

URL scheme:
  GET  /prompts/{prompt_id}/export   → download prompt.yaml
  POST /prompts/import               → upload prompt.yaml → 201 Created

YAML structure produced / consumed
───────────────────────────────────
promptory_version: "1.0"
prompt:
  name: "Book Finder Prompt"
  description: "..."          # omitted when null
  versions:
    - version_number: 1
      content: |
        You are a book recommendation …
      commit_message: "initial"   # omitted when null
  test_cases:
    - input_variables: '{"genre": "literary fiction", "origin": "Japan"}'
      expected_output: null       # omitted when null
"""

import io
from typing import Optional

import yaml
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Prompt, PromptVersion, TestCase

router = APIRouter(tags=["yaml-io"])


# ── YAML schema helpers ───────────────────────────────────────────────────────

PROMPTORY_VERSION = "1.0"


def _prompt_to_dict(prompt: Prompt) -> dict:
    """Converts a fully-loaded Prompt ORM object to a plain Python dict."""
    versions = sorted(prompt.versions, key=lambda v: v.version_number)
    test_cases = sorted(prompt.test_cases, key=lambda tc: tc.id)

    doc: dict = {
        "promptory_version": PROMPTORY_VERSION,
        "prompt": {
            "name": prompt.name,
        },
    }
    if prompt.description:
        doc["prompt"]["description"] = prompt.description

    doc["prompt"]["versions"] = [
        {k: v for k, v in {
            "version_number": ver.version_number,
            "content": ver.content,
            "commit_message": ver.commit_message,
        }.items() if v is not None}
        for ver in versions
    ]

    doc["prompt"]["test_cases"] = [
        {k: v for k, v in {
            "input_variables": tc.input_variables,
            "expected_output": tc.expected_output,
        }.items() if v is not None}
        for tc in test_cases
    ]

    return doc


def _validate_yaml_doc(doc: dict) -> None:
    """
    Raises ValueError with a human-readable message if the YAML document is
    missing required fields.  Called before any DB writes.
    """
    if not isinstance(doc, dict):
        raise ValueError("Top-level YAML must be a mapping.")

    prompt_node = doc.get("prompt")
    if not isinstance(prompt_node, dict):
        raise ValueError("Missing required top-level key: 'prompt'.")

    if not prompt_node.get("name"):
        raise ValueError("prompt.name is required and must be a non-empty string.")

    versions = prompt_node.get("versions")
    if not isinstance(versions, list) or len(versions) == 0:
        raise ValueError("prompt.versions must be a non-empty list.")

    for i, ver in enumerate(versions):
        if not isinstance(ver, dict):
            raise ValueError(f"versions[{i}] must be a mapping.")
        if not ver.get("content"):
            raise ValueError(f"versions[{i}].content is required.")


# ── Export endpoint ───────────────────────────────────────────────────────────

@router.get(
    "/prompts/{prompt_id}/export",
    summary="Export prompt to YAML",
    response_description="A YAML file download containing the full prompt snapshot.",
)
def export_prompt(prompt_id: int, db: Session = Depends(get_db)):
    """
    Serialises the prompt (all versions + test cases) as a YAML file and
    streams it to the client with a `Content-Disposition: attachment` header so
    the browser saves it as a file download.

    The file is safe to open in any text editor or commit to source control.
    Re-import it later with `POST /prompts/import`.
    """
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt {prompt_id} not found")

    doc = _prompt_to_dict(prompt)

    # Render to YAML string.  allow_unicode keeps non-ASCII chars readable.
    yaml_str = yaml.dump(
        doc,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )

    # Build a safe filename: lowercase, replace spaces with underscores.
    safe_name = prompt.name.lower().replace(" ", "_")[:60]
    filename = f"{safe_name}_prompt.yaml"

    return StreamingResponse(
        content=io.BytesIO(yaml_str.encode("utf-8")),
        media_type="application/x-yaml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Import endpoint ───────────────────────────────────────────────────────────

class ImportResult(BaseModel):
    """Response body returned after a successful import."""
    prompt_id: int
    name: str
    versions_imported: int
    test_cases_imported: int
    message: str


@router.post(
    "/prompts/import",
    response_model=ImportResult,
    status_code=201,
    summary="Import prompt from YAML",
    response_description="Summary of what was created.",
)
async def import_prompt(
    file: UploadFile = File(..., description="A .yaml file previously exported from Promptory"),
    db: Session = Depends(get_db),
):
    """
    Imports a YAML snapshot produced by `GET /prompts/{id}/export`.

    A brand-new prompt is created with a fresh database ID — existing prompts
    are never modified.  All versions (preserving version_number) and test cases
    from the file are recreated.

    **Accepts:** `multipart/form-data` with a single field named `file`.

    **Error cases:**
    - 400 if the uploaded file cannot be parsed as valid YAML.
    - 422 if required fields (prompt.name, versions[].content) are missing.
    """
    # --- Read & parse --------------------------------------------------------
    raw_bytes = await file.read()
    try:
        doc = yaml.safe_load(raw_bytes.decode("utf-8"))
    except yaml.YAMLError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid YAML: {exc}",
        )

    # --- Validate structure --------------------------------------------------
    try:
        _validate_yaml_doc(doc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    prompt_node: dict = doc["prompt"]

    # --- Write to DB (all-or-nothing via session rollback on exception) -------
    try:
        # 1. Create the prompt
        new_prompt = Prompt(
            name=prompt_node["name"],
            description=prompt_node.get("description"),
        )
        db.add(new_prompt)
        db.flush()  # get new_prompt.id without committing yet

        # 2. Create versions (honour original version_number ordering)
        version_rows = sorted(
            prompt_node.get("versions", []),
            key=lambda v: v.get("version_number", 0),
        )
        for ver in version_rows:
            db.add(PromptVersion(
                prompt_id=new_prompt.id,
                version_number=ver.get("version_number") or (
                    # fallback: recalculate if version_number is absent in file
                    (db.query(func.max(PromptVersion.version_number))
                     .filter(PromptVersion.prompt_id == new_prompt.id)
                     .scalar() or 0) + 1
                ),
                content=ver["content"],
                commit_message=ver.get("commit_message"),
            ))

        # 3. Create test cases
        test_case_rows = prompt_node.get("test_cases", [])
        for tc in test_case_rows:
            db.add(TestCase(
                prompt_id=new_prompt.id,
                input_variables=tc.get("input_variables"),
                expected_output=tc.get("expected_output"),
            ))

        db.commit()
        db.refresh(new_prompt)

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database error during import: {exc}",
        )

    return ImportResult(
        prompt_id=new_prompt.id,
        name=new_prompt.name,
        versions_imported=len(version_rows),
        test_cases_imported=len(test_case_rows),
        message=(
            f"Imported '{new_prompt.name}' as prompt #{new_prompt.id} "
            f"({len(version_rows)} version(s), {len(test_case_rows)} test case(s))."
        ),
    )
