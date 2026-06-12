"""Load a Case from a Hydra/OmegaConf YAML file."""

from __future__ import annotations

from pathlib import Path
from typing import Union

from .schemas import Case, ChecklistItem


def case_from_dict(data: dict) -> Case:
    """Build a Case from a plain dict (e.g. an OmegaConf-resolved config)."""
    checklist = tuple(
        ChecklistItem(
            item_id=item["item_id"],
            text=item["text"],
            weight=float(item.get("weight", 1.0)),
        )
        for item in data["history_checklist"]
    )
    return Case(
        case_id=data["case_id"],
        title=data["title"],
        language=data["language"],
        persona=data["persona"],
        history_checklist=checklist,
        difficulty=data.get("difficulty", "moderate"),
    )


def load_case(path: Union[str, Path]) -> Case:
    """Load a Case from a YAML file via OmegaConf."""
    from omegaconf import OmegaConf  # noqa: PLC0415

    cfg = OmegaConf.load(str(path))
    return case_from_dict(OmegaConf.to_container(cfg, resolve=True))  # type: ignore[arg-type]
