"""
Rider Data Model
Stores rider/jockey information and career statistics.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List


@dataclass
class RiderData:
    """Data class for rider/jockey information and statistics.

    Attributes:
        rider_id: Unique identifier for the rider.
        name: Full name of the rider.
        registration_number: Official registration number.
        branch: Branch (home track) of the rider.
        birth_date: Date of birth.
        gender: Gender of the rider.
        rank: Current rank/class (e.g. 'A1', 'A2', 'B1', 'B2').
        weight: Body weight in kg.
        win_rate: Career win rate (0.0–1.0).
        place_rate: Career top-3 placement rate (0.0–1.0).
        payoff_rate: Payout rate across career races.
        avg_start_timing: Average start timing in seconds.
        flying_count: Number of flying starts (fouls) in recent period.
        late_start_count: Number of late starts in recent period.
        recent_results: List of recent result codes (e.g. ['1', '2', '1', '3']).
        annual_wins: Number of wins in the current year.
        total_races: Total number of career races.
        total_wins: Total number of career wins.
        created_at: Timestamp when this record was created.
    """

    rider_id: str
    name: str
    registration_number: str
    branch: str = ""
    birth_date: Optional[date] = None
    gender: str = "male"
    rank: str = "B1"
    weight: float = 52.0
    win_rate: float = 0.0
    place_rate: float = 0.0
    payoff_rate: float = 0.0
    avg_start_timing: float = 0.0
    flying_count: int = 0
    late_start_count: int = 0
    recent_results: List[str] = field(default_factory=list)
    annual_wins: int = 0
    total_races: int = 0
    total_wins: int = 0
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Validate field values after initialisation."""
        if not self.rider_id:
            raise ValueError("rider_id must not be empty")
        if not self.name:
            raise ValueError("name must not be empty")
        if not (0.0 <= self.win_rate <= 1.0):
            raise ValueError("win_rate must be between 0.0 and 1.0")
        if not (0.0 <= self.place_rate <= 1.0):
            raise ValueError("place_rate must be between 0.0 and 1.0")

    def age(self) -> Optional[int]:
        """Calculate the rider's current age.

        Returns:
            Age in full years, or None if birth_date is not set.
        """
        if self.birth_date is None:
            return None
        today = date.today()
        return (
            today.year
            - self.birth_date.year
            - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        )

    def recent_win_rate(self) -> float:
        """Calculate the win rate from recent_results.

        Returns:
            Fraction of '1' results in recent_results, or 0.0 if no results.
        """
        if not self.recent_results:
            return 0.0
        wins = sum(1 for r in self.recent_results if r == "1")
        return wins / len(self.recent_results)

    def is_top_rider(self) -> bool:
        """Return True if the rider is classified as top-tier.

        Returns:
            True when rank is A1 or A2.
        """
        return self.rank in ("A1", "A2")

    def to_dict(self) -> dict:
        """Serialise the instance to a plain dictionary.

        Returns:
            Dictionary representation of this rider.
        """
        return {
            "rider_id": self.rider_id,
            "name": self.name,
            "registration_number": self.registration_number,
            "branch": self.branch,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "gender": self.gender,
            "rank": self.rank,
            "weight": self.weight,
            "win_rate": self.win_rate,
            "place_rate": self.place_rate,
            "payoff_rate": self.payoff_rate,
            "avg_start_timing": self.avg_start_timing,
            "flying_count": self.flying_count,
            "late_start_count": self.late_start_count,
            "recent_results": self.recent_results,
            "annual_wins": self.annual_wins,
            "total_races": self.total_races,
            "total_wins": self.total_wins,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RiderData":
        """Create a RiderData instance from a dictionary.

        Args:
            data: Dictionary containing rider fields.

        Returns:
            A new RiderData instance.
        """
        birth_date_raw = data.get("birth_date")
        birth_date: Optional[date] = None
        if isinstance(birth_date_raw, str):
            birth_date = date.fromisoformat(birth_date_raw)
        elif isinstance(birth_date_raw, date):
            birth_date = birth_date_raw

        return cls(
            rider_id=data["rider_id"],
            name=data["name"],
            registration_number=data["registration_number"],
            branch=data.get("branch", ""),
            birth_date=birth_date,
            gender=data.get("gender", "male"),
            rank=data.get("rank", "B1"),
            weight=float(data.get("weight", 52.0)),
            win_rate=float(data.get("win_rate", 0.0)),
            place_rate=float(data.get("place_rate", 0.0)),
            payoff_rate=float(data.get("payoff_rate", 0.0)),
            avg_start_timing=float(data.get("avg_start_timing", 0.0)),
            flying_count=int(data.get("flying_count", 0)),
            late_start_count=int(data.get("late_start_count", 0)),
            recent_results=list(data.get("recent_results", [])),
            annual_wins=int(data.get("annual_wins", 0)),
            total_races=int(data.get("total_races", 0)),
            total_wins=int(data.get("total_wins", 0)),
        )
