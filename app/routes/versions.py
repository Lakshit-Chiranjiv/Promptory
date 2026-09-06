"""
app/routes/versions.py

Endpoints for prompt version management:
  POST /prompts/{prompt_id}/versions              — save a new version
  GET  /prompts/{prompt_id}/versions              — list all versions for a prompt
  GET  /prompts/{prompt_id}/versions/{v1}/diff/{v2} — diff two versions
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Prompt, PromptVersion
from app.schemas import PromptVersionCreate, PromptVersionOut, DiffOut
from app.services.diff_service import compute_diff

router = APIRouter(prefix="/prompts", tags=["versions"])


@router.post("/{prompt_id}/versions", response_model=PromptVersionOut, status_code=201)
def save_version(prompt_id: int, payload: PromptVersionCreate, db: Session = Depends(get_db)):
    """
    Appends a new version row for the given prompt.
    version_number = max existing version for this prompt + 1, defaulting to 1.
    """
    # Guard: ensure the parent prompt exists
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt {prompt_id} not found")

    # Calculate next version number scoped to THIS prompt (not a global counter)
    max_version = db.query(func.max(PromptVersion.version_number)).filter(
        PromptVersion.prompt_id == prompt_id
    ).scalar()  # .scalar() returns a single value (or None) instead of a row

    next_version = (max_version or 0) + 1

    version = PromptVersion(
        prompt_id=prompt_id,
        version_number=next_version,
        content=payload.content,
        commit_message=payload.commit_message,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


@router.get("/{prompt_id}/versions", response_model=list[PromptVersionOut])
def list_versions(prompt_id: int, db: Session = Depends(get_db)):
    """Returns all versions for a prompt, ordered by version_number ascending."""
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt {prompt_id} not found")

    return (
        db.query(PromptVersion)
        .filter(PromptVersion.prompt_id == prompt_id)
        .order_by(PromptVersion.version_number)
        .all()
    )


@router.get("/{prompt_id}/versions/{v1}/diff/{v2}", response_model=DiffOut)
def diff_versions(prompt_id: int, v1: int, v2: int, db: Session = Depends(get_db)):
    """
    Returns a unified diff between version v1 and version v2 of a prompt.
    v1 and v2 are version_numbers (1, 2, 3...), not database IDs.
    """
    def get_version(version_number: int) -> PromptVersion:
        version = (
            db.query(PromptVersion)
            .filter(
                PromptVersion.prompt_id == prompt_id,
                PromptVersion.version_number == version_number,
            )
            .first()
        )
        if not version:
            raise HTTPException(
                status_code=404,
                detail=f"Version {version_number} not found for prompt {prompt_id}",
            )
        return version

    version_a = get_version(v1)
    version_b = get_version(v2)

    diff_text = compute_diff(
        text_a=version_a.content,
        text_b=version_b.content,
        label_a=f"v{v1}",
        label_b=f"v{v2}",
    )

    return DiffOut(version_a=v1, version_b=v2, diff=diff_text)
