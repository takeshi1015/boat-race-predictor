"""
Feature Engineer
Extracts and engineers features from raw boat race data for ML models.
"""

from typing import Any, Dict, List, Optional

import numpy as np

from utils.logger import setup_logger

logger = setup_logger(__name__)

# Feature index constants for the flat feature vector produced by
# extract_entry_features().  These are exposed so that downstream code can
# reference specific positions without relying on magic numbers.
FEATURE_WIN_RATE = 0
FEATURE_PLACE_RATE = 1
FEATURE_PAYOFF_RATE = 2
FEATURE_AVG_START_TIMING = 3
FEATURE_RECENT_WIN_RATE = 4
FEATURE_IS_TOP_RIDER = 5
FEATURE_FLYING_COUNT = 6
FEATURE_ENGINE_RATE = 7
FEATURE_BOAT_WIN_RATE = 8
FEATURE_BOAT_PLACE_RATE = 9
FEATURE_EXHIBITION_TIME = 10
FEATURE_BOAT_START_TIMING = 11
FEATURE_WIND_SPEED = 12
FEATURE_WAVE_HEIGHT = 13
FEATURE_AIR_TEMP = 14
FEATURE_WATER_TEMP = 15
FEATURE_FRAME_NUMBER = 16

FEATURE_DIM = 17  # Total number of features per entry


class FeatureEngineer:
    """Extracts and engineers features from race/rider/boat data.

    This class converts raw race data dictionaries into numerical feature
    matrices suitable for machine learning models.  The public interface
    closely mirrors the structure expected by the predictor classes.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_feature_matrix(
        self, race_data: Dict[str, Any]
    ) -> Optional[np.ndarray]:
        """Build a feature matrix from a full race data dictionary.

        Each row in the returned matrix corresponds to one race entry
        (participant).  The column layout is documented by the FEATURE_*
        constants at the top of this module.

        Args:
            race_data: Dictionary containing race, condition, and entry data.
                Must include an 'entries' key with a list of entry dicts.

        Returns:
            NumPy array of shape (n_entries, FEATURE_DIM), or None if the
            entries list is empty or extraction fails.
        """
        entries: List[Dict[str, Any]] = race_data.get("entries", [])
        if not entries:
            logger.warning("build_feature_matrix: no entries in race_data")
            return None

        rows = []
        for entry in entries:
            row = self.extract_entry_features(entry, race_data)
            rows.append(row)

        matrix = np.array(rows, dtype=float)
        logger.debug("Feature matrix shape: %s", matrix.shape)
        return matrix

    def extract_entry_features(
        self,
        entry: Dict[str, Any],
        race_data: Optional[Dict[str, Any]] = None,
    ) -> List[float]:
        """Extract a flat feature vector for a single race entry.

        Args:
            entry: Entry dictionary (rider + boat statistics).
            race_data: Optional dictionary with race-level features such as
                weather and course conditions.

        Returns:
            List of floats of length FEATURE_DIM.
        """
        if race_data is None:
            race_data = {}

        win_rate = float(entry.get("win_rate", 0.0))
        place_rate = float(entry.get("place_rate", 0.0))
        payoff_rate = float(entry.get("payoff_rate", 0.0))
        avg_start_timing = float(entry.get("avg_start_timing", 0.0))
        recent_win_rate = self._recent_win_rate(entry)
        is_top_rider = 1.0 if entry.get("rank") in ("A1", "A2") else 0.0
        flying_count = float(entry.get("flying_count", 0))

        engine_rate = float(entry.get("engine_rate", 0.0))
        boat_win_rate = float(entry.get("boat_win_rate", 0.0))
        boat_place_rate = float(entry.get("boat_place_rate", 0.0))
        exhibition_time = float(entry.get("exhibition_time", 0.0))
        boat_start_timing = float(entry.get("boat_start_timing", 0.0))

        wind_speed = float(race_data.get("wind_speed", 0.0))
        wave_height = float(race_data.get("wave_height", 0.0))
        air_temperature = float(race_data.get("air_temperature", 20.0))
        water_temperature = float(race_data.get("water_temperature", 20.0))
        frame_number = float(entry.get("frame_number", 0))

        return [
            win_rate,           # FEATURE_WIN_RATE
            place_rate,         # FEATURE_PLACE_RATE
            payoff_rate,        # FEATURE_PAYOFF_RATE
            avg_start_timing,   # FEATURE_AVG_START_TIMING
            recent_win_rate,    # FEATURE_RECENT_WIN_RATE
            is_top_rider,       # FEATURE_IS_TOP_RIDER
            flying_count,       # FEATURE_FLYING_COUNT
            engine_rate,        # FEATURE_ENGINE_RATE
            boat_win_rate,      # FEATURE_BOAT_WIN_RATE
            boat_place_rate,    # FEATURE_BOAT_PLACE_RATE
            exhibition_time,    # FEATURE_EXHIBITION_TIME
            boat_start_timing,  # FEATURE_BOAT_START_TIMING
            wind_speed,         # FEATURE_WIND_SPEED
            wave_height,        # FEATURE_WAVE_HEIGHT
            air_temperature,    # FEATURE_AIR_TEMP
            water_temperature,  # FEATURE_WATER_TEMP
            frame_number,       # FEATURE_FRAME_NUMBER
        ]

    def normalize(self, matrix: np.ndarray) -> np.ndarray:
        """Apply min-max normalisation column-wise to a feature matrix.

        Columns with zero range (constant columns) are left unchanged.

        Args:
            matrix: Feature matrix of shape (n_samples, n_features).

        Returns:
            Normalised matrix with the same shape.
        """
        col_min = matrix.min(axis=0)
        col_max = matrix.max(axis=0)
        col_range = col_max - col_min

        # Avoid division by zero for constant columns
        col_range_safe = np.where(col_range == 0, 1.0, col_range)
        normalized = (matrix - col_min) / col_range_safe
        return normalized

    def compute_score_vector(
        self,
        matrix: np.ndarray,
        weights: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Compute a scalar score for each entry via a weighted dot product.

        Args:
            matrix: Feature matrix of shape (n_entries, FEATURE_DIM).
            weights: Optional weight vector of length FEATURE_DIM.  When
                omitted, uniform weights are used.

        Returns:
            Score vector of shape (n_entries,).
        """
        if weights is None:
            weights = np.ones(matrix.shape[1]) / matrix.shape[1]
        return matrix @ weights

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _recent_win_rate(entry: Dict[str, Any]) -> float:
        """Compute win rate from the recent_results list in an entry dict.

        Args:
            entry: Entry dictionary that may contain 'recent_results'.

        Returns:
            Fraction of '1' results, or 0.0 if recent_results is absent/empty.
        """
        results: List[str] = entry.get("recent_results", [])
        if not results:
            return 0.0
        wins = sum(1 for r in results if str(r) == "1")
        return wins / len(results)
