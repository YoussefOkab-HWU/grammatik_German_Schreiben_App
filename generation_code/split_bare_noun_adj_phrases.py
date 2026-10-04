import json, sys
sys.path.insert(0, ".")
from split_bare_noun_phrases import (
    ARTICLE_WORDS, article_kind, article_display, predict_form,
    build_gender_dict, governing_verb, DATIVE_VERBS, COPULA_VERBS,
)

SRC = "./exercises.jsonl"

# Adjective declension after an article is already showing case/gender/number
# clearly (a der-word) -- "weak" declension, adjective just needs -e or -en.
WEAK_ADJ_ENDINGS = {
    ('Nom','Masc'):'e', ('Nom','Fem'):'e', ('Nom','Neut'):'e', ('Nom','Plur'):'en',
    ('Acc','Masc'):'en', ('Acc','Fem'):'e', ('Acc','Neut'):'e', ('Acc','Plur'):'en',
    ('Dat','Masc'):'en', ('Dat','Fem'):'en', ('Dat','Neut'):'en', ('Dat','Plur'):'en',
    ('Gen','Masc'):'en', ('Gen','Fem'):'en', ('Gen','Neut'):'en', ('Gen','Plur'):'en',
}
# After an ein-word, which doesn't show gender in masc-Nom/neut-Nom/neut-Acc --
# the adjective picks up the "missing" marking there ("mixed" declension).
MIXED_ADJ_ENDINGS = {
    ('Nom','Masc'):'er', ('Nom','Fem'):'e', ('Nom','Neut'):'es', ('Nom','Plur'):'en',
    ('Acc','Masc'):'en', ('Acc','Fem'):'e', ('Acc','Neut'):'es', ('Acc','Plur'):'en',
    ('Dat','Masc'):'en', ('Dat','Fem'):'en', ('Dat','Neut'):'en', ('Dat','Plur'):'en',
    ('Gen','Masc'):'en', ('Gen','Fem'):'en', ('Gen','Neut'):'en', ('Gen','Plur'):'en',
}


INVARIANT_QUANTIFIERS = {'paar', 'dreiviertel', 'anderthalb'}


def classify(ex, chips_sorted, idx, c, gender_dict):
    words = c['answer'].split()
    if len(words) != 3 or words[0].lower() not in ARTICLE_WORDS:
        return None
    article_word, adj_word, noun_word = words
    if not noun_word[0].isupper() or adj_word[0].isupper():
        return None  # only handle article+adjective+NOUN, adjective lowercase
    if adj_word.lower() in INVARIANT_QUANTIFIERS:
        return None  # "ein paar X" / "ein dreiviertel X" don't decline like normal adjectives

    gender_counts = gender_dict.get(noun_word)
    if not gender_counts:
        return None
    lexical_gender = gender_counts.most_common(1)[0][0]
    lexical_gender_for_sing = lexical_gender if lexical_gender != 'Plur' else None

    gv = governing_verb(chips_sorted, idx)
    verb_lemma = (gv.get('display') or '').lower() if gv else ''
    gap_min_order = min(x['order'] for x in chips_sorted if x['correct_gap'] == c['correct_gap'])
    is_first_in_gap = (c['order'] == gap_min_order)
    if is_first_in_gap:
        case = 'Nom'
    elif verb_lemma in DATIVE_VERBS:
        case = 'Dat'
    elif verb_lemma in COPULA_VERBS:
        case = 'Nom'
    else:
        case = 'Acc'

    kind = article_kind(article_word)
    if not kind:
        return None

    for gender_try, number in ([(lexical_gender_for_sing, 'Sing')] if lexical_gender_for_sing else []) + [('Plur', 'Plur')]:
        if gender_try is None:
            continue
        art_pred = predict_form(kind, case, gender_try, article_word)
        if not (art_pred and art_pred.lower() == article_word.lower()):
            continue
        adj_table = WEAK_ADJ_ENDINGS if kind == 'der_word' else MIXED_ADJ_ENDINGS
        ending = adj_table.get((case, gender_try))
        if ending and adj_word.lower().endswith(ending):
            stem = adj_word[:len(adj_word) - len(ending)]
            return (case, kind, gender_try, number, stem, ending)
    return None


def report():
    exercises = [json.loads(l) for l in open(SRC)]
    gender_dict, _ = build_gender_dict()
    total = validated = 0
    mismatches = []
    for ex in exercises:
        chips_sorted = sorted(ex['chips'], key=lambda c: (c['correct_gap'], c['order']))
        for idx, c in enumerate(chips_sorted):
            if c['type'] != 'bare_noun' or not c.get('answer') or ' ' not in c['answer']:
                continue
            words = c['answer'].split()
            if len(words) != 3 or words[0].lower() not in ARTICLE_WORDS:
                continue
            if not words[2][0].isupper() or words[1][0].isupper():
                continue
            if words[1].lower() in INVARIANT_QUANTIFIERS:
                continue
            total += 1
            result = classify(ex, chips_sorted, idx, c, gender_dict)
            if result:
                validated += 1
            else:
                mismatches.append((ex['id'], c['answer']))
    print(f"total article+adjective+noun (exactly 3 words): {total}")
    print(f"validated: {validated}")
    print(f"mismatches: {len(mismatches)}")
    for m in mismatches[:30]:
        print(" ", m)


def apply_split():
    exercises = [json.loads(l) for l in open(SRC)]
    gender_dict, _ = build_gender_dict()
    n_converted = 0
    for ex in exercises:
        chips_sorted = sorted(ex['chips'], key=lambda c: (c['correct_gap'], c['order']))
        for idx, c in enumerate(chips_sorted):
            if c['type'] != 'bare_noun' or not c.get('answer') or ' ' not in c['answer']:
                continue
            words = c['answer'].split()
            if len(words) != 3 or words[0].lower() not in ARTICLE_WORDS:
                continue
            if not words[2][0].isupper() or words[1][0].isupper():
                continue
            result = classify(ex, chips_sorted, idx, c, gender_dict)
            if not result:
                continue
            case, kind, gender, number, adj_stem, adj_ending = result
            article_word, adj_word, noun_word = c['answer'].split()
            display = article_display(kind, article_word)
            new_chip = {
                "type": "noun_phrase",
                "article": {
                    "kind": kind, "display": display, "answer": article_word,
                    "case": case, "gender": gender, "number": number,
                },
                "adjectives": [{
                    "display": adj_stem, "answer": adj_word,
                    "case": case, "gender": gender, "number": number,
                }],
                "noun": noun_word,
                "correct_gap": c["correct_gap"],
                "order": c["order"],
            }
            for i, orig in enumerate(ex["chips"]):
                if orig is c:
                    ex["chips"][i] = new_chip
                    break
            n_converted += 1
    print(f"converted {n_converted} bare_noun chips to noun_phrase+adjective chips")
    with open(SRC, "w") as f:
        for ex in exercises:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print("wrote", SRC)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "apply":
        apply_split()
    else:
        report()
