"""
Utility helpers for the REST API.
"""

import csv
import io
import json
import os
from datetime import datetime
from typing import Any, Dict, List

import config
from utils.logger import logger


def _ensure_output_dirs() -> None:
    """Create output directories if they do not exist."""
    os.makedirs(config.OUTPUTS_DIR, exist_ok=True)
    os.makedirs(config.OUTPUTS_HISTORY_DIR, exist_ok=True)


def save_results_json(results: Dict[str, Any]) -> str:
    """Persist prediction results to the canonical JSON file and history.

    Args:
        results: Prediction results dictionary.

    Returns:
        Path of the written canonical file.
    """
    _ensure_output_dirs()

    canonical = os.path.join(config.OUTPUTS_DIR, "results.json")
    with open(canonical, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    history_path = os.path.join(config.OUTPUTS_HISTORY_DIR, f"{ts}.json")
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    _rotate_history()
    logger.info("Saved prediction results to %s", canonical)
    return canonical


def save_results_csv(results: Dict[str, Any]) -> str:
    """Persist prediction results to the canonical CSV file and history.

    Args:
        results: Prediction results dictionary.

    Returns:
        Path of the written canonical file.
    """
    _ensure_output_dirs()

    canonical = os.path.join(config.OUTPUTS_DIR, "results.csv")
    rows = _results_to_rows(results)
    with open(canonical, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "model", "prediction", "confidence"])
        writer.writeheader()
        writer.writerows(rows)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    history_path = os.path.join(config.OUTPUTS_HISTORY_DIR, f"{ts}.csv")
    with open(history_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "model", "prediction", "confidence"])
        writer.writeheader()
        writer.writerows(rows)

    _rotate_history()
    logger.info("Saved prediction results (CSV) to %s", canonical)
    return canonical


def results_to_csv_string(results: Dict[str, Any]) -> str:
    """Convert prediction results dict to a CSV string.

    Args:
        results: Prediction results dictionary.

    Returns:
        CSV content as a string.
    """
    rows = _results_to_rows(results)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["timestamp", "model", "prediction", "confidence"])
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _results_to_rows(results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten prediction results into a list of CSV-ready dicts."""
    ts = results.get("timestamp", datetime.now().isoformat())
    rows: List[Dict[str, Any]] = []
    for model_name, data in results.get("predictions", {}).items():
        rows.append({
            "timestamp": ts,
            "model": model_name,
            "prediction": "|".join(str(p) for p in data.get("prediction", [])),
            "confidence": round(data.get("confidence", 0.0), 4),
        })
    return rows


def load_latest_results() -> Dict[str, Any]:
    """Load the most recently saved prediction results from disk.

    Returns:
        Prediction results dictionary, or an empty structure if none saved.
    """
    canonical = os.path.join(config.OUTPUTS_DIR, "results.json")
    if not os.path.exists(canonical):
        return {}
    try:
        with open(canonical, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load results from %s: %s", canonical, exc)
        return {}


def load_history(limit: int = 100) -> List[Dict[str, Any]]:
    """Return the last *limit* saved prediction history entries.

    Args:
        limit: Maximum number of history entries to return.

    Returns:
        List of prediction result dictionaries, newest first.
    """
    _ensure_output_dirs()
    history: List[Dict[str, Any]] = []
    files = sorted(
        [f for f in os.listdir(config.OUTPUTS_HISTORY_DIR) if f.endswith(".json")],
        reverse=True,
    )
    for fname in files[:limit]:
        path = os.path.join(config.OUTPUTS_HISTORY_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                history.append(json.load(f))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Skipping history file %s: %s", fname, exc)
    return history


def _rotate_history() -> None:
    """Delete oldest history files when the count exceeds the configured limit."""
    _ensure_output_dirs()
    files = sorted(
        [f for f in os.listdir(config.OUTPUTS_HISTORY_DIR) if f.endswith((".json", ".csv"))]
    )
    # Keep only the most recent OUTPUTS_MAX_HISTORY unique timestamps
    timestamps = sorted({f.rsplit(".", 1)[0] for f in files}, reverse=True)
    for old_ts in timestamps[config.OUTPUTS_MAX_HISTORY:]:
        for ext in (".json", ".csv"):
            old_file = os.path.join(config.OUTPUTS_HISTORY_DIR, old_ts + ext)
            if os.path.exists(old_file):
                os.remove(old_file)
                logger.debug("Rotated history file: %s", old_file)
