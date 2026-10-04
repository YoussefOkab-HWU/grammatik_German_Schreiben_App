import json, re, sys

SRC = "./exercises.jsonl"
EXPL_JS = "./explanations.js"
BAD_ORDER_OUT = "./bad_order_v2_ids.jsonl"

CHECKABLE_TYPES = {"verb", "negation_nicht", "verb_prefix"}

ORDER_PATTERNS = [
    (re.compile(r"['\"]?(\w+)['\"]?\s+(?:comes?|is placed|sits?|follows(?!\s+the))\s+(?:directly\s+)?(before|after)\s+(?:the\s+\w+(?:\s+\w+){0,3}\s+)?['\"]?(\w+)['\"]?", re.IGNORECASE), "direct"),
    (re.compile(r"places?\s+(?:the\s+\w+(?:\s+\w+){0,3}\s+)?['\"]?(\w+)['\"]?\s+(before|after)\s+(?:the\s+\w+(?:\s+\w+){0,3}\s+)?['\"]?(\w+)['\"]?", re.IGNORECASE), "direct"),
    (re.compile(r"['\"]?(\w+)['\"]?\s+precedes\s+['\"]?(\w+)['\"]?", re.IGNORECASE), "precedes"),
    (re.compile(r"['\"]?(\w+)['\"]?\s+follows\s+['\"]?(\w+)['\"]?", re.IGNORECASE), "follows"),
    (re.compile(r"['\"]?(\w+)['\"]?(?:\s*\([^)]{0,30}\))?\s+is\s+followed\s+(?:directly\s+)?by\s+(?:[^'\"\n]{0,80})?['\"](\w+)['\"]", re.IGNORECASE), "is_followed_by"),
]

# NEW: catches "'X' ... (before|after) the (subject|object|verb)" where the
# second referent is a generic role-word, not a specific quoted/named word --
# the exact pattern that let "'nicht' comes after the verb and before the
# object" slip through undetected (v1 doesn't track noun_phrase words at all,
# so even a NAMED noun wouldn't have been checkable, let alone a placeholder).
GENERIC_ROLE_PATTERN = re.compile(
    r"['\"]?(\w+)['\"]?\s+(?:comes?|is placed|sits?|follows(?!\s+the))\s+(?:directly\s+)?(before|after)\s+the\s+(subject|object|verb)\b",
    re.IGNORECASE)

# compound form: "'X' comes after the verb and before the object" -- the
# second half has no explicit word1 of its own, it's implied by "and"
# continuing the same clause, so this must be captured as one combined match
COMPOUND_ROLE_PATTERN = re.compile(
    r"['\"]?(\w+)['\"]?\s+(?:comes?|is placed|sits?)\s+(before|after)\s+the\s+(subject|object|verb)"
    r"(?:\s+\w+){0,2}\s+and\s+(before|after)\s+the\s+(subject|object|verb)\b",
    re.IGNORECASE)

ROLE_WORDS = {"subject", "object", "verb"}


SUBJECT_PRONOUNS = {"ich", "du", "er", "sie", "es", "wir", "ihr", "man"}


def ground_truth_positions(ex):
    """word(lowercased) -> list of (gap, order) -- now includes noun_phrase
    nouns (keyed by the noun itself) in addition to verb/nicht/prefix, so
    claims naming an actual object noun are checkable too. role_candidates
    lists ALL candidates per gap (not just the first found) so callers can
    pick the one NEAREST a given position -- some gaps span multiple clauses
    (main + subordinate crammed into one gap), so "first Nom noun in the
    gap" can silently grab an unrelated subordinate clause's subject."""
    pos_by_word = {}
    role_candidates = {}  # gap -> {"subject": [chips], "object": [chips], "verb": [chips]}
    for c in ex["chips"]:
        word = None
        if c["type"] in CHECKABLE_TYPES:
            word = c.get("answer") or c.get("display")
        elif c["type"] == "noun_phrase" and c.get("noun"):
            word = c["noun"]
        if word:
            pos_by_word.setdefault(word.lower(), []).append((c["correct_gap"], c["order"]))

        gap = c["correct_gap"]
        role_candidates.setdefault(gap, {"subject": [], "object": [], "verb": []})
        if c["type"] == "verb":
            role_candidates[gap]["verb"].append(c)
        elif c["type"] == "noun_phrase" and c.get("article"):
            case = c["article"].get("case")
            if case == "Nom":
                role_candidates[gap]["subject"].append(c)
            elif case == "Acc":
                role_candidates[gap]["object"].append(c)
        elif c["type"] == "bare_noun" and c.get("answer", "").lower() in SUBJECT_PRONOUNS:
            # pronoun subjects (Wir/Ich/Du/Er/Sie/Es) aren't noun_phrase
            # chips but are overwhelmingly the actual grammatical subject
            role_candidates[gap]["subject"].append(c)
    return pos_by_word, role_candidates


def nearest_role_chip(candidates, ref_order):
    """Among same-gap role candidates, pick the one closest in position to
    ref_order -- avoids grabbing a role-chip from an unrelated clause that
    happens to share the same gap."""
    if not candidates:
        return None
    return min(candidates, key=lambda c: abs(c["order"] - ref_order))


def extract_order_claims(reason):
    claims = []
    for pattern, kind in ORDER_PATTERNS:
        for m in pattern.finditer(reason):
            if kind == "direct":
                w1, rel, w2 = m.group(1), m.group(2).lower(), m.group(3)
                if w2.lower() in ROLE_WORDS:
                    continue  # handled separately below with role resolution
                claims.append(("word", w1, rel, w2))
            elif kind == "precedes":
                w1, w2 = m.group(1), m.group(2)
                claims.append(("word", w1, "before", w2))
            elif kind == "follows":
                w1, w2 = m.group(1), m.group(2)
                claims.append(("word", w1, "after", w2))
            elif kind == "is_followed_by":
                w1, w2 = m.group(1), m.group(2)
                claims.append(("word", w1, "before", w2))
    compound_spans = []
    for m in COMPOUND_ROLE_PATTERN.finditer(reason):
        w1, rel1, role1, rel2, role2 = m.group(1), m.group(2).lower(), m.group(3).lower(), m.group(4).lower(), m.group(5).lower()
        claims.append(("role", w1, rel1, role1))
        claims.append(("role", w1, rel2, role2))
        compound_spans.append(m.span())

    for m in GENERIC_ROLE_PATTERN.finditer(reason):
        if any(s <= m.start() < e for s, e in compound_spans):
            continue  # already captured by the compound pattern above
        w1, rel, role = m.group(1), m.group(2).lower(), m.group(3).lower()
        claims.append(("role", w1, rel, role))
    return claims


def check_explanation(ex, chunks):
    pos_by_word, role_candidates = ground_truth_positions(ex)
    mistakes = []
    for chunk in chunks:
        claims = extract_order_claims(chunk["reason"])
        for kind, w1, rel, w2 in claims:
            w1_l = w1.lower()
            if w1_l not in pos_by_word:
                continue
            p1 = min(pos_by_word[w1_l])

            if kind == "word":
                w2_l = w2.lower()
                if w1_l == w2_l or w2_l not in pos_by_word:
                    continue
                p2 = min(pos_by_word[w2_l])
            else:  # role
                gap = p1[0]
                candidates = role_candidates.get(gap, {}).get(w2, [])
                role_chip = nearest_role_chip(candidates, p1[1])
                if not role_chip:
                    continue
                role_word = (role_chip.get("noun") or role_chip.get("answer") or role_chip.get("display") or "").lower()
                if role_word == w1_l:
                    continue  # claim is about itself (e.g. "the verb X comes ... the verb") -- skip
                p2 = (role_chip["correct_gap"], role_chip["order"])
                w2 = f"the {w2} ({role_chip.get('noun') or role_chip.get('answer')})"

            if p1 == p2:
                continue
            actual_rel = "before" if p1 < p2 else "after"
            if actual_rel != rel:
                mistakes.append({
                    "chunk": chunk["chunk"], "reason": chunk["reason"],
                    "claim": f"{w1} {rel} {w2}", "actual": f"{w1} {actual_rel} {w2}",
                })
    return mistakes


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    exercises = {}
    for l in open(SRC):
        ex = json.loads(l)
        exercises[ex["id"]] = ex

    expl = json.loads(open(EXPL_JS).read()[len("const EXPLANATIONS = "):-1])
    items = [(int(id_str), {"chunks": chunks}) for id_str, chunks in expl.items()]
    if limit:
        items = items[:limit]

    n_checked = 0
    n_bad = 0
    bad_records = []
    for id_, rec in items:
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
    print(f"  {n_bad} have at least one order mistake ({n_bad/n_checked*100:.2f}%)" if n_checked else "")
    print(f"wrote {len(bad_records)} flagged exercises to {BAD_ORDER_OUT}")


if __name__ == "__main__":
    main()
