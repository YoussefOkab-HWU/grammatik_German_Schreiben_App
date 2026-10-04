"""RECONSTRUCTED generator for the "Konjunktiv II" and "Modal verb forms" sentences.

Reconstructed with the assistance of Claude AI (Anthropic).

The original script that produced these two categories was not saved. This file
rebuilds it from the patterns found in the finished data:

  * every sentence is   SUBJECT + conjugated verb + VERB PHRASE.
    e.g.  "Du würdest mehr Sport treiben."   "Ihr könnt heute Abend ausgehen."
  * one shared list of verb phrases (infinitive at the end) is used for both
    categories - see konjunktiv_modal_lists.json (887 phrases, extracted from
    the data in the order they first appear)
  * subjects rotate through the personal pronouns, and later rounds also use
    plural nouns ("Die Ärzte dürfen ...")
  * verb forms: würde (Konjunktiv II), the modal verbs in present tense,
    Präteritum, and Konjunktiv II

It generates every combination; the app's data is a filtered subset of that.
Run with --verify to check it against exercises.jsonl.

Not reconstructed here (small hand-written sets in the original data):
  "hätte/wäre + participle" (Ich hätte das gemacht.), modal Perfekt
  (Ich habe nicht kommen können.) and "wenn" sentences.
"""

import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LISTS = json.load(open(os.path.join(HERE, "konjunktiv_modal_lists.json"), encoding="utf-8"))
VERB_PHRASES = LISTS["verb_phrases"]
PLURAL_NOUNS = LISTS["plural_nouns"]

# person keys: 1sg 2sg 3sg 1pl 2pl 3pl
PRONOUNS = [("Ich", "1sg"), ("Du", "2sg"), ("Er", "3sg"), ("Sie", "3sg"),
            ("Wir", "1pl"), ("Ihr", "2pl"), ("Sie", "3pl")]

WUERDE = {"1sg": "würde", "2sg": "würdest", "3sg": "würde",
          "1pl": "würden", "2pl": "würdet", "3pl": "würden"}

MODALS_PRESENT = {
    "können": {"1sg": "kann", "2sg": "kannst", "3sg": "kann", "1pl": "können", "2pl": "könnt", "3pl": "können"},
    "müssen": {"1sg": "muss", "2sg": "musst", "3sg": "muss", "1pl": "müssen", "2pl": "müsst", "3pl": "müssen"},
    "dürfen": {"1sg": "darf", "2sg": "darfst", "3sg": "darf", "1pl": "dürfen", "2pl": "dürft", "3pl": "dürfen"},
    "sollen": {"1sg": "soll", "2sg": "sollst", "3sg": "soll", "1pl": "sollen", "2pl": "sollt", "3pl": "sollen"},
    "wollen": {"1sg": "will", "2sg": "willst", "3sg": "will", "1pl": "wollen", "2pl": "wollt", "3pl": "wollen"},
    "möchten": {"1sg": "möchte", "2sg": "möchtest", "3sg": "möchte", "1pl": "möchten", "2pl": "möchtet", "3pl": "möchten"},
}


def stem_forms(stem):
    """Präteritum / Konjunktiv II modal endings: konnte, konntest, konnte, konnten, konntet, konnten."""
    return {"1sg": stem + "e", "2sg": stem + "est", "3sg": stem + "e",
            "1pl": stem + "en", "2pl": stem + "et", "3pl": stem + "en"}


MODALS_PRAETERITUM = {m: stem_forms(s) for m, s in
                      [("können", "konnt"), ("müssen", "musst"), ("dürfen", "durft"), ("sollen", "sollt")]}
MODALS_KONJ2 = {m: stem_forms(s) for m, s in
                [("können", "könnt"), ("müssen", "müsst"), ("dürfen", "dürft"), ("sollen", "sollt")]}


def subjects():
    for pron, person in PRONOUNS:
        yield pron, person
    for noun in PLURAL_NOUNS:
        yield f"Die {noun}", "3pl"


def sentence(subject, verb, phrase):
    return f"{subject} {verb} {phrase}."


def generate():
    """Yields (category, sentence) for every combination."""
    for phrase in VERB_PHRASES:
        for subject, person in subjects():
            yield "konjunktiv_ii", sentence(subject, WUERDE[person], phrase)
            for table in (MODALS_PRESENT, MODALS_PRAETERITUM):
                for forms in table.values():
                    yield "modal_verb_forms", sentence(subject, forms[person], phrase)
            for forms in MODALS_KONJ2.values():
                # Konjunktiv II of modals appears under both categories in the data
                yield "konjunktiv_ii", sentence(subject, forms[person], phrase)
                yield "modal_verb_forms", sentence(subject, forms[person], phrase)


def verify(exercises_path):
    generated = {s for _, s in generate()}
    real = [json.loads(l) for l in open(exercises_path, encoding="utf-8")]
    for cat in ("konjunktiv_ii", "modal_verb_forms"):
        sents = [e["answer"] for e in real if e["category"] == cat]
        hit = sum(1 for s in sents if s in generated)
        print(f"{cat:18s} {hit:5d} / {len(sents):5d} real sentences reproduced exactly ({hit / len(sents):.1%})")
    print(f"total combinations generated: {len(generated):,}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--verify", metavar="EXERCISES_JSONL", help="compare against the real exercises.jsonl")
    p.add_argument("--out", default="generated_konjunktiv_modal.jsonl", help="output file (one sentence per line)")
    args = p.parse_args()
    if args.verify:
        verify(args.verify)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            for cat, s in generate():
                f.write(json.dumps({"category": cat, "answer": s}, ensure_ascii=False) + "\n")
        print(f"wrote {args.out}")
