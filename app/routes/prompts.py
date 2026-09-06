"""
app/routes/prompts.py

Handles the three core prompt endpoints:
  GET  /prompts          — list all prompts
  POST /prompts          — create a new prompt
  GET  /prompts/{id}     — get one prompt with its full version history
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Prompt
from app.schemas import PromptCreate, PromptOut, PromptDetailOut

# APIRouter is a mini-app — groups related routes together.
# prefix="/prompts" means every route here automatically starts with /prompts.
# tags=["prompts"] groups them in the auto-generated Swagger docs at /docs.
router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.get("/", response_model=list[PromptOut])
def list_prompts(db: Session = Depends(get_db)):
    """
    Returns all prompts, ordered newest-first.
    `Depends(get_db)` tells FastAPI to call get_db() and inject the session automatically.
    """
    return db.query(Prompt).order_by(Prompt.created_at.desc()).all()


@router.post("/", response_model=PromptOut, status_code=201)
def create_prompt(payload: PromptCreate, db: Session = Depends(get_db)):
    """
    Creates a new prompt row.
    `payload` is auto-validated by Pydantic against PromptCreate before this runs.
    status_code=201 — HTTP convention for "resource created".
    """
    prompt = Prompt(
        name=payload.name,
        description=payload.description,
    )
    db.add(prompt)     # stage the new row
    db.commit()        # write to disk
    db.refresh(prompt) # reload from DB so `prompt.id` and `prompt.created_at` are populated
    return prompt


@router.get("/{prompt_id}", response_model=PromptDetailOut)
def get_prompt(prompt_id: int, db: Session = Depends(get_db)):
    """
    Returns a single prompt with its full version history (via the `versions` relationship).
    Raises 404 if the prompt_id doesn't exist.
    """
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt {prompt_id} not found")
    return prompt
