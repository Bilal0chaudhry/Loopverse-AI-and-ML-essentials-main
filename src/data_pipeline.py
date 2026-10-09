from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data"
EPA_PM25_BREAKPOINTS = [
    (0.0, 12.0, 0, 50), (12.1, 35.4, 51, 100), (35.5, 55.4, 101, 150),
    (55.5, 150.4, 151, 200), (150.5, 250.4, 201, 300), (250.5, 350.4, 301, 400),
    (350.5, 500.4, 401, 500),
]
FLATLINE_MIN_RUN = 3
def aqi_to_pm25(aqi: float) -> float:
    if pd.isna(aqi):
        return np.nan
    for c_lo, c_hi, i_lo, i_hi in EPA_PM25_BREAKPOINTS:
        if i_lo <= aqi <= i_hi:
            return (c_hi - c_lo) / (i_hi - i_lo) * (aqi - i_lo) + c_lo
    raise ValueError(f"AQI out of range: {aqi}")
def pm25_to_aqi(c: float) -> float:
    if pd.isna(c):
        return np.nan
    c = np.floor(c * 10) / 10
    for c_lo, c_hi, i_lo, i_hi in EPA_PM25_BREAKPOINTS:
        if c_lo <= c <= c_hi:
            return round((i_hi - i_lo) / (c_hi - c_lo) * (c - c_lo) + i_lo)
    return np.nan
def flag_flatlines(s: pd.Series, min_run: int = FLATLINE_MIN_RUN) -> pd.Series:
    grp = (s != s.shift()).cumsum()
    run_len = s.groupby(grp).transform("size")
    return (run_len >= min_run) & s.notna()
def build() -> pd.DataFrame:
    b1 = pd.read_csv(ROOT / "sensors/batch_1_sensor_data.csv")
    b2 = pd.read_csv(ROOT / "sensors/batch_2_sensor_data.csv")
    meta = pd.read_csv(ROOT / "weather/sensor_metadata.csv")
    b1["date"] = (pd.to_datetime(b1.timestamp, format="%Y-%m-%d %H:%M:%S")
                  + pd.Timedelta(hours=5)).dt.normalize()
    b2["date"] = pd.to_datetime(b2.timestamp, format="%Y-%m-%d")
    assert (pd.to_datetime(b1.timestamp).dt.hour == 19).all(), "unexpected UTC hour in batch_1"
    b1["pm25_b1"] = b1.reading_value.replace(-999, np.nan)
    b2["aqi_b2"] = b2.reading_value.replace(-999, np.nan)
    assert (b1.pm25_b1.dropna() >= 0).all() and (b2.aqi_b2.dropna() >= 0).all()
    b2["pm25_b2"] = b2.aqi_b2.apply(aqi_to_pm25)
    df = b1[["sensor_id", "date", "pm25_b1"]].merge(
        b2[["sensor_id", "date", "aqi_b2", "pm25_b2"]], on=["sensor_id", "date"], how="outer"
    ).sort_values(["sensor_id", "date"]).reset_index(drop=True)
    assert not df.duplicated(["sensor_id", "date"]).any()
    both = df.dropna(subset=["pm25_b1", "aqi_b2"])
    agree = (both.pm25_b1.apply(pm25_to_aqi) - both.aqi_b2).abs() <= 1
    assert agree.mean() > 0.99, f"batch agreement too low: {agree.mean():.3f}"
    df["flag_flatline"] = df.groupby("sensor_id").pm25_b1.transform(flag_flatlines)
    df["source"] = np.where(df.pm25_b1.notna(), "batch_1",
                            np.where(df.pm25_b2.notna(), "batch_2_converted", "none"))
    df["pm25_observed"] = df.pm25_b1.fillna(df.pm25_b2)
    df.loc[df.flag_flatline, ["pm25_observed"]] = np.nan
    df.loc[df.flag_flatline, "source"] = "flatline_removed"
    df["pm25_filled"] = df.groupby("sensor_id").pm25_observed.transform(
        lambda s: s.interpolate(limit_direction="both"))
    df["flag_imputed"] = df.pm25_observed.isna()
    df = df.merge(meta[["sensor_id", "area", "batch"]], on="sensor_id", how="left")
    return df
def main():
    df = build()
    OUT.mkdir(exist_ok=True)
    df.assign(date=df.date.dt.strftime("%Y-%m-%d")).to_csv(OUT / "clean_daily.csv", index=False)
    print("rows:", len(df), "| sensors:", df.sensor_id.nunique(),
          "| dates:", df.date.min().date(), "->", df.date.max().date())
    print("source counts:", df.source.value_counts().to_dict())
    print("flat-line rows:\n", df.loc[df.flag_flatline, ["sensor_id", "date", "pm25_b1"]].to_string(index=False))
    print("remaining imputed rows:", int(df.flag_imputed.sum()))
    print("PM2.5 >= 165 days (observed):", int((df.pm25_observed >= 165).sum()),
          f"({(df.pm25_observed >= 165).mean():.1%})")
if __name__ == "__main__":
    main()
