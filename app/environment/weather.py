"""Weather rules for HarvestAgent."""

WEATHER_WEIGHTS = (
    ("sunny", 0.65),
    ("rainy", 0.25),
    ("storm", 0.10),
)


def is_auto_water_weather(weather: str) -> bool:
    return weather in {"rainy", "storm"}


def is_mine_closed(weather: str, event_type: str | None = None) -> bool:
    return weather == "storm" or event_type == "mine_collapse"


def is_river_closed(weather: str) -> bool:
    return weather == "storm"
