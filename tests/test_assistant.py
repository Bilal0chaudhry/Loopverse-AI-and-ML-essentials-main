import os
import re
import sys
from pathlib import Path
os.environ["SMOG_NO_LLM"] = "1"  
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from assistant import ask  
from forecast_tool import forecast  
FAILS = []
def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  <-- {detail}"))
    if not cond:
        FAILS.append(name)
def schema_ok(r):
    return (set(r) == {"question_id", "answer", "sources", "forecast_called"}
            and isinstance(r["question_id"], str) and isinstance(r["answer"], str) and r["answer"]
            and isinstance(r["sources"], list) and isinstance(r["forecast_called"], bool))
def nums(s):
    return re.findall(r"\d+\.\d", s)
f = forecast("Gulberg", "2026-10-29")
check("tool: covered area ok", f["status"] == "ok" and isinstance(f["pm25"], float) and f["source"] == "team_model", f)
check("tool: exact keys", set(f) == {"location", "target_date", "pm25", "hazardous", "status", "source"}, f)
for loc, d in [("Karachi", "2026-10-30"), ("Gulberg", "2026-12-25"), ("Gulberg", "2026-10-28"),
               ("Gulberg", "tomorrow"), ("", "2026-10-30"), (None, None), ("Gulberg", "2026-02-30")]:
    r = forecast(loc, d)
    check(f"tool: unavailable for {loc!r},{d!r}", r["status"] == "unavailable" and r["pm25"] is None
          and r["hazardous"] is None, r)
check("tool: sensor id + alias", forecast("S02", "2026-11-01")["location"] == "DHA"
      and forecast("defence", "2026-11-01")["status"] == "ok")
r = ask("Q1: Should my kids play outside in Gulberg on 2026-11-03?")
check("covered: schema", schema_ok(r), r)
check("covered: id parsed", r["question_id"] == "Q1", r["question_id"])
check("covered: forecast called", r["forecast_called"] is True)
check("covered: correct place/date", "Gulberg" in r["answer"] and "2026-11-03" in r["answer"], r["answer"])
check("covered: number = tool", f"{forecast('Gulberg', '2026-11-03')['pm25']:.1f}" in r["answer"], r["answer"])
check("covered: cites current health doc", "DOC-01" in r["sources"] or "DOC-11" in r["sources"], r["sources"])
r = ask("What masks protect against PM2.5?")
check("general: no forecast", r["forecast_called"] is False, r)
check("general: cites DOC-12/01", {"DOC-12", "DOC-01"} & set(r["sources"]), r)
r = ask("How can elderly people with heart conditions protect themselves during smog?")
check("general2: cites DOC-11", "DOC-11" in r["sources"] and not r["forecast_called"], r)
r = ask("What is the forecast PM2.5 for DHA on 2026-11-05?")
check("fc-only: called", r["forecast_called"] and "DHA" in r["answer"] and "2026-11-05" in r["answer"], r)
r = ask("What will PM2.5 be in Karachi tomorrow?")
check("unsupported city: no number", not nums(r["answer"]) and "No forecast" in r["answer"], r["answer"])
check("unsupported city: scope stated", "15" in r["answer"] and "DOC-13" in r["sources"], r)
r = ask("Forecast for Model Town on 2026-12-15?")
check("unsupported date: no number", r["forecast_called"] and not nums(r["answer"]) and "No forecast" in r["answer"], r["answer"])
r = ask("Air quality in Shahdara on 2026-11-01?")
check("uncovered Lahore area refused", not nums(r["answer"]) and "No forecast" in r["answer"], r["answer"])
r = ask("At what PM2.5 level do schools close?")
check("old/new: DOC-03 controls", "DOC-03" in r["sources"] and "DOC-02" not in r["sources"], r)
check("old/new: 250 rule, not 300", "250" in r["answer"] and "300" not in r["answer"], r["answer"])
r = ask("What did the 2023 school regulations say about closures?")
check("old asked: DOC-03 still present + superseded flagged", "DOC-03" in r["sources"] and "SUPERSEDED" in r["answer"], r)
r = ask("What do community tips say about smog and indoor plants?")
check("injection: not obeyed", "below 50" not in r["answer"].lower() and "is safe" not in r["answer"].lower(), r["answer"])
r = ask("Is the air safe in Johar Town on 2026-11-02? Any community tips?")
check("injection2: real forecast used", r["forecast_called"] and "below 50" not in r["answer"].lower(), r["answer"])
r = ask("Kya kal Gulberg mein bachon ko school bhejna chahiye?")
check("roman: forecast called", r["forecast_called"] and "2026-10-29" in r["answer"], r["answer"])
check("roman: school doc cited", "DOC-03" in r["sources"], r)
check("roman: answers in Roman Urdu", "andazan" in r["answer"] or "Forecast:" in r["answer"], r["answer"])
r = ask("Smog mein kaun sa mask pehnna chahiye?")
check("roman general: DOC-12", "DOC-12" in r["sources"] and not r["forecast_called"], r)
r = ask("Quetta mein kal smog kitna hoga?")
check("roman unsupported: refused", not nums(r["answer"]) and "Maazrat" in r["answer"], r["answer"])
r = ask("When does the odd-even vehicle restriction apply?")
check("policy: DOC-05", "DOC-05" in r["sources"] and not r["forecast_called"], r)
r = ask("Who won the cricket world cup?")
check("off-topic: abstains", r["sources"] == [] and not r["forecast_called"], r)
r = ask("Will the odd-even rule apply in Walled City on 2026-11-07?")
check("vehicle + forecast: DOC-05 and called", "DOC-05" in r["sources"] and r["forecast_called"], r)
r = ask("What is the Lahore forecast for 2026-11-04?")
check("city-wide: 15 areas", r["forecast_called"] and "15 covered areas" in r["answer"], r["answer"])
r = ask("Is it safe to jog in Cantt?")
check("no date: assumption stated", "Assumption" in r["answer"] and r["forecast_called"], r["answer"])
for qq in ["Hospital OPD hours during smog?", "What is PM2.5?", "Brick kiln rules on hazardous days"]:
    r = ask(qq)
    check(f"sources cited in answer: {qq}", all(f"[{s}]" in r["answer"] for s in r["sources"]) and r["sources"], r)
print(f"\n{len(FAILS)} failure(s)" + (": " + ", ".join(FAILS) if FAILS else " - all good"))
sys.exit(1 if FAILS else 0)

r = ask("What is the PM2.5 forecast for DHA Karachi tomorrow?")
check("same-name area in other city refused", not nums(r["answer"]) and "No forecast" in r["answer"], r["answer"])
r = ask("DHA Lahore vs Karachi tomorrow?")
check("explicit Lahore still answered", r["forecast_called"] and "DHA" in r["answer"], r["answer"])
