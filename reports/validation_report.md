# Walk-forward validation report

- Folds: 12 cutoffs from 2026-09-15 to 2026-10-18 (every 3 days)
- Each fold trains only on dates <= cutoff and predicts cutoff+1 .. cutoff+10 (same 1-10 day horizon as the real holdout, since history ends 2026-10-28).
- Final config: `{'fit_days': 56, 'factor_window': 30, 'alpha': 1.0, 'use_dow': True, 'use_weather': False}`

## Model comparison

|                                |    MAE |   RMSE |   bias |   alarm165_recall |   alarm165_precision |   alarm165_f1 |
|:-------------------------------|-------:|-------:|-------:|------------------:|---------------------:|--------------:|
| FINAL (ridge trend+dow, tuned) | 13.352 | 21.568 | -2.284 |             0     |                0     |         0     |
| ridge_trend_dow                | 13.417 | 21.707 | -2.06  |             0     |                0     |         0     |
| ridge_trend_dow_wx             | 13.491 | 21.712 | -1.818 |             0     |                0     |         0     |
| ridge_trend                    | 14.327 | 22.376 | -2.026 |             0     |                0     |         0     |
| ridge_trend_wx                 | 14.554 | 22.536 | -1.594 |             0     |                0     |         0     |
| factor_x_city14                | 14.836 | 23.332 | -7.26  |             0     |                0     |         0     |
| sensor_mean7                   | 15.654 | 23.739 | -5.156 |             0     |                0     |         0     |
| persistence                    | 22.255 | 33.312 | -2.974 |             0.051 |                0.043 |         0.047 |

## Hazardous alarm threshold sweep (final model)

Validation targets with true PM2.5 >= 165: 59 of 1800.

|   threshold |   tp |   fp |   fn |   recall |   precision |    f1 |
|------------:|-----:|-----:|-----:|---------:|------------:|------:|
|         120 |   36 |  737 |   23 |    0.61  |       0.047 | 0.087 |
|         125 |   27 |  590 |   32 |    0.458 |       0.044 | 0.08  |
|         130 |   21 |  453 |   38 |    0.356 |       0.044 | 0.079 |
|         135 |   18 |  326 |   41 |    0.305 |       0.052 | 0.089 |
|         140 |    8 |  204 |   51 |    0.136 |       0.038 | 0.059 |
|         145 |    4 |  118 |   55 |    0.068 |       0.033 | 0.044 |
|         150 |    4 |   48 |   55 |    0.068 |       0.077 | 0.072 |
|         155 |    2 |   15 |   57 |    0.034 |       0.118 | 0.053 |
|         160 |    0 |    2 |   59 |    0     |       0     | 0     |
|         165 |    0 |    0 |   59 |    0     |       0     | 0     |

Precision stays near the base rate at every threshold: single-day sensor spikes are not predictable from past data (sensor deviation autocorrelation ~0). We therefore apply the SPEC rule directly (`hazardous = predicted_pm25 >= 165`) instead of lowering the threshold, which would add many false alarms for little real recall.

Note: The untuned `ridge_trend_dow` scores almost the same as the final tuned model (13.42 vs 13.35). This shows the gain comes from the weekday pattern, not from tuning.
