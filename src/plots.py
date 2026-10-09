"""Audit plots required by the handbook. Run after data_pipeline:  python src/plots.py  -> reports/*.png"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
df = pd.read_csv(ROOT / "data/clean_daily.csv", parse_dates=["date"])
(ROOT / "reports").mkdir(exist_ok=True)
fig, ax = plt.subplots(2, 2, figsize=(16, 8))

s02 = df[df.sensor_id == "S02"]
ax[0, 0].plot(s02.date, s02.pm25_b1, label="batch_1 (UTC -> PKT)")
ax[0, 0].plot(s02.date, s02.pm25_b2, "--", label="batch_2 (AQI -> PM2.5)")
ax[0, 0].set_title("Trap 2: same sensor (S02, DHA) in both networks after conversion"); ax[0, 0].legend()

cov = df.assign(n=df[["pm25_b1", "pm25_b2"]].notna().sum(axis=1)).pivot(index="sensor_id", columns="date", values="n")
im = ax[0, 1].imshow(cov, aspect="auto", vmin=0, vmax=2)
ax[0, 1].set_yticks(range(len(cov)), cov.index); ax[0, 1].set_xlabel("day (0 = 2026-07-01)")
ax[0, 1].set_title("Coverage: valid readings per sensor-day (0, 1 or 2 files)"); fig.colorbar(im, ax=ax[0, 1])

s07 = df[(df.sensor_id == "S07") & df.date.between("2026-08-15", "2026-09-05")]
ax[1, 0].plot(s07.date, s07.pm25_b1, "o-", label="raw"); ax[1, 0].plot(s07.date, s07.pm25_filled, label="cleaned")
ax[1, 0].set_title("Trap 3: S07 flat line removed"); ax[1, 0].legend()

city = df.groupby("date").pm25_filled.mean()
wd = (city - city.rolling(7, center=True).mean()).groupby(city.index.dayofweek).mean()
ax[1, 1].bar(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], wd)
ax[1, 1].set_title("Weekly pattern used by the final model (city PM2.5 vs weekly mean)")
for a in (ax[0, 0], ax[1, 0]):
    a.tick_params(axis="x", rotation=45)
plt.tight_layout(); plt.savefig(ROOT / "reports/audit_plots.png", dpi=110)
print("saved reports/audit_plots.png")
