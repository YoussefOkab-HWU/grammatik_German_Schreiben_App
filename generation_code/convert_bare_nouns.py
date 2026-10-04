import json, sys
from collections import Counter, defaultdict
from itertools import groupby
sys.path.insert(0, ".")
from known_genders import KNOWN_GENDERS
from check_case_accuracy import FIXED_CASE, TWO_WAY

SRC = "./exercises.jsonl"
CLASSIFICATION = "./bare_noun_classification.jsonl"

DATIVE_VERBS = {"helfen", "danken", "gefallen", "gehoeren", "gehören", "folgen", "gratulieren",
    "passen", "schmecken", "vertrauen", "verzeihen", "glauben", "gelingen", "misslingen", "fehlen",
    "dienen", "drohen", "raten", "widersprechen", "zuhoeren", "zuhören", "zusehen", "gehorchen",
    "aehneln", "ähneln", "begegnen", "entkommen", "entgehen", "genuegen", "genügen", "imponieren",
    "nuetzen", "nützen", "schaden", "trotzen", "unterliegen", "zustimmen", "applaudieren", "antworten"}

PLURAL_TRIGGERS = {"zwei", "drei", "vier", "fünf", "fuenf", "sechs", "sieben", "acht", "neun", "zehn",
    "viele", "einige", "mehrere", "wenige", "beide", "alle", "paar"}

FUSED_PREP_CASE = {
    "am": "Dat", "ans": "Acc", "im": "Dat", "ins": "Acc",
    "zum": "Dat", "zur": "Dat", "vom": "Dat", "beim": "Dat",
}

# two specific (id, word) instances found during review where the generic
# heuristic gets the case wrong: id=821 "Klima" sits in a nested apposition
# ("zum Thema Klima") rather than being a separate governed object; id=3239
# "Haarfarbe" is actually the NOMINATIVE subject of a relative clause
# ("welche Haarfarbe ... passt"), not the dative object of "passen" -- both
# are one-off structural edge cases (2 out of 3410), not worth a general rule.
MANUAL_SKIP = {(821, "Klima"), (3239, "Haarfarbe")}

# manual fixups for LLM schema slips / gaps noticed during review
MANUAL_CLASS_FIXUPS = {
    "Schach": ("common_noun", "Neut", "Sing"), "Geschirr": ("common_noun", "Neut", "Sing"),
    "Fieber": ("common_noun", "Neut", "Sing"), "Zimmer": ("common_noun", "Neut", "Sing"),
    "Lesen": ("common_noun", "Neut", "Sing"), "Umsteigen": ("common_noun", "Neut", "Sing"),
    # "Plastik" is polysemous: "das Plastik" (neuter, the material) vs "die
    # Plastik" (feminine, a sculpture) -- every instance in this corpus uses
    # the material sense ("weniger Plastik benutzen"), which the LLM missed.
    "Plastik": ("common_noun", "Neut", "Sing"),
}


def load_classification():
    words = {}
    for l in open(CLASSIFICATION):
        d = json.loads(l)
        words[d["word"]] = (d["class"], d.get("gender"), d.get("number"))
    for w, v in MANUAL_CLASS_FIXUPS.items():
        words[w] = v
    return words


def build_exact_form_dict(exercises):
    """gender+number keyed by the EXACT noun surface string (not lemma) --
    noun_phrase.noun already stores the literal inflected form as it appears
    in the sentence (e.g. "Freunden" dative plural), so an exact-string match
    against every other correctly-tagged noun_phrase elsewhere in the corpus
    gives a precise, corpus-verified answer for this specific inflected form."""
    d = defaultdict(Counter)
    for ex in exercises:
        for c in ex["chips"]:
            if c["type"] == "noun_phrase" and c.get("noun") and c.get("article"):
                art = c["article"]
                if art.get("gender") and art.get("number"):
                    d[c["noun"]][(art["gender"], art["number"])] += 1
    return d


def governing_verb(chips_sorted, idx):
    gap = chips_sorted[idx]["correct_gap"]
    last_verb = None
    for c in chips_sorted:
        if c["correct_gap"] != gap:
            continue
        if c["type"] == "verb":
            last_verb = c
    return last_verb


def infer_case(chips_sorted, idx):
    """Returns case, or None if not confidently determinable (e.g. governed
    by a two-way preposition with no article to verify motion-vs-location
    against -- better to skip than to silently guess wrong)."""
    chip = chips_sorted[idx]
    gap = chip["correct_gap"]
    # look for an immediately preceding preposition_req in the same gap
    prev = chips_sorted[idx - 1] if idx > 0 else None
    if prev and prev["correct_gap"] == gap and prev["type"] == "preposition_req":
        prep = prev["answer"].lower()
        if prep in FIXED_CASE:
            return FIXED_CASE[prep]
        if prep in TWO_WAY:
            return None  # ambiguous without an article form to verify against
        return None
    # some sentences store a FUSED preposition (beim, am, im, zum, zur, vom,
    # ans, ins) as a plain bare_noun token rather than a decomposed
    # preposition_req chip -- these fused forms are unambiguous (each maps to
    # exactly one base preposition + case), so check for them too, otherwise
    # this signal is silently missed and falls through to the verb/position
    # heuristic below, which can coincidentally agree (as with "beim...helfen",
    # both dative) but isn't guaranteed to for a different verb.
    if prev and prev["correct_gap"] == gap and prev["type"] == "bare_noun":
        fused_case = FUSED_PREP_CASE.get(prev["answer"].lower())
        if fused_case:
            return fused_case
    gv = governing_verb(chips_sorted, idx)
    verb_lemma = (gv.get("display") or "").lower() if gv else ""
    gap_min_order = min(x["order"] for x in chips_sorted if x["correct_gap"] == gap)
    if chip["order"] == gap_min_order:
        return "Nom"
    if verb_lemma in DATIVE_VERBS:
        return "Dat"
    if verb_lemma in ("sein", "werden", "bleiben"):
        return "Nom"
    return "Acc"


def infer_number(chips_sorted, idx, exact_form_dict, noun_word, classified_number):
    # the LLM saw this exact word in its actual sentence context and is a
    # far more reliable signal than guessing from a preceding quantifier --
    # e.g. "Krimis" is plural on its own, with no "zwei"/"viele" anywhere
    # nearby, which a quantifier-trigger heuristic alone would miss entirely.
    if classified_number in ("Sing", "Plur"):
        return classified_number
    exact = exact_form_dict.get(noun_word)
    if exact:
        (gender, number), _ = exact.most_common(1)[0]
        return number
    chip = chips_sorted[idx]
    prev = chips_sorted[idx - 1] if idx > 0 else None
    if prev and prev["correct_gap"] == chip["correct_gap"] and prev["type"] == "bare_noun" \
            and prev["answer"].lower() in PLURAL_TRIGGERS:
        return "Plur"
    return "Sing"


def main():
    do_apply = len(sys.argv) > 1 and sys.argv[1] == "apply"
    exercises = [json.loads(l) for l in open(SRC)]
    classification = load_classification()
    exact_form_dict = build_exact_form_dict(exercises)

    n_converted = 0
    n_skipped_ambiguous_case = 0
    n_skipped_class = 0
    examples = []

    for ex in exercises:
        chips_sorted = sorted(ex["chips"], key=lambda c: (c["correct_gap"], c["order"]))
        for idx, c in enumerate(chips_sorted):
            if c["type"] != "bare_noun" or not c["answer"] or not c["answer"][0].isupper():
                continue
            if (ex["id"], c["answer"]) in MANUAL_SKIP:
                continue
            cls_info = classification.get(c["answer"])
            if not cls_info or cls_info[0] != "common_noun":
                n_skipped_class += 1
                continue
            cls, gender, classified_number = cls_info
            if not gender:
                gender = KNOWN_GENDERS.get(c["answer"])
            case = infer_case(chips_sorted, idx)
            if not case:
                n_skipped_ambiguous_case += 1
                continue
            number = infer_number(chips_sorted, idx, exact_form_dict, c["answer"], classified_number)
            final_gender = gender if number != "Plur" else (gender or "Plur")
            if not final_gender:
                n_skipped_class += 1
                continue

            new_chip = {
                "type": "noun_phrase", "article": None, "adjectives": [],
                "noun": c["answer"], "gender": final_gender, "case": case, "number": number,
                "correct_gap": c["correct_gap"], "order": c["order"],
            }
            if len(examples) < 30:
                examples.append((ex["id"], ex["answer"], c["answer"], final_gender, case, number))

            if do_apply:
                for i, orig in enumerate(ex["chips"]):
                    if orig is c:
                        ex["chips"][i] = new_chip
                        break
            n_converted += 1

    print(f"{'converted' if do_apply else 'would convert'}: {n_converted}")
    print(f"skipped (not common_noun / no gender): {n_skipped_class}")
    print(f"skipped (ambiguous two-way-preposition case): {n_skipped_ambiguous_case}")
    print()
    for id_, ans, word, g, cs, n in examples:
        print(f"  id={id_} word={word!r} -> {g}/{cs}/{n}  | {ans}")

    if do_apply:
        with open(SRC, "w") as f:
            for ex in exercises:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        print("wrote", SRC)


if __name__ == "__main__":
    main()
