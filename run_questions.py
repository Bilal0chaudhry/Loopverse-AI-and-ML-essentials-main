"""Answer the released question set.  Run:  python run_questions.py spec/25_unseen_questions.md
Accepts .md/.txt (lines like "Q1: ...", "1. ...", "| Q1 | ... |"), .csv (id + question columns) or .json.
Writes answers.json and answers.csv. Keeps the official question IDs."""
import csv, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from assistant import ask  # noqa: E402


def load_questions(path):
    p = Path(path)
    if p.suffix == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        data = data.get("questions", data) if isinstance(data, dict) else data
        return [(str(d.get("question_id") or d.get("id")), d.get("question") or d.get("text")) for d in data]
    if p.suffix == ".csv":
        rows = list(csv.DictReader(p.open(encoding="utf-8")))
        id_col = next(c for c in rows[0] if "id" in c.lower())
        q_col = next(c for c in rows[0] if "question" in c.lower() or "text" in c.lower())
        return [(r[id_col].strip(), r[q_col].strip()) for r in rows]
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip().replace("**", "")
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) >= 2 and re.fullmatch(r"Q?\s*-?\d{1,3}", cells[0], re.I):
                out.append((cells[0], max(cells[1:], key=len)))
            continue
        m = re.match(r"^[-*]?\s*(Q\s*-?\s*\d{1,3}|\d{1,3})\s*[:.)\-]\s*(.+)$", s, re.I)
        if m:
            out.append((m.group(1), m.group(2).strip().strip('"')))
    return out


def norm_id(qid):
    qid = re.sub(r"[\s\-_]", "", qid).upper()
    return qid if qid.startswith("Q") else f"Q{qid}"


if __name__ == "__main__":
    questions = load_questions(sys.argv[1])
    print(f"parsed {len(questions)} questions")
    results = []
    for qid, text in questions:
        r = ask(text)
        r["question_id"] = norm_id(qid)      # official ID, not the hash fallback
        results.append(r)
    Path("answers.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    with open("answers.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["question_id", "answer", "sources", "forecast_called"])
        for r in results:
            w.writerow([r["question_id"], r["answer"], ";".join(r["sources"]), r["forecast_called"]])
    print("wrote answers.json and answers.csv")
