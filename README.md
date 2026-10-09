# Lahore Smog Intelligence Challenge: Team Loopverse

## Setup
```bash
pip install -r requirements.txt
```

## Reproduce everything (from the repo root)
```bash
python src/predict.py                       # clean data -> validate models -> predictions.csv (+ data/forecast_table.csv, reports/validation_report.md)
python src/plots.py                         # audit plots -> reports/audit_plots.png
python tests/test_assistant.py              # 40+ checks for forecast() and ask()
python run_questions.py <questions file>    # answers.json + answers.csv for the released question set
```
Optional: set `GEMINI_API_KEY` (free tier) to let an LLM rephrase answers. Its output is rejected if it changes numbers or citations. Without a key, answers are fully deterministic.

## Sprint 1: forecast
- **Alignment:** batch_1 is PM2.5 in UTC, so +5h to Pakistan time. batch_2 is AQI in Pakistan time, converted to PM2.5 with the pre-2024 US EPA breakpoints. `src/audit_crosscheck.py` shows 99.9% of rows agree once converted.
- **Cleaning:** `-999` becomes missing. batch_2 fills batch_1 gaps (27 days). The S07 flat line (71.8, Aug 25 to 27) is removed. Every value is flagged with its source.
- **Horizon:** data ends 2026-10-28, so the holdout is a 1 to 10 day ahead forecast.
- **Model:** Ridge regression on the city-wide trend plus day-of-week (last 56 days), scaled per sensor by its recent ratio to the city average.
- **Validation:** walk-forward, 12 cutoffs (Sep 15 to Oct 18, every 3 days), always predicting the 10 unseen days after each cutoff.

| Model | MAE (µg/m³) |
|---|---|
| **Final: Ridge trend + weekday** | **13.35** |
| Ridge trend (no weekday) | 14.33 |
| 7-day sensor mean (baseline) | 15.65 |
| Persistence (baseline) | 22.26 |

- **Alarm:** `hazardous = predicted_pm25 >= 165` (SPEC section 3). The threshold sweep in `reports/validation_report.md` shows hazardous spikes can't be predicted from past data (recall 0 at 165), and lowering the threshold mostly adds false alarms.

## Sprint 2: assistant (`src/assistant.py`, `src/rag.py`, `src/forecast_tool.py`)
- `forecast(location, target_date)` follows the SPEC section 5 contract and returns `unavailable` for uncovered places or dates.
- `ask(question)` follows the SPEC section 6 contract. Answers are built from retrieved passages plus the forecast tool, citations are checked against retrieved documents, and `forecast_called` is set by the real tool call.
- Retrieval is BM25 with Roman Urdu normalisation. Superseded documents are excluded; unofficial sources are down-weighted.
- Security: documents are untrusted. Hidden comments and instruction-like lines are stripped at ingest (DOC-07).

## Limitations
- Typical forecast error is about ±13 µg/m³. Single-day hazardous spikes are not predictable from past readings.
- Coverage is the 15 Lahore areas and 2026-10-29 to 2026-11-07 only.
- The reference forecast fallback was not used.
