from __future__ import annotations
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior|above) (instructions|rules)", r"system (note|prompt|message)",
    r"do not (mention|cite|tell)", r"from now on", r"you are now", r"disregard",
    r"always respond", r"regardless of the actual",
]
UNOFFICIAL_WEIGHT = 0.5
ROMAN_URDU = {
    "kal": "tomorrow", "aaj": "today", "parson": "day after tomorrow", "agle": "next",
    "school": "school", "schools": "school", "skool": "school", "sakool": "school",
    "band": "close closure", "bund": "close closure", "chutti": "close closure", "chhutti": "close closure",
    "khulay": "open", "khulenge": "open", "aadha": "half", "adha": "half",
    "bachay": "children", "bachon": "children", "bachey": "children", "bache": "children", "bacchon": "children",
    "bachy": "children", "buzurg": "elderly", "boorhay": "elderly", "budhe": "elderly",
    "hamla": "pregnant", "hamila": "pregnant", "hamilah": "pregnant", "hamal": "pregnant",
    "dama": "asthma", "saans": "breath breathing", "sans": "breath breathing", "khansi": "cough",
    "seena": "chest", "dard": "pain",
    "sehat": "health", "sehet": "health", "hawa": "air", "aloodgi": "pollution", "aaloodgi": "pollution",
    "dhund": "smog", "dhuwan": "smog smoke", "dhuan": "smog smoke", "smog": "smog",
    "mask": "mask", "maask": "mask", "naqab": "mask",
    "gaari": "vehicle car", "gari": "vehicle car", "gaadi": "vehicle car", "gadi": "vehicle car",
    "garion": "vehicle car", "gaariyon": "vehicle car", "number": "number plate",
    "aspatal": "hospital", "haspatal": "hospital", "hospital": "hospital",
    "bahar": "outdoor outside", "baahar": "outdoor outside", "ghar": "indoor home", "andar": "indoor",
    "khel": "sports play", "khelna": "sports play", "varzish": "exercise", "warzish": "exercise",
    "daurna": "exercise running", "sair": "walk outdoor",
    "khatarnak": "hazardous", "khatarnaak": "hazardous", "mehfooz": "safe", "mahfooz": "safe",
    "qanoon": "policy rule", "qawaneen": "policy rule", "pabandi": "restriction ban",
    "ijazat": "allowed", "bhatta": "brick kiln", "bhattay": "brick kiln", "jalana": "burning",
    "fasal": "crop", "kachra": "waste", "taamir": "construction", "tameer": "construction",
    "dawai": "medication", "dawa": "medication", "safar": "travel transport",
    "metro": "metrobus metro", "kiraya": "fare", "tadabeer": "precautions",
    "ehtiyat": "precautions", "ehtiyaat": "precautions", "hidayat": "guidance advice",
    "elaqa": "area", "ilaqa": "area", "ilaqe": "area", "shehar": "city",
}
STOPWORDS = set("""a an the is are was were be been being am do does did of in on at to for from by with
and or but if then than that this these those it its as into about over under up down out what which who
whom whose when where why how can could should would will shall may might must i me my we our you your he
she they them their there here please tell kya hai hain ka ki ke ko se mein me main aur ya bhi hi to tha
thi the hoga hogi honge karna karein chahiye kar raha rahi kaise kaisa kitna kitni kab kahan jab nahi na
""".split())
@dataclass
class Doc:
    doc_id: str
    title: str
    authority: str
    published_date: str
    status: str
    supersedes: str | None
    superseded_by: str | None
    body: str
    security_flags: list[str] = field(default_factory=list)
    @property
    def is_current(self) -> bool:
        return self.status.lower() == "current"
    @property
    def is_official(self) -> bool:
        return "unofficial" not in self.authority.lower()
@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    section: str
    text: str
    tokens: list[str]
def tokenize(text: str) -> list[str]:
    raw = re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", text.lower().replace("pm2.5", "pm25"))
    out = []
    for t in raw:
        out.extend(ROMAN_URDU.get(t, t).split())
    norm = []
    for t in out:
        if t in STOPWORDS:
            continue
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        norm.append(t)
    return norm
def _parse_front_matter(raw: str) -> tuple[dict, str]:
    m = re.search(r"^---\s*\n(.*?)\n---\s*\n", raw, re.S | re.M)
    if not m:
        return {}, raw
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    body = (raw[:m.start()] + "\n" + raw[m.end():]).strip()
    return meta, body
def sanitize(body: str) -> tuple[str, list[str]]:
    flags = []
    if re.search(r"<!--.*?-->", body, re.S):
        flags.append("hidden HTML comment removed")
        body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    kept = []
    for line in body.splitlines():
        if any(re.search(p, line, re.I) for p in INJECTION_PATTERNS):
            flags.append(f"instruction-like line removed: {line.strip()[:80]}")
            continue
        kept.append(line)
    return "\n".join(kept), flags
def _chunks_for(doc: Doc) -> list[Chunk]:
    chunks, section, para = [], doc.title, []
    def emit(text):
        text = re.sub(r"\*\*|__|`", "", text).strip()
        if len(text) < 15:
            return
        cid = f"{doc.doc_id}#{len(chunks) + 1}"
        chunks.append(Chunk(cid, doc.doc_id, section, text,
                            tokenize(f"{doc.title} {section} {text}")))
    for line in doc.body.splitlines():
        s = line.strip()
        if not s:
            if para:
                emit(" ".join(para)); para = []
            continue
        if s.startswith("#"):
            if para:
                emit(" ".join(para)); para = []
            section = s.lstrip("#").strip()
            continue
        if re.fullmatch(r"\*\*[^*]+\*\*", s) and len(s) < 60:   
            if para:
                emit(" ".join(para)); para = []
            section = s.strip("*").strip()
            continue
        if s.endswith(":") and not s.startswith(("- ", "* ")):     
            if para:
                emit(" ".join(para)); para = []
            section = re.sub(r"\*\*", "", s[:-1]).strip()
            continue
        if s.startswith(("- ", "* ")):
            if para:
                emit(" ".join(para)); para = []
            emit(s[2:])
            continue
        para.append(s.lstrip("> "))
    if para:
        emit(" ".join(para))
    return chunks
@lru_cache(maxsize=1)
def load_corpus() -> tuple[dict[str, Doc], list[Chunk]]:
    docs, chunks = {}, []
    for path in sorted(DOCS_DIR.glob("DOC-*.md")):
        raw = path.read_text(encoding="utf-8", errors="replace")
        meta, body = _parse_front_matter(raw)
        body, flags = sanitize(body)
        doc = Doc(
            doc_id=meta.get("document_id", path.stem[:6]),
            title=meta.get("title", path.stem),
            authority=meta.get("authority", "unknown"),
            published_date=meta.get("published_date", ""),
            status=meta.get("status", "unknown"),
            supersedes=meta.get("supersedes"),
            superseded_by=meta.get("superseded_by"),
            body=body,
            security_flags=flags,
        )
        docs[doc.doc_id] = doc
        chunks.extend(_chunks_for(doc))
    for d in docs.values():
        if d.supersedes and d.supersedes in docs:
            old = docs[d.supersedes]
            old.status, old.superseded_by = "superseded", d.doc_id
    return docs, chunks
class BM25:
    def __init__(self, chunks: list[Chunk], k1=1.4, b=0.75):
        self.chunks, self.k1, self.b = chunks, k1, b
        self.tf = [Counter(c.tokens) for c in chunks]
        self.len = [len(c.tokens) for c in chunks]
        self.avg = sum(self.len) / len(self.len)
        df = Counter(t for c in chunks for t in set(c.tokens))
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
    def score(self, q_tokens: list[str], i: int) -> float:
        s, tf, dl = 0.0, self.tf[i], self.len[i]
        for t in set(q_tokens):
            if t in tf:
                f = tf[t]
                s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avg))
        return s
@lru_cache(maxsize=1)
def _index() -> BM25:
    return BM25(load_corpus()[1])
@dataclass
class Hit:
    chunk: Chunk
    doc: Doc
    score: float
def retrieve(query: str, k: int = 8, include_superseded: bool = False,
             doc_boost: dict[str, float] | None = None, only_docs: set[str] | None = None) -> list[Hit]:
    docs, chunks = load_corpus()
    idx = _index()
    q = tokenize(query)
    doc_boost = doc_boost or {}
    hits = []
    for i, c in enumerate(chunks):
        d = docs[c.doc_id]
        if only_docs is not None and c.doc_id not in only_docs:
            continue
        if not d.is_current and not include_superseded:
            continue
        s = idx.score(q, i)
        s *= (1.0 if d.is_official else UNOFFICIAL_WEIGHT)
        s += doc_boost.get(c.doc_id, 0.0) * (1 if s > 0 else 0.5)
        if s > 0:
            hits.append(Hit(c, d, s))
    hits.sort(key=lambda h: (-h.score, h.doc.published_date))
    return hits[:k]
if __name__ == "__main__":
    docs, chunks = load_corpus()
    print(f"{len(docs)} docs, {len(chunks)} chunks")
    for d in docs.values():
        print(f"  {d.doc_id} [{d.status}{' -> ' + d.superseded_by if d.superseded_by else ''}] "
              f"{d.published_date} {d.authority[:40]} flags={d.security_flags}")
    for q in ["When do schools close because of smog?", "kya bachon ko school bhejna chahiye?",
              "Which mask should I wear?", "odd even gaari pabandi"]:
        print("\nQ:", q)
        for h in retrieve(q, k=4):
            print(f"  {h.score:5.2f} {h.chunk.chunk_id:8} {h.chunk.text[:90]}")
