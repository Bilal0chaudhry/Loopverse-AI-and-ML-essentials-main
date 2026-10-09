from __future__ import annotations
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parent.parent
TEAM_TABLE = ROOT / "data/forecast_table.csv"            
REFERENCE_TABLE = ROOT / "data/reference_forecast.csv"   
HAZARD = 165.0
AREA_ALIASES = {
    "gulberg": "Gulberg",
    "dha": "DHA", "defence": "DHA", "defense": "DHA", "d.h.a": "DHA",
    "johar town": "Johar Town", "johar": "Johar Town", "joher town": "Johar Town",
    "model town": "Model Town",
    "wagah": "Wagah", "wagha": "Wagah", "wagah border": "Wagah",
    "thokar niaz baig": "Thokar Niaz Baig", "thokar": "Thokar Niaz Baig", "niaz baig": "Thokar Niaz Baig",
    "allama iqbal town": "Allama Iqbal Town", "iqbal town": "Allama Iqbal Town", "aiqbal town": "Allama Iqbal Town",
    "shadman": "Shadman",
    "cantt": "Cantt", "cantonment": "Cantt", "lahore cantt": "Cantt",
    "faisal town": "Faisal Town",
    "township": "Township",
    "walled city": "Walled City", "androon shehar": "Walled City", "androon lahore": "Walled City",
    "andaroon shehar": "Walled City", "old city": "Walled City",
    "raiwind road": "Raiwind Road", "raiwind": "Raiwind Road",
    "bahria town": "Bahria Town", "bahria": "Bahria Town",
    "airport road": "Airport Road", "airport": "Airport Road",
}
@lru_cache(maxsize=1)
def _meta() -> pd.DataFrame:
    return pd.read_csv(ROOT / "weather/sensor_metadata.csv")
def covered_areas() -> list[str]:
    return _meta().area.tolist()
def area_to_sensor(area: str) -> str:
    m = _meta()
    return m.loc[m.area == area, "sensor_id"].iloc[0]
def resolve_location(location) -> str | None:
    if not isinstance(location, str):
        return None
    loc = re.sub(r"\s+", " ", location.strip().lower())
    loc = re.sub(r",?\s*lahore$", "", loc).strip()
    m = _meta()
    if re.fullmatch(r"s(0[1-9]|1[0-5])", loc):
        return m.loc[m.sensor_id == loc.upper(), "area"].iloc[0]
    for area in m.area:
        if loc == area.lower():
            return area
    return AREA_ALIASES.get(loc)
@lru_cache(maxsize=1)
def _table() -> tuple[pd.DataFrame | None, str]:
    if TEAM_TABLE.exists():
        return pd.read_csv(TEAM_TABLE), "team_model"
    if REFERENCE_TABLE.exists():
        return pd.read_csv(REFERENCE_TABLE), "reference_fallback"
    return None, "team_model"
def supported_window() -> tuple[str, str] | None:
    t, _ = _table()
    if t is None:
        return None
    return t.target_date.min(), t.target_date.max()
def forecast_with_reason(location, target_date) -> tuple[dict, str]:
    table, source = _table()
    area = resolve_location(location)
    td = target_date.isoformat() if isinstance(target_date, date) else str(target_date).strip()
    result = {
        "location": area or (str(location) if location is not None else ""),
        "target_date": td,
        "pm25": None,
        "hazardous": None,
        "status": "unavailable",
        "source": source,
    }
    if table is None:
        return result, "no forecast table available"
    if area is None:
        return result, f"location '{location}' is not one of the 15 covered Lahore areas"
    try:
        parsed = date.fromisoformat(td)
    except ValueError:
        return result, f"target_date '{td}' is not a valid YYYY-MM-DD date"
    result["target_date"] = parsed.isoformat()
    row = table[(table.area == area) & (table.target_date == parsed.isoformat())]
    if len(row) != 1:
        lo, hi = supported_window()
        return result, f"{parsed.isoformat()} is outside the supported forecast window {lo} to {hi}"
    pm = float(row.predicted_pm25.iloc[0])
    result.update(pm25=round(pm, 1), hazardous=bool(pm >= HAZARD), status="ok")
    return result, "ok"
def forecast(location, target_date) -> dict:
    return forecast_with_reason(location, target_date)[0]
if __name__ == "__main__":
    for args in [("Gulberg", "2026-10-29"), ("s12", "2026-11-07"), ("Karachi", "2026-10-30"),
                 ("DHA", "2026-12-01"), ("Model Town", "tomorrow")]:
        print(args, "->", forecast(*args))
