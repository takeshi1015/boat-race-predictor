"""
CSV Importer
Bulk import of boat race data from CSV files.
"""

import csv
import io
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

from utils.logger import setup_logger

logger = setup_logger(__name__)

# Expected column sets for each data type
_RACE_REQUIRED_COLUMNS = {"race_id", "race_number", "race_date", "location", "location_code"}
_BOAT_REQUIRED_COLUMNS = {"boat_id", "boat_number"}
_RIDER_REQUIRED_COLUMNS = {"rider_id", "name", "registration_number"}
_RESULT_REQUIRED_COLUMNS = {"result_id", "race_id", "race_date", "location", "race_number"}


class CSVImporter:
    """Importer for bulk-loading boat race data from CSV files.

    This class reads CSV files (or CSV strings/streams) and returns
    lists of dictionaries ready for conversion into data model instances.

    Attributes:
        encoding: File encoding used when opening CSV files.
        delimiter: Field delimiter character.
    """

    def __init__(self, encoding: str = "utf-8", delimiter: str = ",") -> None:
        """Initialise the CSV importer.

        Args:
            encoding: File encoding (default 'utf-8').
            delimiter: Column delimiter (default ',').
        """
        self.encoding = encoding
        self.delimiter = delimiter

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def import_races(
        self, source: Union[str, Path, io.TextIOBase]
    ) -> List[Dict[str, Any]]:
        """Import race data from a CSV source.

        Args:
            source: File path (str or Path) or an already-opened text stream.

        Returns:
            List of race data dictionaries.

        Raises:
            ValueError: If required columns are missing.
        """
        rows = list(self._read(source))
        if not rows:
            return []
        self._validate_columns(set(rows[0].keys()), _RACE_REQUIRED_COLUMNS, "race")
        return [self._coerce_race(row) for row in rows]

    def import_boats(
        self, source: Union[str, Path, io.TextIOBase]
    ) -> List[Dict[str, Any]]:
        """Import boat data from a CSV source.

        Args:
            source: File path (str or Path) or an already-opened text stream.

        Returns:
            List of boat data dictionaries.

        Raises:
            ValueError: If required columns are missing.
        """
        rows = list(self._read(source))
        if not rows:
            return []
        self._validate_columns(set(rows[0].keys()), _BOAT_REQUIRED_COLUMNS, "boat")
        return [self._coerce_boat(row) for row in rows]

    def import_riders(
        self, source: Union[str, Path, io.TextIOBase]
    ) -> List[Dict[str, Any]]:
        """Import rider data from a CSV source.

        Args:
            source: File path (str or Path) or an already-opened text stream.

        Returns:
            List of rider data dictionaries.

        Raises:
            ValueError: If required columns are missing.
        """
        rows = list(self._read(source))
        if not rows:
            return []
        self._validate_columns(set(rows[0].keys()), _RIDER_REQUIRED_COLUMNS, "rider")
        return [self._coerce_rider(row) for row in rows]

    def import_results(
        self, source: Union[str, Path, io.TextIOBase]
    ) -> List[Dict[str, Any]]:
        """Import result data from a CSV source.

        Args:
            source: File path (str or Path) or an already-opened text stream.

        Returns:
            List of result data dictionaries.

        Raises:
            ValueError: If required columns are missing.
        """
        rows = list(self._read(source))
        if not rows:
            return []
        self._validate_columns(set(rows[0].keys()), _RESULT_REQUIRED_COLUMNS, "result")
        return [self._coerce_result(row) for row in rows]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _read(
        self, source: Union[str, Path, io.TextIOBase]
    ) -> Iterator[Dict[str, str]]:
        """Yield rows from a CSV source as dictionaries.

        Args:
            source: File path or text stream.

        Yields:
            Row dictionaries with string values.
        """
        if isinstance(source, (str, Path)):
            path = Path(source)
            try:
                with path.open(encoding=self.encoding, newline="") as fh:
                    reader = csv.DictReader(fh, delimiter=self.delimiter)
                    yield from reader
            except OSError as exc:
                logger.error("Failed to open CSV file %s: %s", path, exc)
        else:
            reader = csv.DictReader(source, delimiter=self.delimiter)
            yield from reader

    @staticmethod
    def _validate_columns(
        present: set, required: set, data_type: str
    ) -> None:
        """Raise ValueError if any required columns are absent.

        Args:
            present: Set of column names found in the CSV.
            required: Set of required column names.
            data_type: Human-readable name used in the error message.

        Raises:
            ValueError: If one or more required columns are missing.
        """
        missing = required - present
        if missing:
            raise ValueError(
                f"CSV is missing required {data_type} columns: {sorted(missing)}"
            )

    @staticmethod
    def _safe_float(value: str, default: float = 0.0) -> float:
        """Convert a string to float, returning default on failure."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_int(value: str, default: int = 0) -> int:
        """Convert a string to int, returning default on failure."""
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_bool(value: str) -> bool:
        """Convert a string to bool."""
        return str(value).strip().lower() in ("1", "true", "yes", "y")

    def _coerce_race(self, row: Dict[str, str]) -> Dict[str, Any]:
        """Coerce a raw CSV row into typed race data.

        Args:
            row: Raw string dictionary from the CSV reader.

        Returns:
            Typed dictionary compatible with RaceData.from_dict.
        """
        return {
            "race_id": row["race_id"].strip(),
            "race_number": self._safe_int(row["race_number"]),
            "race_date": row["race_date"].strip(),
            "location": row["location"].strip(),
            "location_code": row["location_code"].strip(),
            "grade": row.get("grade", "general").strip(),
            "race_class": row.get("race_class", "").strip(),
            "distance": self._safe_int(row.get("distance", "1800"), 1800),
            "course_type": row.get("course_type", "straight").strip(),
            "weather": row.get("weather", "sunny").strip(),
            "wind_direction": row.get("wind_direction", "").strip(),
            "wind_speed": self._safe_float(row.get("wind_speed", "0")),
            "wave_height": self._safe_float(row.get("wave_height", "0")),
            "water_temperature": self._safe_float(row.get("water_temperature", "20")),
            "air_temperature": self._safe_float(row.get("air_temperature", "20")),
            "is_night_race": self._safe_bool(row.get("is_night_race", "false")),
        }

    def _coerce_boat(self, row: Dict[str, str]) -> Dict[str, Any]:
        """Coerce a raw CSV row into typed boat data.

        Args:
            row: Raw string dictionary from the CSV reader.

        Returns:
            Typed dictionary compatible with BoatData.from_dict.
        """
        return {
            "boat_id": row["boat_id"].strip(),
            "boat_number": self._safe_int(row["boat_number"]),
            "age": self._safe_float(row.get("age", "0")),
            "manufacturer": row.get("manufacturer", "").strip(),
            "engine_id": row.get("engine_id", "").strip(),
            "engine_rate": self._safe_float(row.get("engine_rate", "0")),
            "exhibition_time": self._safe_float(row.get("exhibition_time", "0")),
            "start_timing": self._safe_float(row.get("start_timing", "0")),
            "win_rate": self._safe_float(row.get("win_rate", "0")),
            "place_rate": self._safe_float(row.get("place_rate", "0")),
            "recent_maintenance": row.get("recent_maintenance", "").strip(),
        }

    def _coerce_rider(self, row: Dict[str, str]) -> Dict[str, Any]:
        """Coerce a raw CSV row into typed rider data.

        Args:
            row: Raw string dictionary from the CSV reader.

        Returns:
            Typed dictionary compatible with RiderData.from_dict.
        """
        return {
            "rider_id": row["rider_id"].strip(),
            "name": row["name"].strip(),
            "registration_number": row["registration_number"].strip(),
            "branch": row.get("branch", "").strip(),
            "birth_date": row.get("birth_date", "").strip() or None,
            "gender": row.get("gender", "male").strip(),
            "rank": row.get("rank", "B1").strip(),
            "weight": self._safe_float(row.get("weight", "52")),
            "win_rate": self._safe_float(row.get("win_rate", "0")),
            "place_rate": self._safe_float(row.get("place_rate", "0")),
            "payoff_rate": self._safe_float(row.get("payoff_rate", "0")),
            "avg_start_timing": self._safe_float(row.get("avg_start_timing", "0")),
            "flying_count": self._safe_int(row.get("flying_count", "0")),
            "late_start_count": self._safe_int(row.get("late_start_count", "0")),
            "annual_wins": self._safe_int(row.get("annual_wins", "0")),
            "total_races": self._safe_int(row.get("total_races", "0")),
            "total_wins": self._safe_int(row.get("total_wins", "0")),
        }

    def _coerce_result(self, row: Dict[str, str]) -> Dict[str, Any]:
        """Coerce a raw CSV row into typed result data.

        Args:
            row: Raw string dictionary from the CSV reader.

        Returns:
            Typed dictionary compatible with ResultData.from_dict.
        """
        return {
            "result_id": row["result_id"].strip(),
            "race_id": row["race_id"].strip(),
            "race_date": row["race_date"].strip(),
            "location": row["location"].strip(),
            "race_number": self._safe_int(row["race_number"]),
            "trifecta_payout": self._safe_float(row.get("trifecta_payout", "0")),
            "quinella_payout": self._safe_float(row.get("quinella_payout", "0")),
            "win_payout": self._safe_float(row.get("win_payout", "0")),
            "exacta_payout": self._safe_float(row.get("exacta_payout", "0")),
            "bracket_quinella_payout": self._safe_float(
                row.get("bracket_quinella_payout", "0")
            ),
            "cancelled": self._safe_bool(row.get("cancelled", "false")),
            "cancel_reason": row.get("cancel_reason", "").strip(),
        }
