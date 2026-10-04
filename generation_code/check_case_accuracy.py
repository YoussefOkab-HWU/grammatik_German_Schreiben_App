import json, re

SRC = "./exercises.jsonl"
OUT = "./explanations.jsonl"
BAD_CASE_OUT = "./bad_case_ids.jsonl"

# fixed-case prepositions -- these NEVER vary by context, so any claim
# contradicting this table is a hard factual error, not a judgment call
FIXED_CASE = {
    "durch": "Acc", "für": "Acc", "gegen": "Acc", "ohne": "Acc", "um": "Acc", "bis": "Acc", "entlang": "Acc",
    "aus": "Dat", "ausser": "Dat", "außer": "Dat", "bei": "Dat", "mit": "Dat", "nach": "Dat", "seit": "Dat",
    "von": "Dat", "zu": "Dat", "gegenueber": "Dat", "gegenüber": "Dat", "entgegen": "Dat",
    "waehrend": "Gen", "während": "Gen", "wegen": "Gen", "trotz": "Gen", "statt": "Gen", "anstatt": "Gen",
    "innerhalb": "Gen", "ausserhalb": "Gen", "außerhalb": "Gen", "oberhalb": "Gen", "unterhalb": "Gen",
    "diesseits": "Gen", "jenseits": "Gen",
}
# two-way (Wechselpraepositionen) -- correct case is context-dependent (motion=Acc,
# location=Dat), so we check against the ground-truth case already recorded on
# that specific exercise's noun_phrase chip, not a fixed table
TWO_WAY = {"an", "auf", "hinter", "in", "neben", "ueber", "über", "unter", "vor", "zwischen"}

FUSED = {
    "im": "in", "ins": "in", "am": "an", "ans": "an", "beim": "bei", "vom": "von",
    "zum": "zu", "zur": "zu", "aufs": "auf", "durchs": "durch", "fuers": "für",
    "fürs": "für", "ums": "um", "ueberm": "über", "überm": "über", "unterm": "unter",
    "vorm": "vor", "hinterm": "hinter",
}

CASE_WORDS = {
    "Acc": ["accusative", "akkusativ"],
    "Dat": ["dative", "dativ"],
    "Gen": ["genitive", "genitiv"],
    "Nom": ["nominative", "nominativ"],
}

ALL_PREPS = set(FIXED_CASE) | TWO_WAY | set(FUSED)

# da-compounds (da + preposition) found in this corpus's da_compound category.
# For fixed-case base prepositions the case never varies. For two-way bases
# (an/auf/über/unter/vor/in) the case is fixed by the specific verb idiom,
# not by motion-vs-location like a normal two-way preposition would be --
# verified per-verb against the actual (verb, da-form) pairs present in the
# corpus (see conversation: darauf/darüber idioms here are uniformly
# accusative, darunter/davor/darin uniformly dative, daran is the one
# genuinely mixed case: erinnern/denken/gewöhnen=Acc but zweifeln=Dat).
DA_COMPOUND_FIXED = {
    "dafür": "Acc", "darum": "Acc", "dagegen": "Acc", "dadurch": "Acc",
    "davon": "Dat", "danach": "Dat", "dabei": "Dat", "dazu": "Dat",
    "darauf": "Acc", "darüber": "Acc", "daraus": "Dat",
    "darunter": "Dat", "davor": "Dat", "darin": "Dat",
}
DA_COMPOUND_BY_VERB = {
    "daran": {
        "zweifeln": "Dat",
        "_default": "Acc",  # erinnern, denken, gewöhnen etc.
    },
}


def norm_prep_token(tok):
    tok = tok.lower().strip(".,!?")
    if tok in FUSED:
        return FUSED[tok], True  # (base preposition, was_fused)
    if tok in ALL_PREPS:
        return tok, False
    return None, False


def ground_truth_case_items(ex):
    """Walk chips in true left-to-right order and return every checkable case
    claim as {marker, kind, case}:
      - kind="prep": marker is the preposition word, case is what it assigns
        to the noun immediately following it (compounds like "bis zu" only
        credit the LAST preposition in the run, since that's the one that
        actually governs the noun -- e.g. "bis zum Wochenende" is dative
        because of "zu", not "bis").
      - kind="noun": marker is the noun's own text, for noun_phrases with NO
        governing preposition (subjects, direct objects, indirect objects) --
        these get their case straight from the verb's valency, not a
        preposition, but the model still routinely states a case for them.
    """
    chips = sorted(range(len(ex["chips"])), key=lambda i: (ex["chips"][i]["correct_gap"], ex["chips"][i]["order"]))
    consumed = set()
    items = []
    for pos, i in enumerate(chips):
        if i in consumed:
            continue
        c = ex["chips"][i]
        if c["type"] == "preposition_req":
            prep = c["answer"].lower()
            expected = FIXED_CASE.get(prep)
            if expected is None and prep not in TWO_WAY:
                continue
            for j in chips[pos + 1:]:
                nxt = ex["chips"][j]
                if nxt["correct_gap"] != c["correct_gap"]:
                    break
                if nxt["type"] == "preposition_req":
                    break  # compound like "bis zu" -- the LATER prep governs, not this one
                if nxt["type"] == "noun_phrase":
                    case = (nxt.get("article") or {}).get("case")
                    if case:
                        true_case = expected if expected else case  # two-way: trust the chip's own case
                        items.append({"marker": prep, "kind": "prep", "case": true_case})
                        consumed.add(j)  # this noun is prepositional -- don't also check it as a bare object
                    break
                break
        elif c["type"] == "noun_phrase":
            case = (c.get("article") or {}).get("case")
            if case and c.get("noun"):
                items.append({"marker": c["noun"], "kind": "noun", "case": case})
        elif c["type"] == "adverb" and c.get("display") == "da":
            form = c["answer"].lower()
            if form in DA_COMPOUND_BY_VERB:
                verb_table = DA_COMPOUND_BY_VERB[form]
                verb = None
                for j in chips[:pos][::-1]:
                    prev = ex["chips"][j]
                    if prev["correct_gap"] != c["correct_gap"]:
                        break
                    if prev["type"] == "verb":
                        verb = prev["display"]
                        break
                case = None
                for key, val in verb_table.items():
                    if key != "_default" and verb and key in verb:
                        case = val
                        break
                if case is None:
                    case = verb_table["_default"]
                items.append({"marker": form, "kind": "noun", "case": case})
            elif form in DA_COMPOUND_FIXED:
                items.append({"marker": form, "kind": "noun", "case": DA_COMPOUND_FIXED[form]})
    return items


def _marker_in_word(word, marker, kind):
    if kind == "prep":
        base, _ = norm_prep_token(word)
        return base == marker
    return word.lower() == marker.lower()


def claimed_cases_in_reason(reason, marker, kind):
    """Only look for case-words in the sentence(s) of the reason that actually
    mention the target marker (preposition or noun) -- a reason covering
    multiple bundled prepositions/nouns (e.g. "um + Akkusativ ... mit dem
    Nachbarn wegen des Fernsehers") must not let a case-word said about one
    of them get blamed on a different one."""
    sentences = re.split(r"(?<=[.!?])\s+", reason)
    relevant = []
    for s in sentences:
        s_low = s.lower()
        words = re.findall(r"[a-zA-ZäöüßÄÖÜ]+", s_low)
        if any(_marker_in_word(w, marker, kind) for w in words):
            relevant.append(s_low)
    if not relevant:
        return set()  # the reason never actually discusses this marker at all --
                       # nothing to check, NOT license to blame it for a case-word
                       # said about something else bundled into the same chunk
    found = set()
    for s_low in relevant:
        for case, words in CASE_WORDS.items():
            if any(w in s_low for w in words):
                found.add(case)
    return found


def check_explanation(ex, chunks):
    truth_items = ground_truth_case_items(ex)
    if not truth_items:
        return []  # nothing to check

    mistakes = []
    truth_idx = 0
    for chunk in chunks:
        if truth_idx >= len(truth_items):
            break
        item = truth_items[truth_idx]
        chunk_words = re.findall(r"[a-zA-ZäöüßÄÖÜ]+", chunk["chunk"])
        matched = any(_marker_in_word(w, item["marker"], item["kind"]) for w in chunk_words)
        if not matched:
            continue
        claimed = claimed_cases_in_reason(chunk["reason"], item["marker"], item["kind"])
        if claimed and item["case"] not in claimed:
            mistakes.append({
                "chunk": chunk["chunk"],
                "reason": chunk["reason"],
                "expected_case": item["case"],
                "claimed_cases": sorted(claimed),
                "marker": item["marker"],
                "kind": item["kind"],
            })
        truth_idx += 1
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
    n_with_prep = 0
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
        if ground_truth_case_items(ex):
            n_with_prep += 1

    bad_records.sort(key=lambda b: b["id"])
    with open(BAD_CASE_OUT, "w") as f:
        for b in bad_records:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")

    print(f"checked {n_checked} generated explanations")
    print(f"  {n_with_prep} contain at least one checkable preposition")
    print(f"  {n_bad} have at least one case mismatch ({n_bad/n_with_prep*100:.2f}% of preposition-bearing exercises)" if n_with_prep else "")
    print(f"wrote {len(bad_records)} flagged exercises to {BAD_CASE_OUT}")


if __name__ == "__main__":
    main()
