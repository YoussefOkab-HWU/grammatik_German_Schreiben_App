import json, re

SRC = "./exercises.jsonl"
EXPL = "./explanations.js"
OUT = "./definiteness_candidates.json"

NOT_ADVERBIAL = {'ich','du','er','sie','es','wir','ihr','sich','mich','dich','ihn','uns','euch','ihnen','mir','dir','ihm',
    'und','oder','aber','weil','dass','wenn','als','obwohl','denn','sondern','damit','bevor','nachdem','waehrend','während','ob',
    'warum','wann','wo','wie','was','wer'}  # question words -- usually start a separate subordinate clause, not a Tekamolo adverbial


def is_definite(article):
    if not article:
        return False
    return article.get("kind") == "der_word"


def is_adv(chip):
    if chip["type"] not in ("bare_noun", "adverb"):
        return False
    text = (chip.get("answer") or chip.get("display") or "").strip()
    if not text:
        return False
    return text.split()[0].lower() not in NOT_ADVERBIAL


def find_candidates(ex):
    chips = sorted(ex["chips"], key=lambda c: (c["correct_gap"], c["order"]))
    by_gap = {}
    for c in chips:
        by_gap.setdefault(c["correct_gap"], []).append(c)
    found = []
    for gap, items in by_gap.items():
        for i, c in enumerate(items):
            if c["type"] != "noun_phrase" or i == 0:
                continue
            prev = items[i - 1]
            nxt = items[i + 1] if i + 1 < len(items) else None
            if prev["type"] == "preposition_req":
                continue
            adverbial = None
            relation = None
            if is_adv(prev):
                adverbial = prev
                relation = "after"  # object comes after the adverbial
            elif nxt and is_adv(nxt):
                adverbial = nxt
                relation = "before"  # object comes before the adverbial
            if not adverbial:
                continue
            found.append({
                "noun": c.get("noun"),
                "article_answer": (c.get("article") or {}).get("answer"),
                "definite": is_definite(c.get("article")),
                "adverbial_word": adverbial.get("answer") or adverbial.get("display"),
                "relation": relation,
            })
    return found


def main():
    exercises = [json.loads(l) for l in open(SRC)]
    expl = json.loads(open(EXPL).read()[len("const EXPLANATIONS = "):-1])

    candidates = []
    for ex in exercises:
        found = find_candidates(ex)
        if not found:
            continue
        chunks = expl.get(str(ex["id"]))
        if not chunks:
            continue
        full_text = " ".join(c["reason"].lower() for c in chunks)
        if re.search(r"\bindefinite\b", full_text) or re.search(r"\bdefinite\b", full_text):
            continue  # already discusses it somewhere
        candidates.append({"id": ex["id"], "objects": found})

    print(f"candidate exercises needing definiteness enrichment: {len(candidates)}")
    json.dump(candidates, open(OUT, "w"), ensure_ascii=False)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
