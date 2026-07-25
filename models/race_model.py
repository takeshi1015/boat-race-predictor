"""
Race Data Model
Stores boat race information including date, location, weather, and race details.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List


@dataclass
class RaceData:
    """Data class for storing boat race information.

    Attributes:
        race_id: Unique identifier for the race.
        race_number: Race number at the venue (1-12).
        race_date: Date of the race.
        location: Name of the race venue.
        location_code: Venue code (e.g. '01' for Kiryu).
        grade: Race grade (SG, G1, G2, G3, or general).
        race_class: Class of the race.
        distance: Course distance in metres.
        course_type: Type of course (e.g. 'straight', 'round').
        weather: Weather conditions at race time.
        wind_direction: Wind direction (e.g. 'N', 'SW').
        wind_speed: Wind speed in m/s.
        wave_height: Wave height in cm.
        water_temperature: Water temperature in degrees Celsius.
        air_temperature: Air temperature in degrees Celsius.
        is_night_race: Whether the race is held at night.
        participant_ids: List of registered participant IDs.
        start_time: Scheduled start time of the race.
        created_at: Timestamp when this record was created.
    """

    race_id: str
    race_number: int
    race_date: date
    location: str
    location_code: str
    grade: str = "general"
    race_class: str = ""
    distance: int = 1800
    course_type: str = "straight"
    weather: str = "sunny"
    wind_direction: str = ""
    wind_speed: float = 0.0
    wave_height: float = 0.0
    water_temperature: float = 20.0
    air_temperature: float = 20.0
    is_night_race: bool = False
    participant_ids: List[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Validate field values after initialisation."""
        if not self.race_id:
            raise ValueError("race_id must not be empty")
        if not (1 <= self.race_number <= 12):
            raise ValueError("race_number must be between 1 and 12")
        if self.wind_speed < 0:
            raise ValueError("wind_speed must not be negative")
        if self.wave_height < 0:
            raise ValueError("wave_height must not be negative")

    def is_good_condition(self) -> bool:
        """Return True if racing conditions are considered good.

        Returns:
            True when wind speed is below 5 m/s and wave height is below 15 cm.
        """
        return self.wind_speed < 5.0 and self.wave_height < 15.0

    def to_dict(self) -> dict:
        """Serialise the instance to a plain dictionary.

        Returns:
            Dictionary representation of this race.
        """
        return {
            "race_id": self.race_id,
            "race_number": self.race_number,
            "race_date": self.race_date.isoformat(),
            "location": self.location,
            "location_code": self.location_code,
            "grade": self.grade,
            "race_class": self.race_class,
            "distance": self.distance,
            "course_type": self.course_type,
            "weather": self.weather,
            "wind_direction": self.wind_direction,
            "wind_speed": self.wind_speed,
            "wave_height": self.wave_height,
            "water_temperature": self.water_temperature,
            "air_temperature": self.air_temperature,
            "is_night_race": self.is_night_race,
            "participant_ids": self.participant_ids,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RaceData":
        """Create a RaceData instance from a dictionary.

        Args:
            data: Dictionary containing race fields.

        Returns:
            A new RaceData instance.
        """
        race_date_raw = data.get("race_date")
        if isinstance(race_date_raw, str):
            race_date = date.fromisoformat(race_date_raw)
        else:
            race_date = race_date_raw

        start_time_raw = data.get("start_time")
        start_time: Optional[datetime] = None
        if isinstance(start_time_raw, str):
            start_time = datetime.fromisoformat(start_time_raw)
        elif isinstance(start_time_raw, datetime):
            start_time = start_time_raw

        return cls(
            race_id=data["race_id"],
            race_number=int(data["race_number"]),
            race_date=race_date,
            location=data["location"],
            location_code=data["location_code"],
            grade=data.get("grade", "general"),
            race_class=data.get("race_class", ""),
            distance=int(data.get("distance", 1800)),
            course_type=data.get("course_type", "straight"),
            weather=data.get("weather", "sunny"),
            wind_direction=data.get("wind_direction", ""),
            wind_speed=float(data.get("wind_speed", 0.0)),
            wave_height=float(data.get("wave_height", 0.0)),
            water_temperature=float(data.get("water_temperature", 20.0)),
            air_temperature=float(data.get("air_temperature", 20.0)),
            is_night_race=bool(data.get("is_night_race", False)),
            participant_ids=list(data.get("participant_ids", [])),
            start_time=start_time,
        )
