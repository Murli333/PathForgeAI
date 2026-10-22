
from pathlib import Path
import json
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

ROLE_SKILL_PATH = DATA_DIR / "req_skill_graph.csv"
SKILL_DEMAND_PATH = DATA_DIR / "skill_demand.csv"
AI_EXPOSURE_PATH = DATA_DIR / "ai_exposure_results.csv"


class AnalyzeRequest(BaseModel):
    target_role: str
    current_skills: list[str] = Field(default_factory=list)


class RoadmapRequest(BaseModel):
    target_role: str
    current_skills: list[str] = Field(default_factory=list)
    max_skills: int = 15

@router.post("/analyze")
def analyze_skills(request: AnalyzeRequest):
    if not ROLE_SKILL_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail="Role-skill dataset was not found.",
        )

    df = pd.read_csv(ROLE_SKILL_PATH)

    # Validate the dataset schema
    required_columns = {
        "role", "skill", "skill_demand_pct", "requirement_level"
    }
    if not required_columns.issubset(df.columns):
        raise HTTPException(
            status_code=500,
            detail="Role-skill dataset is missing required columns.",
        )

    # Match the requested target role
    role_mask = (
        df["role"].astype(str).str.strip().str.casefold()
        == request.target_role.strip().casefold()
    )
    role_df = df.loc[role_mask].copy()

    if role_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Target role not found: {request.target_role}",
        )

    # Normalize skill names
    role_df["skill"] = (
        role_df["skill"].astype(str).str.strip().str.casefold()
    )
    current_skills = {
        skill.strip().casefold()
        for skill in request.current_skills
        if skill.strip()
    }

    # Keep skills missing from the user's profile
    missing_df = role_df[
        ~role_df["skill"].isin(current_skills)
    ].copy()

    # Rank role requirements using demand and requirement level
    requirement_weights = {
        "Core": 1.00,
        "Common": 0.75,
        "Supporting": 0.50,
        "Rare": 0.25,
    }

    missing_df["requirement_weight"] = (
        missing_df["requirement_level"]
        .map(requirement_weights)
        .fillna(0.25)
    )

    missing_df["priority_score"] = (
        missing_df["skill_demand_pct"].fillna(0) / 100
    ) * missing_df["requirement_weight"]

    missing_df = missing_df.sort_values(
        "priority_score", ascending=False
    )

    missing_skills = [
        {
            "skill": row["skill"],
            "requirement_level": row["requirement_level"],
            "role_demand_pct": round(
                float(row["skill_demand_pct"]), 2
            ),
            "priority_score": round(
                float(row["priority_score"]), 4
            ),
        }
        for _, row in missing_df.iterrows()
    ]

    return {
        "target_role": role_df["role"].iloc[0],
        "current_skill_count": len(current_skills),
        "matched_skill_count": int(
            role_df["skill"].isin(current_skills).sum()
        ),
        "missing_skill_count": len(missing_skills),
        "missing_skills": missing_skills,
    }

    RESILIENCE_PATH = DATA_DIR / "role_skill_priorities.csv"
# Enrich missing skills with available resilience data
    if RESILIENCE_PATH.exists():
     resilience_df = pd.read_csv(RESILIENCE_PATH)

    if "skill" in resilience_df.columns:
        resilience_df["skill"] = (
            resilience_df["skill"]
            .astype(str)
            .str.strip()
            .str.casefold()
        )

        # Select only columns available in the saved file
        desired_columns = [
            "skill",
            "market_demand_score",
            "transferability_score",
            "task_based_score",
            "resilience_score",
            "exposure_status",
        ]

        available_columns = [
            col for col in desired_columns
            if col in resilience_df.columns
        ]

        resilience_df = resilience_df[available_columns].drop_duplicates(
            subset=["skill"]
        )

        missing_df = missing_df.merge(
            resilience_df,
            on="skill",
            how="left",
        )

        missing_skills = []

        for _, row in missing_df.iterrows():
         item = {
        "skill": row["skill"],
        "requirement_level": row["requirement_level"],
        "role_demand_pct": round(
            float(row["skill_demand_pct"]), 2
        ),
        "priority_score": round(
            float(row["priority_score"]), 4
        ),
    }

    for column in [
        "market_demand_score",
        "transferability_score",
        "task_based_score",
        "resilience_score",
        "exposure_status",
    ]:
        if column in row.index and pd.notna(row[column]):
            value = row[column]
            item[column] = (
                float(value)
                if isinstance(value, (int, float))
                else str(value)
            )

    missing_skills.append(item)



# roadmap endpoint
@router.post("/roadmap")
def generate_roadmap(request: RoadmapRequest):
    # Reuse the same role-skill dataset as /analyze
    if not ROLE_SKILL_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail="Role-skill dataset not found."
        )

    df = pd.read_csv(ROLE_SKILL_PATH)

    required_columns = {
        "role", "skill", "skill_demand_pct", "requirement_level"
    }

    if not required_columns.issubset(df.columns):
        raise HTTPException(
            status_code=500,
            detail="Invalid role-skill dataset."
        )

    role_df = df[
        df["role"].astype(str).str.strip().str.casefold()
        == request.target_role.strip().casefold()
    ].copy()

    if role_df.empty:
        raise HTTPException(
            status_code=404,
            detail="Target role not found."
        )

    role_df["skill"] = (
        role_df["skill"].astype(str).str.strip().str.casefold()
    )

    current_skills = {
        skill.strip().casefold()
        for skill in request.current_skills
        if skill.strip()
    }

    roadmap_df = role_df[
        ~role_df["skill"].isin(current_skills)
    ].copy()

    requirement_weights = {
        "Core": 1.00,
        "Common": 0.75,
        "Supporting": 0.50,
        "Rare": 0.25
    }

    roadmap_df["requirement_weight"] = (
        roadmap_df["requirement_level"]
        .map(requirement_weights)
        .fillna(0.25)
    )

    roadmap_df["priority_score"] = (
        roadmap_df["skill_demand_pct"].fillna(0) / 100
        * roadmap_df["requirement_weight"]
    )

    # Order by role importance and observed demand
    roadmap_df = roadmap_df.sort_values(
        ["requirement_weight", "priority_score"],
        ascending=False
    ).head(request.max_skills)

    roadmap = []

    for index, (_, row) in enumerate(roadmap_df.iterrows(), start=1):
        level = row["requirement_level"]

        if level == "Core":
            phase = "Phase 1 - Core Skills"
        elif level == "Common":
            phase = "Phase 2 - Important Skills"
        elif level == "Supporting":
            phase = "Phase 3 - Supporting Skills"
        else:
            phase = "Phase 4 - Optional Skills"

        roadmap.append({
            "step": index,
            "skill": row["skill"],
            "phase": phase,
            "requirement_level": level,
            "role_demand_pct": round(
                float(row["skill_demand_pct"]), 2
            ),
            "priority_score": round(
                float(row["priority_score"]), 4
            )
        })

    return {
        "target_role": role_df["role"].iloc[0],
        "roadmap_steps": len(roadmap),
        "roadmap": roadmap,
        "note": (
            "Phases reflect role importance, not verified prerequisites. "
            "Learning duration and resources are not yet personalized."
        )
    }