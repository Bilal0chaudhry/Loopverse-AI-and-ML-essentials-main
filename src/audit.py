"""Exploratory data audit — prints facts, changes nothing."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
b1 = pd.read_csv(ROOT / "sensors/batch_1_sensor_data.csv")
b2 = pd.read_csv(ROOT / "sensors/batch_2_sensor_data.csv")
meta = pd.read_csv(ROOT / "weather/sensor_metadata.csv")

for name, df in [("batch_1", b1), ("batch_2", b2)]:
    print(f"\n===== {name}: {len(df)} rows =====")
    print("sensors:", sorted(df.sensor_id.unique()))
    print("rows per sensor:\n", df.groupby("sensor_id").size().to_dict())
    print("timestamp examples:", df.timestamp.head(3).tolist(), "...", df.timestamp.tail(2).tolist())
    print("ts lengths:", df.timestamp.str.len().value_counts().to_dict())
    print("-999 count:", (df.reading_value == -999).sum(),
          "| NaN:", df.reading_value.isna().sum(),
          "| negatives (not -999):", ((df.reading_value < 0) & (df.reading_value != -999)).sum())
    print(df.loc[df.reading_value != -999, "reading_value"].describe().round(1).to_dict())
    dup = df.duplicated(["sensor_id", "timestamp"]).sum()
    print("duplicate (sensor,timestamp):", dup)

    # flat-line: same value 3+ consecutive days for a sensor
    for sid, g in df.sort_values(["sensor_id", "timestamp"]).groupby("sensor_id"):
        v = g.reading_value.values
        run = 1
        for i in range(1, len(v)):
            run = run + 1 if v[i] == v[i - 1] and v[i] != -999 else 1
            if run == 3:
                print(f"  FLATLINE {sid} value={v[i]} ending at {g.timestamp.iloc[i]}")

# Is the same sensor present in both batches?
both = set(b1.sensor_id) & set(b2.sensor_id)
print("\nsensors in both batches:", sorted(both))
print("\nmetadata:\n", meta)
