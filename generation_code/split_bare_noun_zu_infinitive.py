import json, sys
sys.path.insert(0, ".")
from split_bare_noun_phrases import ARTICLE_WORDS, article_kind, article_display, predict_form, build_gender_dict
from split_bare_noun_adj_phrases import WEAK_ADJ_ENDINGS, MIXED_ADJ_ENDINGS, INVARIANT_QUANTIFIERS

SRC = "./exercises.jsonl"


def split_zu(answer):
    """Returns (np_words, verb_words) if answer is '[NP] zu [infinitive]',
    else None. The infinitive is the final word; 'zu' is the word right
    before it."""
    words = answer.split()
    if len(words) < 3:
        return None
    if words[-2].lower() != 'zu':
        return None
    if not words[-1].endswith(('en', 'n')):
        return None
    return words[:-2], words[-2:]


def classify_np(np_words, gender_dict):
    """Reuses the same article(+adjective)+noun logic as the other two
    passes, but case is fixed here: these are always the direct object of
    the following zu-infinitive verb (they never carry their own subject),
    so case=Acc is not a guess -- it's how this construction always works."""
    if len(np_words) not in (2, 3):
        return None
    if np_words[0].lower() not in ARTICLE_WORDS:
        return None
    if len(np_words) == 3 and (np_words[1][0].isupper() or np_words[1].lower() in INVARIANT_QUANTIFIERS):
        return None
    article_word = np_words[0]
    noun_word = np_words[-1]
    adj_word = np_words[1] if len(np_words) == 3 else None
    if not noun_word[0].isupper():
        return None

    gender_counts = gender_dict.get(noun_word)
    if not gender_counts:
        return None
    lexical_gender = gender_counts.most_common(1)[0][0]
    lexical_gender_for_sing = lexical_gender if lexical_gender != 'Plur' else None

    kind = article_kind(article_word)
    if not kind:
        return None

    case = 'Acc'
    for gender_try, number in ([(lexical_gender_for_sing, 'Sing')] if lexical_gender_for_sing else []) + [('Plur', 'Plur')]:
        art_pred = predict_form(kind, case, gender_try, article_word)
        if not (art_pred and art_pred.lower() == article_word.lower()):
            continue
        if adj_word:
            adj_table = WEAK_ADJ_ENDINGS if kind == 'der_word' else MIXED_ADJ_ENDINGS
            ending = adj_table.get((case, gender_try))
            if not (ending and adj_word.lower().endswith(ending)):
                continue
            adj_stem = adj_word[:len(adj_word) - len(ending)]
            return (case, kind, gender_try, number, noun_word, (adj_stem, adj_word))
        return (case, kind, gender_try, number, noun_word, None)
    return None


def report():
    exercises = [json.loads(l) for l in open(SRC)]
    gender_dict, _ = build_gender_dict()
    total = validated = 0
    mismatches = []
    for ex in exercises:
        for c in ex['chips']:
            if c['type'] != 'bare_noun' or not c.get('answer') or ' ' not in c['answer']:
                continue
            words = c['answer'].split()
            if not words or words[0].lower() not in ARTICLE_WORDS:
                continue
            split = split_zu(c['answer'])
            if not split:
                continue
            total += 1
            np_words, verb_words = split
            result = classify_np(np_words, gender_dict)
            if result:
                validated += 1
            else:
                mismatches.append((ex['id'], c['answer']))
    print(f"total NP+zu-infinitive bundles: {total}")
    print(f"validated: {validated}")
    print(f"mismatches: {len(mismatches)}")
    for m in mismatches[:30]:
        print(" ", m)


def apply_split():
    exercises = [json.loads(l) for l in open(SRC)]
    gender_dict, _ = build_gender_dict()
    n_converted = 0
    for ex in exercises:
        for c in list(ex['chips']):
            if c['type'] != 'bare_noun' or not c.get('answer') or ' ' not in c['answer']:
                continue
            words = c['answer'].split()
            if not words or words[0].lower() not in ARTICLE_WORDS:
                continue
            split = split_zu(c['answer'])
            if not split:
                continue
            np_words, verb_words = split
            result = classify_np(np_words, gender_dict)
            if not result:
                continue
            case, kind, gender, number, noun_word, adj = result
            article_word = np_words[0]
            display = article_display(kind, article_word)
            np_chip = {
                "type": "noun_phrase",
                "article": {"kind": kind, "display": display, "answer": article_word,
                            "case": case, "gender": gender, "number": number},
                "adjectives": ([{"display": adj[0], "answer": adj[1],
                                 "case": case, "gender": gender, "number": number}] if adj else []),
                "noun": noun_word,
                "correct_gap": c["correct_gap"],
                "order": c["order"],
            }
            verb_answer = " ".join(verb_words)  # "zu " + infinitive
            infinitive = verb_words[-1]
            verb_chip = {
                "type": "verb",
                "display": infinitive,
                "answer": verb_answer,
                "correct_gap": c["correct_gap"],
                "order": c["order"] + 0.5,
            }
            # bump every OTHER chip in the same gap that came after this one,
            # to make room for the new verb chip landing right after the NP
            for other in ex["chips"]:
                if other is c:
                    continue
                if other["correct_gap"] == c["correct_gap"] and other["order"] > c["order"]:
                    other["order"] += 1

            idx = ex["chips"].index(c)
            ex["chips"][idx] = np_chip
            ex["chips"].insert(idx + 1, verb_chip)
            n_converted += 1

    # re-normalize order values to clean integers per gap (they're currently
    # a mix of ints and +1/+0.5 floats after the inserts above)
    for ex in exercises:
        by_gap = {}
        for c in ex["chips"]:
            by_gap.setdefault(c["correct_gap"], []).append(c)
        for gap, chips in by_gap.items():
            chips.sort(key=lambda c: c["order"])
            for i, c in enumerate(chips):
                c["order"] = i

    print(f"converted {n_converted} bundles into NP+verb chip pairs")
    with open(SRC, "w") as f:
        for ex in exercises:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print("wrote", SRC)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "apply":
        apply_split()
    else:
        report()
