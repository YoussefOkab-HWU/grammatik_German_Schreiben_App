import json, re

SRC = "./exercises.jsonl"
OUT = "./explanations.jsonl"
BAD_ORDER_OUT = "./bad_order_ids.jsonl"

# words whose relative order is actually checkable against ground truth:
# verbs, the negation "nicht", and separable prefixes -- these are exactly
# the pieces that stack up at the end of a German clause (verb clusters,
# Oberfeldumstellung, negation-before-the-bracket) per the verb-placement
# scenarios this corpus's categories are built from.
CHECKABLE_TYPES = {"verb", "negation_nicht", "verb_prefix"}


def ground_truth_order(ex):
    """True left-to-right surface order of every checkable word (verbs,
    'nicht', separable prefixes), as a list of {word, gap, order} so we can
    compare any two of them by (gap, order)."""
    items = []
    for c in ex["chips"]:
        if c["type"] not in CHECKABLE_TYPES:
            continue
        word = c.get("answer") or c.get("display")
        if not word:
            continue
        items.append({"word": word, "gap": c["correct_gap"], "order": c["order"]})
    return items


# Patterns for claims like "'X' comes/is placed/follows (directly) before/after 'Y'"
# or "places 'X' before/after 'Y'" or "'Y' precedes 'X'" (reversed relation).
ORDER_PATTERNS = [
    (re.compile(r"['\"]?(\w+)['\"]?\s+(?:comes?|is placed|sits?|follows(?!\s+the))\s+(?:directly\s+)?(before|after)\s+(?:the\s+\w+(?:\s+\w+){0,3}\s+)?['\"]?(\w+)['\"]?", re.IGNORECASE), "direct"),
    (re.compile(r"places?\s+(?:the\s+\w+(?:\s+\w+){0,3}\s+)?['\"]?(\w+)['\"]?\s+(before|after)\s+(?:the\s+\w+(?:\s+\w+){0,3}\s+)?['\"]?(\w+)['\"]?", re.IGNORECASE), "direct"),
    (re.compile(r"['\"]?(\w+)['\"]?\s+precedes\s+['\"]?(\w+)['\"]?", re.IGNORECASE), "precedes"),
    (re.compile(r"['\"]?(\w+)['\"]?\s+follows\s+['\"]?(\w+)['\"]?", re.IGNORECASE), "follows"),
    # passive phrasing: "X is followed (directly) by Y" means X comes BEFORE Y --
    # opposite meaning from "X follows Y", and a very common phrasing the model uses
    (re.compile(r"['\"]?(\w+)['\"]?(?:\s*\([^)]{0,30}\))?\s+is\s+followed\s+(?:directly\s+)?by\s+(?:[^'\"\n]{0,80})?['\"](\w+)['\"]", re.IGNORECASE), "is_followed_by"),
]


def extract_order_claims(reason):
    """Returns list of (word1, relation, word2) meaning "word1 <relation> word2"
    where relation is 'before' or 'after', normalized so it always reads
    "word1 is <relation> word2"."""
    claims = []
    for pattern, kind in ORDER_PATTERNS:
        for m in pattern.finditer(reason):
            if kind == "direct":
                w1, rel, w2 = m.group(1), m.group(2).lower(), m.group(3)
                claims.append((w1, rel, w2))
            elif kind == "precedes":
                w1, w2 = m.group(1), m.group(2)
                claims.append((w1, "before", w2))
            elif kind == "follows":
                w1, w2 = m.group(1), m.group(2)
                claims.append((w1, "after", w2))
            elif kind == "is_followed_by":
                w1, w2 = m.group(1), m.group(2)
                claims.append((w1, "before", w2))
    return claims


def check_explanation(ex, chunks):
    truth = ground_truth_order(ex)
    pos_by_word = {}
    for it in truth:
        pos_by_word.setdefault(it["word"].lower(), []).append((it["gap"], it["order"]))

    mistakes = []
    for chunk in chunks:
        claims = extract_order_claims(chunk["reason"])
        for w1, rel, w2 in claims:
            w1_l, w2_l = w1.lower(), w2.lower()
            if w1_l == w2_l:
                continue
            if w1_l not in pos_by_word or w2_l not in pos_by_word:
                continue  # can't verify -- word isn't a checkable chip (or model paraphrased it)
            # use the first occurrence of each word (common case: each appears once)
            p1 = min(pos_by_word[w1_l])
            p2 = min(pos_by_word[w2_l])
            if p1 == p2:
                continue
            actual_rel = "before" if p1 < p2 else "after"
            if actual_rel != rel:
                mistakes.append({
                    "chunk": chunk["chunk"],
                    "reason": chunk["reason"],
                    "claim": f"{w1} {rel} {w2}",
                    "actual": f"{w1} {actual_rel} {w2}",
                })
    return mistakes


def main():
    exercises = {}
    for l in open(SRC):
        ex = json.loads(l)
        exercises[ex["id"]] = ex

    latest = {}
    for l in open(OUT):
        l = l.strip()
        if not l:
            continue
        rec = json.loads(l)
        latest[rec["id"]] = rec

    n_checked = 0
    n_bad = 0
    bad_records = []
    for id_, rec in latest.items():
        chunks = rec.get("chunks")
        if not chunks:
            continue
        n_checked += 1
        ex = exercises[id_]
        mistakes = check_explanation(ex, chunks)
        if mistakes:
            n_bad += 1
            bad_records.append({"id": id_, "mistakes": mistakes})

    bad_records.sort(key=lambda b: b["id"])
    with open(BAD_ORDER_OUT, "w") as f:
        for b in bad_records:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")

    print(f"checked {n_checked} generated explanations")
    print(f"  {n_bad} have at least one verb/negation/prefix order mistake ({n_bad/n_checked*100:.2f}%)" if n_checked else "")
    print(f"wrote {len(bad_records)} flagged exercises to {BAD_ORDER_OUT}")


if __name__ == "__main__":
    main()
