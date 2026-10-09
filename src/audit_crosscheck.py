"""Cross-check: are batch_1 (UTC, PM2.5) and batch_2 (PKT, AQI) the same measurements?"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
b1 = pd.read_csv(ROOT / "sensors/batch_1_sensor_data.csv")
b2 = pd.read_csv(ROOT / "sensors/batch_2_sensor_data.csv")

b1["date"] = (pd.to_datetime(b1.timestamp) + pd.Timedelta(hours=5)).dt.strftime("%Y-%m-%d")
b2["date"] = pd.to_datetime(b2.timestamp).dt.strftime("%Y-%m-%d")
b1.loc[b1.reading_value == -999, "reading_value"] = np.nan
b2.loc[b2.reading_value == -999, "reading_value"] = np.nan

# US EPA PM2.5 breakpoints: (C_lo, C_hi, I_lo, I_hi)
OLD = [(0.0, 12.0, 0, 50), (12.1, 35.4, 51, 100), (35.5, 55.4, 101, 150), (55.5, 150.4, 151, 200),
       (150.5, 250.4, 201, 300), (250.5, 350.4, 301, 400), (350.5, 500.4, 401, 500)]
NEW = [(0.0, 9.0, 0, 50), (9.1, 35.4, 51, 100), (35.5, 55.4, 101, 150), (55.5, 125.4, 151, 200),
       (125.5, 225.4, 201, 300), (225.5, 325.4, 301, 500)]

def pm_to_aqi(c, bp):
    if np.isnan(c):
        return np.nan
    c = np.floor(c * 10) / 10
    for clo, chi, ilo, ihi in bp:
        if clo <= c <= chi:
            return round((ihi - ilo) / (chi - clo) * (c - clo) + ilo)
    return np.nan

m = b1.merge(b2, on=["sensor_id", "date"], suffixes=("_b1", "_b2"))
print("merged rows:", len(m), "date range:", m.date.min(), m.date.max())
for name, bp in [("OLD EPA", OLD), ("NEW 2024 EPA", NEW)]:
    m[f"aqi_{name}"] = m.reading_value_b1.apply(lambda c: pm_to_aqi(c, bp))
    ok = m[["reading_value_b2", f"aqi_{name}"]].dropna()
    diff = (ok.reading_value_b2 - ok[f"aqi_{name}"]).abs()
    print(f"{name}: exact match {(diff == 0).mean():.1%}, |diff|<=1 {(diff <= 1).mean():.1%}, mean|diff| {diff.mean():.2f}")

print("\nPer-sensor agreement (OLD EPA, |diff|<=1):")
m["d"] = (m.reading_value_b2 - m["aqi_OLD EPA"]).abs()
print(m.groupby("sensor_id").d.apply(lambda s: f"{(s.dropna() <= 1).mean():.0%} (n={s.notna().sum()})").to_string())

print("\nDisagreeing rows (|diff|>1):")
print(m.loc[m.d > 1, ["sensor_id", "date", "reading_value_b1", "reading_value_b2", "aqi_OLD EPA"]].head(30).to_string())

print("\nMissing pattern: b1 NaN & b2 NaN same day:",
      (m.reading_value_b1.isna() & m.reading_value_b2.isna()).sum(),
      "| b1-only NaN:", (m.reading_value_b1.isna() & m.reading_value_b2.notna()).sum(),
      "| b2-only NaN:", (m.reading_value_b2.isna() & m.reading_value_b1.notna()).sum())

print("\nS07 around flat-line:")
print(m.loc[(m.sensor_id == "S07") & m.date.between("2026-08-22", "2026-08-30"),
            ["date", "reading_value_b1", "reading_value_b2"]].to_string())
