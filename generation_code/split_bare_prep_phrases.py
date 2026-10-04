import json, sys
from collections import Counter, defaultdict
sys.path.insert(0, ".")
from known_genders import KNOWN_GENDERS
from split_bare_noun_phrases import (
    ARTICLE_WORDS, DER_WORD_TABLE, EIN_WORD_ENDINGS, EIN_WORD_STEMS,
    article_kind, predict_form, article_display,
)
from check_case_accuracy import FIXED_CASE, TWO_WAY

SRC = "./exercises.jsonl"

# same bug class as split_bare_noun_phrases.py's "der Zug" merged-chip case,
# but here the whole "preposition + article + noun" sequence was generated as
# three flat, position-only bare_noun chips -- so a learner never has to
# choose the preposition OR the case-correct article at all, defeating the
# entire point of the exercise.
PREPOSITIONS = set(FIXED_CASE) | TWO_WAY


def build_gender_dict():
    gender_dict = defaultdict(Counter)
    for l in open(SRC):
        ex = json.loads(l)
        for c in ex["chips"]:
            if c["type"] == "noun_phrase" and c.get("noun") and c.get("article"):
                if c["article"].get("gender"):
                    gender_dict[c["noun"]][c["article"]["gender"]] += 1
    for noun, gender in KNOWN_GENDERS.items():
        if noun not in gender_dict:
            gender_dict[noun][gender] += 1
    return gender_dict


def find_triples(ex):
    """Consecutive (preposition, article, noun) bare_noun chip triples in the
    same gap, in strict chip order (no other chip between them)."""
    chips_sorted = sorted(ex["chips"], key=lambda c: (c["correct_gap"], c["order"]))
    triples = []
    for i in range(len(chips_sorted) - 2):
        a, b, c = chips_sorted[i], chips_sorted[i + 1], chips_sorted[i + 2]
        if not (a["type"] == "bare_noun" and b["type"] == "bare_noun" and c["type"] == "bare_noun"):
            continue
        if not (a["correct_gap"] == b["correct_gap"] == c["correct_gap"]):
            continue
        if not (b["order"] == a["order"] + 1 and c["order"] == b["order"] + 1):
            continue
        if a["answer"].lower() not in PREPOSITIONS:
            continue
        if b["answer"].lower() not in ARTICLE_WORDS:
            continue
        if not c["answer"][:1].isupper():
            continue
        triples.append((a, b, c))
    return triples


def classify(prep_word, article_word, noun_word, gender_dict):
    gender_counts = gender_dict.get(noun_word)
    if not gender_counts:
        return None
    lexical_gender = gender_counts.most_common(1)[0][0]
    kind = article_kind(article_word)
    if not kind:
        return None

    prep_low = prep_word.lower()
    candidate_cases = []
    if prep_low in FIXED_CASE:
        candidate_cases = [FIXED_CASE[prep_low]]
    elif prep_low in TWO_WAY:
        candidate_cases = ["Acc", "Dat"]
    else:
        return None

    genders_to_try = [lexical_gender] if lexical_gender != "Plur" else []
    genders_to_try.append("Plur")

    matches = []
    for case in candidate_cases:
        for gender in genders_to_try:
            predicted = predict_form(kind, case, gender, article_word)
            if predicted and predicted.lower() == article_word.lower():
                matches.append((case, gender))

    if len(matches) != 1:
        return None
    case, gender = matches[0]
    number = "Plur" if gender == "Plur" else "Sing"
    final_gender = gender if gender != "Plur" else (lexical_gender if lexical_gender != "Plur" else "Plur")
    return (case, kind, final_gender, number)


def report(exercises, gender_dict):
    total = resolved = ambiguous_or_unknown = 0
    for ex in exercises:
        for a, b, c in find_triples(ex):
            total += 1
            result = classify(a["answer"], b["answer"], c["answer"], gender_dict)
            if result:
                resolved += 1
            else:
                ambiguous_or_unknown += 1
                print("UNRESOLVED", ex["id"], ex["category"], a["answer"], b["answer"], c["answer"])
    print(f"total candidate triples: {total}")
    print(f"resolved (safe to convert): {resolved}")
    print(f"unresolved (left untouched): {ambiguous_or_unknown}")


def apply_split(exercises, gender_dict):
    n_converted = 0
    for ex in exercises:
        for a, b, c in find_triples(ex):
            result = classify(a["answer"], b["answer"], c["answer"], gender_dict)
            if not result:
                continue
            case, kind, gender, number = result
            article_word = b["answer"]
            noun_word = c["answer"]

            new_prep = {
                "type": "preposition_req", "answer": a["answer"],
                "correct_gap": a["correct_gap"], "order": a["order"],
            }
            new_noun_phrase = {
                "type": "noun_phrase",
                "article": {
                    "kind": kind, "display": article_display(kind, article_word),
                    "answer": article_word, "case": case, "gender": gender, "number": number,
                },
                "adjectives": [], "noun": noun_word,
                "correct_gap": b["correct_gap"], "order": b["order"],
            }

            for i, orig in enumerate(ex["chips"]):
                if orig is a:
                    ex["chips"][i] = new_prep
                elif orig is b:
                    ex["chips"][i] = new_noun_phrase
            ex["chips"] = [ch for ch in ex["chips"] if ch is not c]
            n_converted += 1
    return n_converted


def main():
    exercises = [json.loads(l) for l in open(SRC)]
    gender_dict = build_gender_dict()

    if len(sys.argv) > 1 and sys.argv[1] == "apply":
        n = apply_split(exercises, gender_dict)
        print(f"converted {n} bare_noun triples to preposition_req + noun_phrase")
        with open(SRC, "w") as f:
            for ex in exercises:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        print("wrote", SRC)
    else:
        report(exercises, gender_dict)


if __name__ == "__main__":
    main()
