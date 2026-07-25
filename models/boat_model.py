"""
Boat Data Model
Stores boat specifications and maintenance history.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List


@dataclass
class BoatData:
    """Data class for boat specifications and history.

    Attributes:
        boat_id: Unique identifier for the boat.
        boat_number: Official boat number.
        age: Age of the boat in years.
        manufacturer: Manufacturer of the boat.
        engine_id: Identifier for the attached engine.
        engine_rate: Engine performance rate (0.0–1.0).
        exhibition_time: Exhibition lap time in seconds.
        start_timing: Average start timing in seconds (negative = early).
        win_rate: Win rate across all races with this boat (0.0–1.0).
        place_rate: Top-3 placement rate (0.0–1.0).
        recent_maintenance: Description of the most recent maintenance.
        last_maintenance_date: Date of the most recent maintenance.
        race_history: List of race IDs this boat has competed in.
        created_at: Timestamp when this record was created.
    """

    boat_id: str
    boat_number: int
    age: float = 0.0
    manufacturer: str = ""
    engine_id: str = ""
    engine_rate: float = 0.0
    exhibition_time: float = 0.0
    start_timing: float = 0.0
    win_rate: float = 0.0
    place_rate: float = 0.0
    recent_maintenance: str = ""
    last_maintenance_date: Optional[date] = None
    race_history: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Validate field values after initialisation."""
        if not self.boat_id:
            raise ValueError("boat_id must not be empty")
        if not (0.0 <= self.win_rate <= 1.0):
            raise ValueError("win_rate must be between 0.0 and 1.0")
        if not (0.0 <= self.place_rate <= 1.0):
            raise ValueError("place_rate must be between 0.0 and 1.0")

    def is_high_performance(self) -> bool:
        """Return True if the boat is considered high-performance.

        A boat is high-performance when its engine rate exceeds 0.6 and its
        win rate exceeds 0.4.

        Returns:
            True if the boat is high-performance.
        """
        return self.engine_rate > 0.6 and self.win_rate > 0.4

    def to_dict(self) -> dict:
        """Serialise the instance to a plain dictionary.

        Returns:
            Dictionary representation of this boat.
        """
        return {
            "boat_id": self.boat_id,
            "boat_number": self.boat_number,
            "age": self.age,
            "manufacturer": self.manufacturer,
            "engine_id": self.engine_id,
            "engine_rate": self.engine_rate,
            "exhibition_time": self.exhibition_time,
            "start_timing": self.start_timing,
            "win_rate": self.win_rate,
            "place_rate": self.place_rate,
            "recent_maintenance": self.recent_maintenance,
            "last_maintenance_date": (
                self.last_maintenance_date.isoformat()
                if self.last_maintenance_date
                else None
            ),
            "race_history": self.race_history,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BoatData":
        """Create a BoatData instance from a dictionary.

        Args:
            data: Dictionary containing boat fields.

        Returns:
            A new BoatData instance.
        """
        last_maint_raw = data.get("last_maintenance_date")
        last_maintenance_date: Optional[date] = None
        if isinstance(last_maint_raw, str):
            last_maintenance_date = date.fromisoformat(last_maint_raw)
        elif isinstance(last_maint_raw, date):
            last_maintenance_date = last_maint_raw

        return cls(
            boat_id=data["boat_id"],
            boat_number=int(data["boat_number"]),
            age=float(data.get("age", 0.0)),
            manufacturer=data.get("manufacturer", ""),
            engine_id=data.get("engine_id", ""),
            engine_rate=float(data.get("engine_rate", 0.0)),
            exhibition_time=float(data.get("exhibition_time", 0.0)),
            start_timing=float(data.get("start_timing", 0.0)),
            win_rate=float(data.get("win_rate", 0.0)),
            place_rate=float(data.get("place_rate", 0.0)),
            recent_maintenance=data.get("recent_maintenance", ""),
            last_maintenance_date=last_maintenance_date,
            race_history=list(data.get("race_history", [])),
        )
