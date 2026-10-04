import json, sys
from collections import Counter, defaultdict
sys.path.insert(0, ".")
from known_genders import KNOWN_GENDERS
from convert_bare_nouns import infer_case, MANUAL_SKIP, PLURAL_TRIGGERS

SRC = "./exercises.jsonl"
NOARTICLE_CLASSIFICATION = "./noarticle_classification.jsonl"
MAIN_CLASSIFICATION = "./bare_noun_classification.jsonl"


def load_classified_numbers_and_genders():
    number_lookup = {}
    gender_lookup = {}
    for fname in (MAIN_CLASSIFICATION, NOARTICLE_CLASSIFICATION):
        try:
            for l in open(fname):
                d = json.loads(l)
                if d["class"] == "common_noun":
                    if d.get("number"):
                        number_lookup.setdefault(d["word"], d["number"])
                    if d.get("gender"):
                        gender_lookup.setdefault(d["word"], d["gender"])
        except FileNotFoundError:
            pass
    return number_lookup, gender_lookup


def load_corpus_singular_gender(exercises):
    """Real lexical gender (Masc/Fem/Neut only) derived from the corpus's own
    correctly-tagged noun_phrase chips -- deliberately excludes any entry
    where number is Plur, since this corpus sometimes stores 'Plur' directly
    in the gender field itself as a shorthand (not a real gender), which
    would otherwise pollute a lookup meant for singular/lexical gender."""
    d = defaultdict(Counter)
    for ex in exercises:
        for c in ex["chips"]:
            if c["type"] == "noun_phrase" and c.get("article") and c.get("noun"):
                art = c["article"]
                if art.get("number") == "Sing" and art.get("gender") in ("Masc", "Fem", "Neut"):
                    d[c["noun"]][art["gender"]] += 1
    return {word: counter.most_common(1)[0][0] for word, counter in d.items()}


def infer_number_for_backfill(chips_sorted, idx, noun_word, classified_number):
    chip = chips_sorted[idx]
    prev = chips_sorted[idx - 1] if idx > 0 else None
    # a directly preceding plural-quantifier ("einige Kollegen", "viele Leute")
    # is the single most reliable signal for THIS specific occurrence --
    # checked first because word-form alone is genuinely ambiguous for weak
    # nouns like "Kollegen" (identical in Sing-Dat/Acc and Plur).
    if prev and prev["correct_gap"] == chip["correct_gap"] and prev["type"] == "bare_noun" \
            and prev["answer"].lower() in PLURAL_TRIGGERS:
        return "Plur"
    if classified_number in ("Sing", "Plur"):
        return classified_number
    return "Sing"


def main():
    do_apply = len(sys.argv) > 1 and sys.argv[1] == "apply"
    exercises = [json.loads(l) for l in open(SRC)]
    classified_numbers, classified_genders = load_classified_numbers_and_genders()
    corpus_singular_gender = load_corpus_singular_gender(exercises)

    n_filled = n_skipped_gender = n_skipped_case = 0
    examples = []

    for ex in exercises:
        chips_sorted = sorted(ex["chips"], key=lambda c: (c["correct_gap"], c["order"]))
        for idx, c in enumerate(chips_sorted):
            if c["type"] != "noun_phrase" or c.get("article") is not None or not c.get("noun"):
                continue
            if c.get("gender"):
                continue  # already has data (e.g. from a previous run)
            if (ex["id"], c["noun"]) in MANUAL_SKIP:
                continue

            noun = c["noun"]
            adj = c["adjectives"][0] if c.get("adjectives") else None

            # most of these chips already carry gender+case+number directly
            # on their own adjective ("nächste Woche": case=Acc, gender=Fem,
            # number=Sing already sitting there) -- far more reliable than
            # re-inferring, since it was computed once already at generation
            # time; only fall back to inference for the ones missing it.
            if adj and adj.get("gender") and adj.get("case") and adj.get("number"):
                gender, case, number = adj["gender"], adj["case"], adj["number"]
            else:
                number = infer_number_for_backfill(chips_sorted, idx, noun, classified_numbers.get(noun))
                if number == "Plur":
                    gender = "Plur"
                else:
                    gender = KNOWN_GENDERS.get(noun) or classified_genders.get(noun) or corpus_singular_gender.get(noun)
                    if not gender:
                        n_skipped_gender += 1
                        continue
                case = infer_case(chips_sorted, idx)
                if not case:
                    n_skipped_case += 1
                    continue

            if len(examples) < 25:
                examples.append((ex["id"], ex["answer"], noun, gender, case, number))
            if do_apply:
                c["gender"] = gender
                c["case"] = case
                c["number"] = number
            n_filled += 1

    print(f"{'filled' if do_apply else 'would fill'}: {n_filled}")
    print(f"skipped (no gender source): {n_skipped_gender}")
    print(f"skipped (ambiguous case): {n_skipped_case}")
    for e in examples:
        print(f"  id={e[0]} noun={e[2]!r} -> {e[3]}/{e[4]}/{e[5]}  | {e[1]}")

    if do_apply:
        with open(SRC, "w") as f:
            for ex in exercises:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        print("wrote", SRC)


if __name__ == "__main__":
    main()
