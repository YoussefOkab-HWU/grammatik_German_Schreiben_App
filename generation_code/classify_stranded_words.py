import json, sys
sys.path.insert(0, ".")
from split_bare_noun_phrases import (
    ARTICLE_WORDS, article_kind, predict_form, article_display,
)

SRC = "./exercises.jsonl"

STRONG_ADJ_ENDINGS = {
    ("Nom","Masc"):"er", ("Nom","Fem"):"e", ("Nom","Neut"):"es", ("Nom","Plur"):"e",
    ("Acc","Masc"):"en", ("Acc","Fem"):"e", ("Acc","Neut"):"es", ("Acc","Plur"):"e",
    ("Dat","Masc"):"em", ("Dat","Fem"):"er", ("Dat","Neut"):"em", ("Dat","Plur"):"en",
    ("Gen","Masc"):"en", ("Gen","Fem"):"er", ("Gen","Neut"):"en", ("Gen","Plur"):"er",
}


def effective_gender(chip):
    if chip.get("number") == "Plur":
        return "Plur"
    return chip.get("gender")


def main():
    exercises = [json.loads(l) for l in open(SRC)]

    n_article = n_adjective = n_neither = 0
    neither_words = {}

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

            kind = article_kind(word)
            is_article = False
            if kind:
                predicted = predict_form(kind, case, gender if gender != "Plur" else "Plur", word)
                if predicted and predicted.lower() == word.lower():
                    is_article = True
                elif gender != "Plur":
                    predicted_plur = predict_form(kind, case, "Plur", word)
                    if predicted_plur and predicted_plur.lower() == word.lower():
                        is_article = True

            if is_article:
                n_article += 1
                continue

            expected_ending = STRONG_ADJ_ENDINGS.get((case, gender))
            if expected_ending and word.endswith(expected_ending) and len(word) > len(expected_ending):
                n_adjective += 1
                continue

            n_neither += 1
            neither_words[word] = neither_words.get(word, 0) + 1

    print("true articles (stranded, need re-attaching as article):", n_article)
    print("true adjectives (stranded, need re-attaching as adjective):", n_adjective)
    print("neither (leave alone / investigate separately):", n_neither)
    print()
    print("neither-words breakdown:")
    for w, cnt in sorted(neither_words.items(), key=lambda x: -x[1])[:30]:
        print(f"  {w}: {cnt}")


if __name__ == "__main__":
    main()
