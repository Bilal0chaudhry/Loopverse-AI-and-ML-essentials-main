from __future__ import annotations
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
import forecast_tool as ft
import rag
REFERENCE_TODAY = date.fromisoformat(os.getenv("SMOG_TODAY", "2026-10-28"))  
VALIDATION_MAE = 13.4  
HAZARD = 165.0
BAND_SECTION = {"hazardous": r"hazardous range", "unhealthy": r"between 100", "low": r"below 100"}
OTHER_CITIES = [
    "karachi", "islamabad", "quetta", "peshawar", "multan", "faisalabad", "rawalpindi", "gujranwala",
    "sialkot", "hyderabad", "sargodha", "bahawalpur", "sukkur", "kasur", "sheikhupura", "abbottabad",
    "murree", "gujrat", "sahiwal", "okara", "jhelum", "mardan", "larkana", "gwadar", "delhi",
    "new delhi", "amritsar", "mumbai", "dubai", "london", "kabul", "chitral", "swat", "skardu",
]
NON_COVERED_LAHORE = [
    "shahdara", "gulshan-e-ravi", "gulshan e ravi", "wapda town", "valencia", "garden town", "samanabad",
    "ichhra", "mughalpura", "baghbanpura", "sabzazar", "askari", "lake city", "eme", "green town",
    "kot lakhpat", "shalimar", "data darbar", "anarkali", "mall road", "gulberg iii",  
    "paragon city", "dha phase", "state life", "nishtar town", "harbanspura", "chung", "manawan",
]
NON_COVERED_LAHORE.remove("gulberg iii")
NON_COVERED_LAHORE.remove("dha phase")
MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
MONTH_RE = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
TOPICS = {
    "school": (r"school|skool|class(es)?\b|assembl|recess|student|parhai|taleem|college", ["DOC-03"]),
    "vehicle": (r"odd|even|vehicle|car\b|cars\b|gaa?r[iy]|gaadi|gadi|number plate|drive|driving", ["DOC-05"]),
    "construction": (r"construct|brick|kiln|bhatt|burn|industr|factory|demolition|excavat|taamir|tameer|crop residue|kachra|waste", ["DOC-08"]),
    "hospital": (r"hospital|opd|nebuli|emergency|aspatal|haspatal|doctor|clinic", ["DOC-09"]),
    "transport": (r"metro|orange line|public transport|bus\b|park.and.ride|fare|kiraya|commute|safar", ["DOC-10"]),
    "mask": (r"mask|maask|n95|kn95|purifier|hepa|filter|naqab", ["DOC-12", "DOC-01"]),
    "vulnerable": (r"child|kid|bach|pregnan|hamil|hamla|elder|old people|buzurg|asthma|dama|copd|heart|senior|infant|baby|65", ["DOC-11", "DOC-01"]),
    "health": (r"health|safe|outdoor|outside|exercise|jog|run\b|running|walk|sair|bahar|baahar|varzish|warzish|precaution|ehtiya|symptom|cough|khansi|saans|breath|window|khel|sport|play", ["DOC-01"]),
    "sensor": (r"sensor|network|aqi|-999|timezone|utc|flat.?line|data quality|station", ["DOC-06", "DOC-04"]),
    "coverage": (r"coverage|covered|which areas|kaun se ilaq|cities|scope", ["DOC-13"]),
    "community": (r"tip|community|bulletin|resident|neighbo|plant|damp cloth|carpool", ["DOC-07"]),
    "faq": (r"what is pm|pm2\.?5 kya|why .*(smog|worse)|october|december|who issues|alert", ["DOC-04"]),
}
ADVICE_RE = (r"should|can i|can my|can we|safe|advice|advise|precaution|recommend|what to do|kya kar|"
             r"chahiye|bhej|send|go out|jog|run|exercise|walk|play|mask|school|open|close|band|khul|allowed|"
             r"ijazat|odd|even|hospital|guidance|hidayat|tips|protect|bach(ao|ne)|outdoor|outside|bahar|"
             r"restriction|pabandi|rule|policy|kiln|construction|metro|transport|children|kids|elderly|"
             r"pregnan|asthma|tadabeer|ehtiya")
FORECAST_RE = (r"forecast|predict|pm\s?2\.?5|pm25|aqi|air quality|smog level|pollution level|level|"
               r"how bad|kitna|kitni|kaisa|kaisi|hoga|hogi|expected|tomorrow|kal\b|parson|hazardous|"
               r"khatarna+k|reading")
OLD_RE = r"\b(old|older|previous|earlier|former|2023|2025|version 1|v1|purana|purani|pehle|superseded|outdated|last year)\b"
WINDOW_RE = r"week|hafta|hafte|next (few|10|ten) days|coming days|agle (kuch )?din|all (the )?days|whole window"
ROMAN_MARKERS = {"kya", "hai", "hain", "ka", "ki", "ke", "mein", "kal", "aaj", "karna", "chahiye", "nahi",
                 "ko", "se", "aur", "hoga", "hogi", "kitna", "kitni", "bachon", "kaise", "kahan", "kab",
                 "bhejna", "bhejein", "jayein", "jana", "sakte", "sakta", "sakti", "hum", "mujhe", "apne",
                 "wala", "wali", "liye", "raha", "rahi", "kar", "parson", "batao", "bataein", "khatarnak"}
AREA_NAMES = sorted(set(ft.AREA_ALIASES) | {a.lower() for a in ft.covered_areas()}, key=len, reverse=True)
@dataclass
class Ctx:
    question: str
    q: str
    roman: bool
    retrieved: set = field(default_factory=set)
    forecast_called: bool = False
    forecasts: list = field(default_factory=list)
    numbers: set = field(default_factory=set)       
    def call_forecast(self, area: str, d: date | str):
        self.forecast_called = True
        res, reason = ft.forecast_with_reason(area, d.isoformat() if isinstance(d, date) else d)
        self.forecasts.append(res)
        if res["pm25"] is not None:
            self.numbers.add(f"{res['pm25']:.1f}")
        return res, reason
    def chunks(self, doc_id: str, query: str = "", section_has: str | None = None,
               k: int = 3, include_superseded: bool = False) -> list[rag.Hit]:
        hits = rag.retrieve(query or doc_id, k=50, include_superseded=include_superseded,
                            only_docs={doc_id}, doc_boost={doc_id: 0.01})
        if not hits:  
            docs, chunks = rag.load_corpus()
            d = docs[doc_id]
            if not d.is_current and not include_superseded:
                return []
            hits = [rag.Hit(c, d, 0.0) for c in chunks if c.doc_id == doc_id]
        if section_has:
            hits = [h for h in hits if re.search(section_has, h.chunk.section, re.I)]
        hits = hits[:k]
        self.retrieved |= {h.doc.doc_id for h in hits}
        return hits
def _split_id(question: str) -> tuple[str, str]:
    m = re.match(r"^\s*\**\s*(Q[\s\-_]?\d{1,3})\s*\**\s*[:.)\-]\s*(.*)$", question, re.S | re.I)
    if m:
        return re.sub(r"[\s\-_]", "", m.group(1)).upper(), m.group(2).strip()
    return "Q-" + hashlib.sha1(question.encode("utf-8")).hexdigest()[:8], question.strip()
def _is_roman_urdu(q: str) -> bool:
    toks = re.findall(r"[a-z]+", q)
    return sum(t in ROMAN_MARKERS for t in toks) >= 2
def _find_areas(q: str) -> list[str]:
    found, taken = [], [False] * len(q)
    for name in AREA_NAMES:
        for m in re.finditer(rf"(?<![a-z]){re.escape(name)}(?![a-z])", q):
            if any(taken[m.start():m.end()]):
                continue
            for i in range(m.start(), m.end()):
                taken[i] = True
            area = ft.resolve_location(name)
            if area:
                found.append((m.start(), area))
    for m in re.finditer(r"\bs(0[1-9]|1[0-5])\b", q):
        area = ft.resolve_location(m.group(0))
        found.append((m.start(), area))
    out = []
    for _, a in sorted(found):
        if a not in out:
            out.append(a)
    return out
def _find_other_places(q: str) -> list[str]:
    hits = []
    for c in OTHER_CITIES + NON_COVERED_LAHORE:
        if re.search(rf"(?<![a-z]){re.escape(c)}(?![a-z])", q):
            hits.append(c.title())
    return hits
def _find_dates(q: str) -> tuple[list[date], list[str]]:
    found, notes = [], []
    for m in re.finditer(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", q):
        found.append((m.start(), _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))))
    for m in re.finditer(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b", q):  
        found.append((m.start(), _safe_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))))
    for m in re.finditer(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{MONTH_RE}\.?(?:,?\s+(20\d{{2}}))?", q):
        found.append((m.start(), _safe_date(int(m.group(3) or REFERENCE_TODAY.year),
                                            MONTHS[m.group(2)[:3]], int(m.group(1)))))
    for m in re.finditer(rf"\b{MONTH_RE}\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(20\d{{2}}))?", q):
        found.append((m.start(), _safe_date(int(m.group(3) or REFERENCE_TODAY.year),
                                            MONTHS[m.group(1)[:3]], int(m.group(2)))))
    rel = [(r"day after tomorrow|parson|parso\b", 2), (r"\btomorrow\b|\bkal\b|agle din|next day", 1),
           (r"\btoday\b|\baaj\b|tonight", 0)]
    for pat, off in rel:
        m = re.search(pat, q)
        if m:
            d = REFERENCE_TODAY + timedelta(days=off)
            found.append((m.start(), d))
            notes.append(f"'{m.group(0)}' is read relative to the latest available data day "
                         f"({REFERENCE_TODAY.isoformat()}), i.e. {d.isoformat()}")
            break
    for i, wd in enumerate(WEEKDAYS):
        m = re.search(rf"\b{wd}\b", q)
        if m:
            delta = (i - REFERENCE_TODAY.weekday()) % 7 or 7
            d = REFERENCE_TODAY + timedelta(days=delta)
            found.append((m.start(), d))
            notes.append(f"'{wd.title()}' is read as the next {wd.title()} after {REFERENCE_TODAY.isoformat()}, "
                         f"i.e. {d.isoformat()}")
    out = []
    for _, d in sorted(found, key=lambda x: x[0]):
        if d not in out:
            out.append(d)
    return out, notes
def _safe_date(y, m, d):
    try:
        return date(y, m, d)
    except ValueError:
        return f"{y:04d}-{m:02d}-{d:02d}"  
def _topics(q: str) -> list[str]:
    return [t for t, (pat, _) in TOPICS.items() if re.search(pat, q)]
def _bullet(h: rag.Hit, label_section=True) -> str:
    txt = h.chunk.text.strip()
    sec = h.chunk.section
    if label_section and sec and sec != h.doc.title and not sec.lower().startswith(h.doc.title.lower()[:20])            and len(sec) < 40:
        txt = f"{sec}: {txt}"
    return f"- {txt} [{h.doc.doc_id}]"
def _doc_header(d: rag.Doc) -> str:
    status = "current" if d.is_current else f"SUPERSEDED by {d.superseded_by}"
    note = " - unofficial community tips, not official guidance" if not d.is_official else ""
    return f"{d.doc_id} \"{d.title}\" ({d.authority}, {d.published_date}, {status}{note})"
def _band(pm: float) -> str:
    return "hazardous" if pm >= HAZARD else ("unhealthy" if pm >= 100 else "low")
def _window_text() -> str:
    w = ft.supported_window()
    return f"{w[0]} to {w[1]}" if w else "no dates (forecast table missing)"
def _forecast_sentence(ctx: Ctx, res: dict, reason: str) -> str:
    area, d = res["location"], res["target_date"]
    if res["status"] != "ok":
        ctx.chunks("DOC-13", "dates outside the supported forecast window out of scope", k=2)
        if ctx.roman:
            return (f"{area} ke liye {d} ka koi forecast dastyab nahi ({reason}). Hum andaza nahi lagate. "
                    f"Yeh system sirf Lahore ke 15 covered ilaqon aur {_window_text()} ki tareekhon ke liye hai [DOC-13].")
        return (f"No forecast is available for {area} on {d} ({reason}). I will not estimate a number. "
                f"Coverage is limited to the 15 named Lahore areas and target dates {_window_text()} [DOC-13].")
    sid = ft.area_to_sensor(res["location"])
    pm, hz = res["pm25"], res["hazardous"]
    prov = "team forecast model" if res["source"] == "team_model" else "organisers' reference forecast"
    if ctx.roman:
        status = ("yeh KHATARNAK (hazardous) satah hai, yani 165 µg/m³ ya us se zyada" if hz else
                  "yeh hazardous had (165 µg/m³) se kam hai")
        return f"Forecast: {area} (sensor {sid}) mein {d} ko andazan PM2.5 {pm:.1f} µg/m³ hai - {status}. (Source: {prov})"
    status = "HAZARDOUS (at or above the 165 µg/m³ threshold)" if hz else "not hazardous (below the 165 µg/m³ threshold)"
    return f"Forecast: {area} (sensor {sid}) on {d}: predicted daily PM2.5 {pm:.1f} µg/m³ - {status}. (Source: {prov})"
def _guidance_for_forecast(ctx: Ctx, res: dict, topics: list[str], area: str) -> list[str]:
    pm, d = res["pm25"], res["target_date"]
    band = _band(pm)
    out = []
    t = set(topics) or {"health"}
    if "school" in t:
        hits = ctx.chunks("DOC-03", "schools half-day close fully outdoor sports decisions evening before", k=6)
        if pm >= 250:
            dec = "full school closure"
        elif pm >= HAZARD:
            dec = "half-day timing (close by 12:00 PM) and suspension of outdoor sports, assemblies and recess"
        else:
            dec = "no half-day timing or closure, because the forecast is below the 165 µg/m³ trigger"
        out.append(f"School rule for this forecast: {dec} [DOC-03].")
        out += [_bullet(h, False) for h in hits if re.search(r"half-day|close fully|evening before|outdoor sports", h.chunk.text)]
    if "vehicle" in t:
        base = date.fromisoformat(d)
        neigh = {}
        for off in (-1, 1):
            r2, _ = ctx.call_forecast(area, base + timedelta(days=off))
            neigh[off] = r2["hazardous"] if r2["status"] == "ok" else None
        consecutive = res["hazardous"] and (neigh[-1] or neigh[1])
        hits = ctx.chunks("DOC-05", "odd even hazardous two consecutive days exemptions lifted", k=6)
        if consecutive:
            out.append("Odd-even rule: this day is forecast hazardous together with an adjacent day, so the "
                       "two-consecutive-day trigger for the odd-even restriction is met [DOC-05].")
        else:
            out.append("Odd-even rule: the restriction needs hazardous forecasts (165 µg/m³ or above) on two or more "
                       "consecutive days; that trigger is not met by this forecast [DOC-05].")
        out += [_bullet(h, False) for h in hits[:3]]
    if "construction" in t:
        hits = ctx.chunks("DOC-08", "open burning construction brick kilns industries hazardous", k=5)
        if res["hazardous"]:
            out.append("Because the forecast is hazardous, these restrictions apply [DOC-08]:")
            out += [_bullet(h, False) for h in hits[:4]]
        else:
            out.append("The construction/industrial restrictions apply only when forecast PM2.5 reaches 165 µg/m³ or above, "
                       "so they are not triggered by this forecast [DOC-08].")
    if "transport" in t:
        hits = ctx.chunks("DOC-10", "metrobus orange line frequency fares park-and-ride", k=4)
        out.append(("Hazardous-day public transport measures [DOC-10]:" if res["hazardous"]
                    else "Public transport smog measures (frequency increase applies on forecast hazardous days) [DOC-10]:"))
        out += [_bullet(h, False) for h in hits[:3]]
    if "hospital" in t:
        hits = ctx.chunks("DOC-09", "extended opd nebulization emergency chest pain", k=4)
        out += [_bullet(h, False) for h in hits[:3]]
    if "mask" in t:
        hits = ctx.chunks("DOC-12", "n95 kn95 masks 15 minutes hepa purifier", k=5)
        out += [_bullet(h, False) for h in hits[:3]]
    if "vulnerable" in t and band == "hazardous":
        q = ctx.q
        groups = []
        if re.search(r"child|kid|bach|infant|baby|student", q): groups.append("Children")
        if re.search(r"elder|old people|buzurg|senior|65", q): groups.append("Elderly")
        if re.search(r"pregnan|hamil|hamla", q): groups.append("Pregnant")
        if re.search(r"asthma|dama|copd", q): groups.append("asthma")
        for g in groups or ["Children", "Elderly"]:
            out += [_bullet(h) for h in ctx.chunks("DOC-11", ctx.q, section_has=g, k=2)]
    if "community" in t:
        hits = ctx.chunks("DOC-07", ctx.q + " tips", k=3)
        if hits:
            out.append("Community tips (unofficial resident association, not official guidance) [DOC-07]:")
            out += [_bullet(h, False) for h in hits]
    if t & {"health", "vulnerable", "mask"} or not (t & {"school", "vehicle", "construction", "transport", "hospital", "community"}):
        sec = BAND_SECTION[band]
        hits = ctx.chunks("DOC-01", ctx.q + " outdoor masks windows sensitive groups", section_has=sec, k=4)
        label = {"hazardous": "Health advice for a hazardous day",
                 "unhealthy": "Health advice for PM2.5 in the 100-164 µg/m³ range",
                 "low": "Health advice for PM2.5 below 100 µg/m³"}[band]
        out.append(f"{label} [DOC-01]:")
        out += [_bullet(h, False) for h in hits]
    return out
def _doc_answer(ctx: Ctx, topics: list[str], asks_old: bool) -> list[str]:
    boost = {}
    for t in topics:
        for i, did in enumerate(TOPICS[t][1]):
            boost[did] = max(boost.get(did, 0), 2.0 - 0.5 * i)
    hits = rag.retrieve(ctx.question, k=12, include_superseded=asks_old, doc_boost=boost)
    if not hits or hits[0].score < 1.5:
        return []
    top = hits[0].score
    hits = [h for h in hits if h.score >= 0.4 * top]
    by_doc: dict[str, list[rag.Hit]] = {}
    for h in hits:
        by_doc.setdefault(h.doc.doc_id, []).append(h)
    for did in list(by_doc):
        d = by_doc[did][0].doc
        if not d.is_current and d.superseded_by:
            repl = ctx.chunks(d.superseded_by, ctx.question, k=4)
            if repl:
                by_doc = {d.superseded_by: repl, **{k: v for k, v in by_doc.items() if k != d.superseded_by}}
    order = sorted(by_doc, key=lambda k: (not by_doc[k][0].doc.is_official, -max(h.score for h in by_doc[k])))
    if any(by_doc[k][0].doc.is_official for k in order):
        order = [k for k in order if by_doc[k][0].doc.is_official or len(order) == 1]
    order = [k for k in order if by_doc[k][0].doc.is_current][:3]
    old_docs = []
    if asks_old:
        docs, _ = rag.load_corpus()
        for k in order:
            old = docs[k].supersedes
            if old and old in docs:
                hits_old = ctx.chunks(old, ctx.question, k=3, include_superseded=True)
                if hits_old:
                    old_docs.append((old, hits_old))
    lines = []
    for did in order:
        d = by_doc[did][0].doc
        ctx.retrieved.add(did)
        lines.append(f"From {_doc_header(d)}:")
        lines += [_bullet(h) for h in by_doc[did][:4]]
    for did, hits_old in old_docs:
        d = hits_old[0].doc
        lines.append(f"Note: {did} is SUPERSEDED by {d.superseded_by} and must not be used for current decisions; "
                     f"{d.superseded_by} above controls. For reference only, the old version said:")
        lines += [_bullet(h) for h in hits_old]
    return lines
def ask(question: str) -> dict:
    qid, text = _split_id(question)
    ctx = Ctx(question=text, q=text.lower(), roman=_is_roman_urdu(text.lower()))
    q = ctx.q
    areas = _find_areas(q)
    others = _find_other_places(q)
    dates, date_notes = _find_dates(q)
    topics = _topics(q)
    asks_old = bool(re.search(OLD_RE, q))
    advice = bool(re.search(ADVICE_RE, q))
    wants_forecast = bool(re.search(FORECAST_RE, q)) or bool(dates)
    mentions_lahore = bool(re.search(r"\blahore\b", q))
    parts: list[str] = []
    for place in others:
        ctx.chunks("DOC-13", "other cities out of scope no forecast available", k=2)
        if ctx.roman:
            parts.append(f"Maazrat, {place} ke liye koi forecast dastyab nahi. Yeh system sirf Lahore ke 15 ilaqon "
                         f"({', '.join(ft.covered_areas())}) aur {_window_text()} ki tareekhon ko cover karta hai, "
                         f"is liye hum andaza nahi lagayenge [DOC-13].")
        else:
            parts.append(f"No forecast is available for {place}: this system covers only 15 Lahore areas "
                         f"({', '.join(ft.covered_areas())}) and target dates {_window_text()}, so I will not "
                         f"estimate a number [DOC-13].")
    if others and not mentions_lahore:
        areas = []  # "DHA Karachi", "Gulberg Islamabad": same names exist in other cities, never guess
    if others and not areas:
        if advice and topics and not wants_forecast:
            parts.append("The supplied policy documents apply to Punjab/Lahore and may not reflect rules elsewhere [DOC-13].")
        return _finish(qid, ctx, parts, date_notes=[])
    fc_dates = [d for d in dates] or ([REFERENCE_TODAY + timedelta(days=1)] if (areas or mentions_lahore) else [])
    if dates and not areas and not others:
        mentions_lahore = True  # system covers Lahore only: "safe tomorrow?" -> Lahore-wide summary
    if not dates and (areas or mentions_lahore) and (wants_forecast or advice):
        if re.search(WINDOW_RE, q):
            lo, hi = ft.supported_window()
            fc_dates = [date.fromisoformat(lo) + timedelta(days=i)
                        for i in range((date.fromisoformat(hi) - date.fromisoformat(lo)).days + 1)]
        else:
            date_notes.append(f"No date was given, so I used the next forecast day, {fc_dates[0].isoformat()} "
                              f"(the day after the latest available data, {REFERENCE_TODAY.isoformat()})")
    doc_only = not areas and not (mentions_lahore and wants_forecast and (dates or not topics))
    if areas and (wants_forecast or advice or dates):
        multi = len(fc_dates) > 3
        for area in areas:
            for d in fc_dates:
                res, reason = ctx.call_forecast(area, d)
                parts.append(_forecast_sentence(ctx, res, reason))
                if res["status"] == "ok" and advice and not multi:
                    parts += _guidance_for_forecast(ctx, res, topics, area)
        if any(f["status"] == "ok" for f in ctx.forecasts) and re.search(r"\baqi\b", q):
            ctx.chunks("DOC-04", "difference between PM2.5 and AQI", k=1)
            parts.append("Note: the forecast is PM2.5 concentration in µg/m³, not AQI; the two are not "
                         "numerically interchangeable [DOC-04].")
        if any(f["status"] == "ok" for f in ctx.forecasts):
            parts.append(f"Limitation: this is a statistical forecast of the daily average; in back-testing its typical "
                         f"error was about ±{VALIDATION_MAE:.0f} µg/m³ and single-day spikes are hard to predict.")
            ctx.numbers.add(f"{VALIDATION_MAE:.0f}")
    elif not areas and mentions_lahore and wants_forecast and not doc_only:
        for d in fc_dates[:3]:
            rows = [ctx.call_forecast(a, d) for a in ft.covered_areas()]
            ok = [r for r, _ in rows if r["status"] == "ok"]
            if not ok:
                parts.append(_forecast_sentence(ctx, rows[0][0] | {"location": "Lahore"}, rows[0][1]))
                continue
            lo_r = min(ok, key=lambda r: r["pm25"]); hi_r = max(ok, key=lambda r: r["pm25"])
            avg = sum(r["pm25"] for r in ok) / len(ok)
            ctx.numbers.add(f"{avg:.1f}")
            hz = [r["location"] for r in ok if r["hazardous"]]
            parts.append(f"Lahore forecast for {d.isoformat() if isinstance(d, date) else d} across the 15 covered areas: "
                         f"lowest {lo_r['pm25']:.1f} µg/m³ ({lo_r['location']}), highest {hi_r['pm25']:.1f} µg/m³ "
                         f"({hi_r['location']}), average {avg:.1f} µg/m³. Hazardous (>=165): "
                         f"{', '.join(hz) if hz else 'none'}. (Source: team forecast model)")
            if advice:
                parts += _guidance_for_forecast(ctx, hi_r, topics, hi_r["location"])
        parts.append("Ask about a specific area (e.g. Gulberg, DHA) for an area-level forecast.")
    if doc_only:
        doc_lines = _doc_answer(ctx, topics, asks_old)
        if doc_lines:
            if ctx.roman:
                parts.append("Official documents ke mutabiq (quotes English mein):")
            parts += doc_lines
            if dates and not areas and (wants_forecast or "school" in topics):
                parts.append("For an area-specific decision, ask about one of the 15 covered Lahore areas with a date "
                             f"between {_window_text()}.")
        elif not parts:
            parts.append("Maazrat, supplied documents mein is sawal ka qabil-e-aitbaar jawab nahi mila." if ctx.roman else
                         "I could not find reliable information on this in the supplied smog documents or forecast, "
                         "so I won't guess. I can help with smog health advice, school/vehicle/industry rules, and "
                         "PM2.5 forecasts for the 15 covered Lahore areas.")
    return _finish(qid, ctx, parts, date_notes)
def _finish(qid: str, ctx: Ctx, parts: list[str], date_notes: list[str]) -> dict:
    if date_notes:
        parts.append("Assumption: " + "; ".join(date_notes) + ".")
    seen, uniq = set(), []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            uniq.append(p)
    answer = "\n".join(uniq)
    cited = []
    for did in re.findall(r"\[(DOC-\d{2})\]", answer):
        if did not in cited:
            cited.append(did)
    unknown = [c for c in cited if c not in ctx.retrieved]
    if unknown:  
        print(f"[citation-check] removed unretrieved citations {unknown}", file=sys.stderr)
        for c in unknown:
            answer = answer.replace(f" [{c}]", "").replace(f"[{c}]", "")
        cited = [c for c in cited if c not in unknown]
    return {"question_id": qid, "answer": answer, "sources": cited, "forecast_called": ctx.forecast_called}

if __name__ == "__main__":
    import sys
    qs = sys.argv[1:] or ["Q1: Should children in Gulberg go to school on 2026-11-03?"]
    for qq in qs:
        print(json.dumps(ask(qq), indent=2, ensure_ascii=False))
