"""Quick EDA: trend, weather relationship, sensor offsets, autocorrelation."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
df = pd.read_csv(ROOT / "data/clean_daily.csv", parse_dates=["date"])
w = pd.read_csv(ROOT / "weather/weather_history.csv", parse_dates=["date"])
hw = pd.read_csv(ROOT / "holdout/holdout_weather.csv", parse_dates=["date"])

city = df.groupby("date").pm25_observed.mean().rename("city_pm").reset_index().merge(w, on="date")
city["week"] = city.date.dt.to_period("W").dt.start_time
print("Weekly city mean PM2.5 + weather:")
print(city.groupby("week")[["city_pm", "temp_c", "humidity_pct", "wind_kmh"]].mean().round(1).to_string())

print("\nCorrelation of city PM2.5 with same-day weather:")
print(city[["city_pm", "temp_c", "humidity_pct", "wind_kmh"]].corr().city_pm.round(3).to_string())
last30 = city[city.date >= city.date.max() - pd.Timedelta(days=30)]
print("\n...last 30 days only:")
print(last30[["city_pm", "temp_c", "humidity_pct", "wind_kmh"]].corr().city_pm.round(3).to_string())

print("\nHoldout weather summary vs last 14 days history:")
print(hw[["temp_c", "humidity_pct", "wind_kmh"]].describe().round(1).loc[["mean", "min", "max"]].to_string())
print(w.tail(14)[["temp_c", "humidity_pct", "wind_kmh"]].describe().round(1).loc[["mean", "min", "max"]].to_string())

# Sensor offset vs city mean (stable sensor effect?)
df = df.merge(city[["date", "city_pm"]], on="date")
df["ratio"] = df.pm25_observed / df.city_pm
print("\nSensor ratio to city mean (first half vs second half):")
mid = df.date.min() + (df.date.max() - df.date.min()) / 2
print(pd.DataFrame({
    "h1": df[df.date < mid].groupby("sensor_id").ratio.mean(),
    "h2": df[df.date >= mid].groupby("sensor_id").ratio.mean()}).round(3).T.to_string())

# Autocorrelation of sensor residual (pm - city) and city series
for lag in [1, 2, 3, 5, 7, 10]:
    print(f"lag {lag}: city autocorr {city.city_pm.autocorr(lag):.3f}", end=" | ")
    resid = (df.pm25_observed - df.city_pm)
    ac = df.assign(r=resid).groupby("sensor_id").r.apply(lambda s: s.autocorr(lag)).mean()
    print(f"sensor residual autocorr {ac:.3f}")

print("\nLast 10 days per sensor (observed):")
print(df[df.date > df.date.max() - pd.Timedelta(days=10)]
      .pivot(index="date", columns="sensor_id", values="pm25_observed").round(0).to_string())
