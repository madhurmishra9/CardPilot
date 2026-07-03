"""Loads the versioned card-rules dataset from /data/cards/*.yaml.

The YAML files are the source of truth for every reward rate, fee and perk.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CARDS_DIR = REPO_ROOT / "data" / "cards"
CATEGORIES_FILE = REPO_ROOT / "data" / "categories.yaml"


def load_card_rules(cards_dir: Path | None = None) -> dict[str, dict]:
    """card_id -> full rules dict, for every YAML file in the catalog."""
    out: dict[str, dict] = {}
    for path in sorted((cards_dir or CARDS_DIR).glob("*.yaml")):
        rules = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not rules or "card_id" not in rules:
            raise ValueError(f"{path.name}: missing card_id")
        out[rules["card_id"]] = rules
    return out


def load_categories(path: Path | None = None) -> list[dict]:
    data = yaml.safe_load((path or CATEGORIES_FILE).read_text(encoding="utf-8"))
    return data.get("categories", [])
