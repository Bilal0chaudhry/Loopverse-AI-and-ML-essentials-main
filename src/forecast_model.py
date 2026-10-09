from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
ROOT = Path(__file__).resolve().parent.parent
HAZARD = 165.0
HORIZON = 10
WEATHER_COLS = ["temp_c", "humidity_pct", "wind_kmh"]
def load():
    df = pd.read_csv(ROOT / "data/clean_daily.csv", parse_dates=["date"])
    w = pd.concat([pd.read_csv(ROOT / "weather/weather_history.csv", parse_dates=["date"]),
                   pd.read_csv(ROOT / "holdout/holdout_weather.csv", parse_dates=["date"])])
    w = w.drop_duplicates("date").sort_values("date").reset_index(drop=True)
    return df, w
def city_series(train: pd.DataFrame) -> pd.Series:
    return train.groupby("date").pm25_filled.mean()
def sensor_factors(train: pd.DataFrame, window: int) -> pd.Series:
    recent = train[train.date > train.date.max() - pd.Timedelta(days=window)]
    city = recent.groupby("date").pm25_filled.mean().rename("city")
    r = recent.merge(city, on="date")
    return r.groupby("sensor_id").pm25_filled.sum() / r.groupby("sensor_id").city.sum()
def _expand(level_by_date: pd.Series, factors: pd.Series) -> pd.DataFrame:
    rows = [(s, d, level_by_date[d] * f) for s, f in factors.items() for d in level_by_date.index]
    return pd.DataFrame(rows, columns=["sensor_id", "date", "pred"])
def m_persistence(train, w, dates):
    last = train[train.date == train.date.max()].set_index("sensor_id").pm25_filled
    return pd.DataFrame([(s, d, v) for s, v in last.items() for d in dates],
                        columns=["sensor_id", "date", "pred"])
def m_sensor_mean7(train, w, dates):
    recent = train[train.date > train.date.max() - pd.Timedelta(days=7)]
    m = recent.groupby("sensor_id").pm25_filled.mean()
    return pd.DataFrame([(s, d, v) for s, v in m.items() for d in dates],
                        columns=["sensor_id", "date", "pred"])
def m_factor_city14(train, w, dates):
    city = city_series(train)
    level = pd.Series(city.iloc[-14:].mean(), index=dates)
    return _expand(level, sensor_factors(train, 60))
def _city_design(dates, t0, w, use_dow, use_weather):
    dates = pd.DatetimeIndex(dates)
    X = pd.DataFrame(index=dates)
    X["t"] = (dates - t0).days.astype(float)
    if use_dow:
        for k in range(6):
            X[f"dow{k}"] = (dates.dayofweek == k).astype(float)
    if use_weather:
        ww = w.set_index("date").reindex(dates)[WEATHER_COLS]
        X = X.join(ww)
    return X
def make_city_ridge(fit_days=70, use_dow=True, use_weather=True, alpha=1.0, factor_window=60):
    def model(train, w, dates):
        city = city_series(train)
        city = city.iloc[-fit_days:]
        t0 = city.index[0]
        X = _city_design(city.index, t0, w, use_dow, use_weather)
        mu, sd = X.mean(), X.std().replace(0, 1)
        reg = Ridge(alpha=alpha).fit((X - mu) / sd, city.values)
        Xf = _city_design(dates, t0, w, use_dow, use_weather)
        level = pd.Series(reg.predict((Xf - mu) / sd), index=dates)
        return _expand(level, sensor_factors(train, factor_window))
    return model
def walk_forward(model, df, w, cutoffs):
    out = []
    for T in cutoffs:
        train = df[df.date <= T]
        assert train.date.max() == T
        dates = pd.date_range(T + pd.Timedelta(days=1), periods=HORIZON)
        p = model(train, w, dates)
        p["cutoff"] = T
        p["h"] = (p.date - T).dt.days
        out.append(p)
    p = pd.concat(out)
    truth = df[["sensor_id", "date", "pm25_observed"]]
    return p.merge(truth, on=["sensor_id", "date"]).dropna(subset=["pm25_observed"])
def alarm_metrics(y, pred, thr):
    yt, yp = y >= HAZARD, pred >= thr
    tp, fp, fn = (yt & yp).sum(), (~yt & yp).sum(), (yt & ~yp).sum()
    rec = tp / max(tp + fn, 1)
    prec = tp / max(tp + fp, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-9)
    return dict(tp=int(tp), fp=int(fp), fn=int(fn), recall=rec, precision=prec, f1=f1)
def score(res):
    e = res.pred - res.pm25_observed
    m = dict(MAE=e.abs().mean(), RMSE=np.sqrt((e ** 2).mean()), bias=e.mean())
    a = alarm_metrics(res.pm25_observed, res.pred, HAZARD)
    m.update({f"alarm165_{k}": v for k, v in a.items() if k in ("recall", "precision", "f1")})
    return m
def default_cutoffs(df, n=12, step=3):
    last = df.date.max() - pd.Timedelta(days=HORIZON)
    return [last - pd.Timedelta(days=step * i) for i in range(n)][::-1]
MODELS = {
    "persistence": m_persistence,
    "sensor_mean7": m_sensor_mean7,
    "factor_x_city14": m_factor_city14,
    "ridge_trend": make_city_ridge(use_dow=False, use_weather=False),
    "ridge_trend_dow": make_city_ridge(use_dow=True, use_weather=False),
    "ridge_trend_wx": make_city_ridge(use_dow=False, use_weather=True),
    "ridge_trend_dow_wx": make_city_ridge(use_dow=True, use_weather=True),
}
if __name__ == "__main__":
    df, w = load()
    cut = default_cutoffs(df)
    print("cutoffs:", cut[0].date(), "->", cut[-1].date(), f"({len(cut)} folds, horizons 1..{HORIZON})")
    rows = {}
    for name, m in MODELS.items():
        rows[name] = score(walk_forward(m, df, w, cut))
    print(pd.DataFrame(rows).T.round(3).sort_values("MAE").to_string())
