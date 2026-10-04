import json, sys

SRC = "./exercises.jsonl"

# strong declension (used when NO article precedes the adjective -- the
# adjective itself then carries the case/gender/number marking that would
# otherwise sit on the article)
STRONG_ADJ_ENDINGS = {
    ("Nom","Masc"):"er", ("Nom","Fem"):"e", ("Nom","Neut"):"es", ("Nom","Plur"):"e",
    ("Acc","Masc"):"en", ("Acc","Fem"):"e", ("Acc","Neut"):"es", ("Acc","Plur"):"e",
    ("Dat","Masc"):"em", ("Dat","Fem"):"er", ("Dat","Neut"):"em", ("Dat","Plur"):"en",
    ("Gen","Masc"):"en", ("Gen","Fem"):"er", ("Gen","Neut"):"en", ("Gen","Plur"):"er",
}

# closed-class adverbs excluded outright even if an ending happened to match --
# many German adverbs and adjective stems share the same uninflected surface
# form (schnell/laut/leise/langsam can be either), so ending-match alone isn't
# sufficient; a word firmly in this list is never itself the noun's adjective.
ADVERB_BLOCKLIST = {
    "immer","oft","gestern","heute","morgen","sehr","wirklich","sofort","gerade",
    "schon","noch","nur","auch","genau","dort","hier","jetzt","bald","vielleicht",
    "ausserdem","außerdem","trotzdem","deshalb","also","dann","meistens","manchmal",
    "selten","nie","niemals","staendig","ständig","sicher","natuerlich","natürlich",
    "wahrscheinlich","eigentlich","ungefaehr","ungefähr","fast","sogar","zwar",
    "allerdings","jedoch","dennoch","dabei","dazu","danach","davor","deswegen",
    "ausser","außer","zusammen","gemeinsam","gern","gerne","weiterhin","bereits",
    "endlich","plotzlich","plötzlich","ploetzlich","zufaellig","zufällig","kaum",
    "besonders","insgesamt","uebrigens","übrigens","woechentlich","wöchentlich",
    "taeglich","täglich","monatlich","jaehrlich","jährlich",
}


def effective_gender(chip):
    if chip.get("number") == "Plur":
        return "Plur"
    return chip.get("gender")


def main():
    do_apply = len(sys.argv) > 1 and sys.argv[1] == "apply"
    exercises = [json.loads(l) for l in open(SRC)]

    n_merged = 0
    n_skipped_adverb = 0
    n_skipped_no_match = 0
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
            if word.lower() in ADVERB_BLOCKLIST:
                n_skipped_adverb += 1
                continue
            gender = effective_gender(c)
            expected_ending = STRONG_ADJ_ENDINGS.get((c["case"], gender))
            if not expected_ending or not word.endswith(expected_ending):
                n_skipped_no_match += 1
                continue
            stem = word[: -len(expected_ending)] if expected_ending else word
            if not stem:
                n_skipped_no_match += 1
                continue

            if len(examples) < 40:
                examples.append((ex["id"], word, stem, expected_ending, c["case"], gender, c["noun"], ex["answer"]))

            if do_apply:
                c["adjectives"] = [{"display": stem, "answer": word, "case": c["case"], "gender": gender, "number": c.get("number")}]
                for i, orig in enumerate(ex["chips"]):
                    if orig is prev:
                        ex["chips"].remove(orig)
                        break
            n_merged += 1

    print(f"{'merged' if do_apply else 'would merge'}: {n_merged}")
    print(f"skipped (known adverb): {n_skipped_adverb}")
    print(f"skipped (ending doesn't match expected declension): {n_skipped_no_match}")
    for e in examples:
        print(f"  id={e[0]} word={e[1]!r} stem={e[2]!r} ending={e[3]!r} case={e[4]} gender={e[5]} noun={e[6]!r} | {e[7]}")

    if do_apply:
        with open(SRC, "w") as f:
            for ex in exercises:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        print("wrote", SRC)


if __name__ == "__main__":
    main()
