
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from routers.analysis import router as analysis_router

app = FastAPI(
    title="PathForge API",
    description="Career intelligence, skill-gap analysis, and career resilience.",
    version="0.1.0",
)
app.include_router(analysis_router)
# Resolve the data directory relative to this file:
# PathForge/backend/main.py -> PathForge/data/
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ROLE_SKILL_PATH = DATA_DIR / "req_skill_graph.csv"


@app.get("/")
def home():
    return {
        "project": "PathForge",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/roles")
def get_roles():
    if not ROLE_SKILL_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail="Role-skill dataset was not found.",
        )

    try:
        df = pd.read_csv(ROLE_SKILL_PATH)

        if "role" not in df.columns:
            raise HTTPException(
                status_code=500,
                detail="Dataset does not contain a role column.",
            )

        roles = sorted(
            df["role"].dropna().astype(str).str.strip().unique().tolist()
        )

        return {
            "count": len(roles),
            "roles": roles,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to load roles: {exc}",
        )


from pydantic import BaseModel,Field


class AnalyzeRequest(BaseModel):
    target_role: str = Field(min_length=1)
    current_skills: list[str] = Field(default_factory=list)






class RoadmapRequest(BaseModel):
    target_role: str = Field(min_length=1)
    current_skills: list[str] = Field(default_factory=list)
    max_skills: int = Field(default=15, ge=1, le=100)



