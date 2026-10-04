import json, sys
sys.path.insert(0, ".")
from split_bare_noun_phrases import article_kind, predict_form, article_display

SRC = "./exercises.jsonl"
KNOWN_ADJ_STEMS = set(json.load(open("./known_adjective_stems.json")))

STRONG_ADJ_ENDINGS = {
    ("Nom","Masc"):"er", ("Nom","Fem"):"e", ("Nom","Neut"):"es", ("Nom","Plur"):"e",
    ("Acc","Masc"):"en", ("Acc","Fem"):"e", ("Acc","Neut"):"es", ("Acc","Plur"):"e",
    ("Dat","Masc"):"em", ("Dat","Fem"):"er", ("Dat","Neut"):"em", ("Dat","Plur"):"en",
    ("Gen","Masc"):"en", ("Gen","Fem"):"er", ("Gen","Neut"):"en", ("Gen","Plur"):"er",
}

# never eligible even if their ending happens to coincide with a strong
# adjective ending -- pronouns, determiners, and common adverbs whose
# uninflected form ends in -e/-en/-es/-em/-er purely by chance (heute,
# morgen, gerne, sie, welche...), not because they're declining to agree
# with the noun that follows.
NEVER_ADJECTIVE = {
    "heute","morgen","gerne","gern","sie","er","es","ich","du","wir","ihr",
    "mich","dich","ihn","ihm","uns","euch","welche","welcher","welches",
    "welchen","welchem","jene","jener","jenes","diese","dieser","dieses",
    "manche","mancher","manches","alle","aller","alles",
}


def effective_gender(chip):
    if chip.get("number") == "Plur":
        return "Plur"
    return chip.get("gender")


def classify_stranded(word, case, gender):
    if word.lower() in NEVER_ADJECTIVE:
        return (None, None, None)
    kind = article_kind(word)
    if kind:
        # ein-words (ein/eine/einen...) are grammatically singular-only --
        # there is no plural indefinite article in German -- so a "match"
        # against the Plur ending pattern is a coincidence, not a real
        # ein-word plural, and must never be accepted.
        if kind != "ein_word" or gender != "Plur":
            predicted = predict_form(kind, case, gender, word)
            if predicted and predicted.lower() == word.lower():
                return ("article", kind, gender)
        if gender != "Plur" and kind != "ein_word":
            predicted_plur = predict_form(kind, case, "Plur", word)
            if predicted_plur and predicted_plur.lower() == word.lower():
                return ("article", kind, "Plur")
    expected_ending = STRONG_ADJ_ENDINGS.get((case, gender))
    if expected_ending and word.endswith(expected_ending) and len(word) > len(expected_ending):
        stem = word[: -len(expected_ending)]
        if stem in KNOWN_ADJ_STEMS:
            return ("adjective", None, gender)
    return (None, None, None)


def main():
    do_apply = len(sys.argv) > 1 and sys.argv[1] == "apply"
    exercises = [json.loads(l) for l in open(SRC)]

    n_article = n_adjective = 0
    examples = []

    for ex in exercises:
        chips_sorted = sorted(ex["chips"], key=lambda c: (c["correct_gap"], c["order"]))
        for idx, c in enumerate(chips_sorted):
            if c["type"] != "noun_phrase" or c.get("article") is not None:
                continue
            if not c.get("gender") or not c.get("case") or c.get("adjectives"):
                continue
            prev = chips_sorted[idx - 1] if idx > 0 else None
            if not (prev and prev["correct_gap"] == c["correct_gap"] and prev["type"] == "bare_noun"
                    and prev["answer"] and prev["answer"][0].islower()):
                continue
            word = prev["answer"]
            gender = effective_gender(c)
            case = c["case"]
            number = c.get("number")

            kind_result, kind, resolved_gender = classify_stranded(word, case, gender)
            if kind_result == "article":
                if len(examples) < 100000:
                    examples.append(("article", ex["id"], word, c["noun"], case, resolved_gender, ex["answer"]))
                if do_apply:
                    c["article"] = {
                        "kind": kind, "display": article_display(kind, word),
                        "answer": word, "case": case, "gender": resolved_gender, "number": number,
                    }
                    ex["chips"] = [ch for ch in ex["chips"] if ch is not prev]
                n_article += 1
            elif kind_result == "adjective":
                expected_ending = STRONG_ADJ_ENDINGS[(case, gender)]
                stem = word[: -len(expected_ending)]
                if len(examples) < 100000:
                    examples.append(("adjective", ex["id"], word, c["noun"], case, gender, ex["answer"]))
                if do_apply:
                    c["adjectives"] = [{"display": stem, "answer": word, "case": case, "gender": gender, "number": number}]
                    ex["chips"] = [ch for ch in ex["chips"] if ch is not prev]
                n_adjective += 1

    print(f"{'reattached' if do_apply else 'would reattach'} {n_article} articles, {n_adjective} adjectives")
    for e in examples:
        print(f"  [{e[0]}] id={e[1]} word={e[2]!r} noun={e[3]!r} {e[4]}/{e[5]} | {e[6]}")

    if do_apply:
        with open(SRC, "w") as f:
            for ex in exercises:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        print("wrote", SRC)


if __name__ == "__main__":
    main()
