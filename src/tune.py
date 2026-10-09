"""Small tuning grid + hazardous-alarm threshold sweep (walk-forward, no holdout labels)."""
import itertools
import pandas as pd
from forecast_model import load, walk_forward, default_cutoffs, make_city_ridge, score, alarm_metrics

df, w = load()
cut = default_cutoffs(df)

rows = []
for fit_days, fw, alpha in itertools.product([42, 56, 70, 90], [30, 60, 119], [0.3, 1.0, 3.0]):
    m = make_city_ridge(fit_days=fit_days, use_dow=True, use_weather=False, alpha=alpha, factor_window=fw)
    s = score(walk_forward(m, df, w, cut))
    rows.append(dict(fit_days=fit_days, factor_window=fw, alpha=alpha, **s))
g = pd.DataFrame(rows).sort_values("MAE")
print(g.head(10)[["fit_days", "factor_window", "alpha", "MAE", "RMSE", "bias"]].round(3).to_string(index=False))

best = g.iloc[0]
m = make_city_ridge(fit_days=int(best.fit_days), use_dow=True, use_weather=False,
                    alpha=best.alpha, factor_window=int(best.factor_window))
res = walk_forward(m, df, w, cut)
print("\nBy horizon (MAE):", res.assign(e=(res.pred - res.pm25_observed).abs()).groupby("h").e.mean().round(1).to_dict())
print(f"\nHazardous days in validation targets: {(res.pm25_observed >= 165).sum()} / {len(res)}")
print("Max prediction:", res.pred.max().round(1))
print("\nAlarm threshold sweep on predicted PM2.5:")
sweep = pd.DataFrame([dict(thr=t, **alarm_metrics(res.pm25_observed, res.pred, t))
                      for t in range(120, 170, 5)])
print(sweep.round(3).to_string(index=False))
