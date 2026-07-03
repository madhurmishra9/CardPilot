"""Devaluation tracking: diff a card's rules across its git history.

The YAML files live in git, so the version history IS the devaluation record —
no extra storage needed. Read-only `git log` / `git show` via subprocess.
"""

from __future__ import annotations

import subprocess

import yaml

from ..catalog import REPO_ROOT

WATCHED_FIELDS = ["point_value_inr", "annual_fee", "annual_fee_waiver_spend",
                  "redemption_fee_inr", "points_expiry_months"]


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True,
                            text=True, timeout=15)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git failed")
    return result.stdout


def _rates_map(rules: dict) -> dict[str, float]:
    return {r.get("category"): float(r.get("rate_points_per_100", 0))
            for r in (rules.get("earn_rules") or {}).get("rates") or []}


def _diff_versions(older: dict, newer: dict) -> list[str]:
    changes: list[str] = []
    for field in WATCHED_FIELDS:
        before, after = older.get(field), newer.get(field)
        if before != after:
            changes.append(f"{field}: {before} → {after}")
    old_rates, new_rates = _rates_map(older), _rates_map(newer)
    for cat in sorted(set(old_rates) | set(new_rates)):
        b, a = old_rates.get(cat), new_rates.get(cat)
        if b != a:
            changes.append(f"earn rate '{cat}': {b} → {a} pts/₹100")
    old_excl = set((older.get("earn_rules") or {}).get("excluded_categories") or [])
    new_excl = set((newer.get("earn_rules") or {}).get("excluded_categories") or [])
    for cat in sorted(new_excl - old_excl):
        changes.append(f"'{cat}' newly EXCLUDED from rewards")
    for cat in sorted(old_excl - new_excl):
        changes.append(f"'{cat}' no longer excluded")
    return changes


def card_history(card_id: str) -> list[dict]:
    """Chronology of rule changes for one card, newest first."""
    rel_path = f"data/cards/{card_id}.yaml"
    try:
        log = _git("log", "--follow", "--format=%H|%as|%s", "--", rel_path)
    except (RuntimeError, FileNotFoundError, subprocess.TimeoutExpired):
        return []

    commits = [line.split("|", 2) for line in log.splitlines() if line.strip()]
    versions = []
    for sha, day, message in commits:  # newest first
        try:
            rules = yaml.safe_load(_git("show", f"{sha}:{rel_path}"))
        except RuntimeError:
            continue
        versions.append({"sha": sha[:10], "date": day, "message": message,
                         "rules": rules})

    history = []
    for i, version in enumerate(versions):
        if i + 1 < len(versions):  # there is an older version to diff against
            changes = _diff_versions(versions[i + 1]["rules"], version["rules"])
        else:
            changes = ["initial version of this card's rules"]
        history.append({"sha": version["sha"], "date": version["date"],
                        "message": version["message"], "changes": changes})
    return history
