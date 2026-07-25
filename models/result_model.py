"""
Result Data Model
Stores historical boat race results and payout information.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List, Dict


@dataclass
class RaceEntry:
    """Result for a single entry in a race.

    Attributes:
        frame_number: Lane number (1–6).
        rider_id: Rider identifier.
        boat_id: Boat identifier.
        finishing_position: Final finishing position (1 = winner).
        start_timing: Recorded start timing in seconds.
        race_time: Lap time for this entry in seconds.
        disqualified: Whether this entry was disqualified.
        disqualification_reason: Reason for disqualification if applicable.
    """

    frame_number: int
    rider_id: str
    boat_id: str
    finishing_position: int = 0
    start_timing: float = 0.0
    race_time: float = 0.0
    disqualified: bool = False
    disqualification_reason: str = ""

    def to_dict(self) -> dict:
        """Serialise the instance to a plain dictionary."""
        return {
            "frame_number": self.frame_number,
            "rider_id": self.rider_id,
            "boat_id": self.boat_id,
            "finishing_position": self.finishing_position,
            "start_timing": self.start_timing,
            "race_time": self.race_time,
            "disqualified": self.disqualified,
            "disqualification_reason": self.disqualification_reason,
        }


@dataclass
class ResultData:
    """Data class for historical race results and payout information.

    Attributes:
        result_id: Unique identifier for this result record.
        race_id: Identifier of the associated race.
        race_date: Date of the race.
        location: Name of the race venue.
        race_number: Race number at the venue.
        entries: Ordered list of RaceEntry instances (by finishing position).
        trifecta_payout: Payout for the winning 3-boat combination (trifecta).
        quinella_payout: Payout for the top-2 combination (quinella).
        win_payout: Payout for picking the winner.
        place_payouts: Mapping of frame_number to place payout.
        exacta_payout: Payout for the exact 1st–2nd order.
        bracket_quinella_payout: Payout for bracket quinella.
        cancelled: Whether the race was cancelled.
        cancel_reason: Reason for cancellation if applicable.
        created_at: Timestamp when this record was created.
    """

    result_id: str
    race_id: str
    race_date: date
    location: str
    race_number: int
    entries: List[RaceEntry] = field(default_factory=list)
    trifecta_payout: float = 0.0
    quinella_payout: float = 0.0
    win_payout: float = 0.0
    place_payouts: Dict[int, float] = field(default_factory=dict)
    exacta_payout: float = 0.0
    bracket_quinella_payout: float = 0.0
    cancelled: bool = False
    cancel_reason: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Validate field values after initialisation."""
        if not self.result_id:
            raise ValueError("result_id must not be empty")
        if not self.race_id:
            raise ValueError("race_id must not be empty")
        if not (1 <= self.race_number <= 12):
            raise ValueError("race_number must be between 1 and 12")

    def winner(self) -> Optional[RaceEntry]:
        """Return the entry that finished in first place.

        Returns:
            The winning RaceEntry, or None if not yet determined.
        """
        for entry in self.entries:
            if entry.finishing_position == 1:
                return entry
        return None

    def top_three(self) -> List[RaceEntry]:
        """Return entries finishing in 1st, 2nd, and 3rd place.

        Returns:
            List of up to three RaceEntry instances sorted by position.
        """
        podium = [e for e in self.entries if e.finishing_position in (1, 2, 3)]
        return sorted(podium, key=lambda e: e.finishing_position)

    def to_dict(self) -> dict:
        """Serialise the instance to a plain dictionary.

        Returns:
            Dictionary representation of this result.
        """
        return {
            "result_id": self.result_id,
            "race_id": self.race_id,
            "race_date": self.race_date.isoformat(),
            "location": self.location,
            "race_number": self.race_number,
            "entries": [e.to_dict() for e in self.entries],
            "trifecta_payout": self.trifecta_payout,
            "quinella_payout": self.quinella_payout,
            "win_payout": self.win_payout,
            "place_payouts": {str(k): v for k, v in self.place_payouts.items()},
            "exacta_payout": self.exacta_payout,
            "bracket_quinella_payout": self.bracket_quinella_payout,
            "cancelled": self.cancelled,
            "cancel_reason": self.cancel_reason,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ResultData":
        """Create a ResultData instance from a dictionary.

        Args:
            data: Dictionary containing result fields.

        Returns:
            A new ResultData instance.
        """
        race_date_raw = data.get("race_date")
        if isinstance(race_date_raw, str):
            race_date = date.fromisoformat(race_date_raw)
        else:
            race_date = race_date_raw

        entries = [
            RaceEntry(
                frame_number=int(e["frame_number"]),
                rider_id=e["rider_id"],
                boat_id=e["boat_id"],
                finishing_position=int(e.get("finishing_position", 0)),
                start_timing=float(e.get("start_timing", 0.0)),
                race_time=float(e.get("race_time", 0.0)),
                disqualified=bool(e.get("disqualified", False)),
                disqualification_reason=e.get("disqualification_reason", ""),
            )
            for e in data.get("entries", [])
        ]

        place_payouts_raw = data.get("place_payouts", {})
        place_payouts = {int(k): float(v) for k, v in place_payouts_raw.items()}

        return cls(
            result_id=data["result_id"],
            race_id=data["race_id"],
            race_date=race_date,
            location=data["location"],
            race_number=int(data["race_number"]),
            entries=entries,
            trifecta_payout=float(data.get("trifecta_payout", 0.0)),
            quinella_payout=float(data.get("quinella_payout", 0.0)),
            win_payout=float(data.get("win_payout", 0.0)),
            place_payouts=place_payouts,
            exacta_payout=float(data.get("exacta_payout", 0.0)),
            bracket_quinella_payout=float(data.get("bracket_quinella_payout", 0.0)),
            cancelled=bool(data.get("cancelled", False)),
            cancel_reason=data.get("cancel_reason", ""),
        )
