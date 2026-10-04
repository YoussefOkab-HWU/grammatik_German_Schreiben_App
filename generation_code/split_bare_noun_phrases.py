import json, sys
from collections import Counter, defaultdict
from known_genders import KNOWN_GENDERS

SRC = "./exercises.jsonl"

ARTICLE_WORDS = {'der','die','das','den','dem','des','ein','eine','einen','einem','einer','eines',
    'mein','meine','meinen','meinem','meiner','dein','deine','deinen','deinem','deiner',
    'sein','seine','seinen','seinem','seiner','ihr','ihre','ihren','ihrem','ihrer',
    'unser','unsere','unseren','unserem','unserer','euer','eure','euren','eurem','eurer',
    'kein','keine','keinen','keinem','keiner'}

DER_WORD_TABLE = {
    ('Nom','Masc'):'der', ('Nom','Fem'):'die', ('Nom','Neut'):'das', ('Nom','Plur'):'die',
    ('Acc','Masc'):'den', ('Acc','Fem'):'die', ('Acc','Neut'):'das', ('Acc','Plur'):'die',
    ('Dat','Masc'):'dem', ('Dat','Fem'):'der', ('Dat','Neut'):'dem', ('Dat','Plur'):'den',
    ('Gen','Masc'):'des', ('Gen','Fem'):'der', ('Gen','Neut'):'des', ('Gen','Plur'):'der',
}
EIN_WORD_ENDINGS = {
    ('Nom','Masc'):'', ('Nom','Fem'):'e', ('Nom','Neut'):'', ('Nom','Plur'):'e',
    ('Acc','Masc'):'en', ('Acc','Fem'):'e', ('Acc','Neut'):'', ('Acc','Plur'):'e',
    ('Dat','Masc'):'em', ('Dat','Fem'):'er', ('Dat','Neut'):'em', ('Dat','Plur'):'en',
    ('Gen','Masc'):'es', ('Gen','Fem'):'er', ('Gen','Neut'):'es', ('Gen','Plur'):'er',
}
EIN_WORD_STEMS = {'ein','mein','dein','sein','ihr','unser','euer','kein'}
# "ihr" (her/their) is both a der-word-like personal-possessive AND coincidentally
# the du-plural pronoun "ihr" (you-all) -- only treat as ein-word when it's
# actually functioning as a possessive in this list (article position), which is
# the only context bare_noun phrases put it in here.

DATIVE_VERBS = {"helfen","danken","gefallen","gehoeren","gehören","folgen","gratulieren",
    "passen","schmecken","vertrauen","verzeihen","glauben","gelingen","misslingen","fehlen",
    "dienen","drohen","raten","widersprechen","zuhoeren","zuhören","zusehen","gehorchen",
    "aehneln","ähneln","begegnen","entkommen","entgehen","genuegen","genügen","imponieren",
    "nuetzen","nützen","schaden","trotzen","unterliegen","zustimmen","applaudieren","antworten"}
COPULA_VERBS = {"sein","werden","bleiben"}


def article_kind(word):
    w = word.lower()
    if w in ('der','die','das','den','dem','des'):
        return 'der_word'
    stem = None
    for s in EIN_WORD_STEMS:
        if w == s or w.startswith(s):
            stem = s
            break
    return 'ein_word' if stem else None


def predict_form(kind, case, gender, stem_word):
    if kind == 'der_word':
        return DER_WORD_TABLE.get((case, gender))
    if kind == 'ein_word':
        # recover the possessive/kein stem from the observed word by matching
        # against known stems (handles ein/mein/dein/sein/ihr/unser/euer/kein)
        w = stem_word.lower()
        for s in sorted(EIN_WORD_STEMS, key=len, reverse=True):
            if w.startswith(s):
                ending = EIN_WORD_ENDINGS.get((case, gender), '')
                return s + ending
    return None


def build_gender_dict():
    gender_dict = defaultdict(Counter)
    number_dict = defaultdict(Counter)
    for l in open(SRC):
        ex = json.loads(l)
        for c in ex['chips']:
            if c['type'] == 'noun_phrase' and c.get('noun') and c.get('article'):
                if c['article'].get('gender'):
                    gender_dict[c['noun']][c['article']['gender']] += 1
                if c['article'].get('number'):
                    number_dict[c['noun']][c['article']['number']] += 1
    # supplement with the hand-built dictionary for nouns not otherwise
    # present anywhere else in the corpus -- only fills gaps, never
    # overrides a real corpus-derived gender count
    for noun, gender in KNOWN_GENDERS.items():
        if noun not in gender_dict:
            gender_dict[noun][gender] += 1
    return gender_dict, number_dict


def governing_verb(chips_sorted, idx):
    """Last verb-type chip in the same gap -- the semantic main verb (not a
    preceding modal/auxiliary), which is what actually governs the object's case."""
    gap = chips_sorted[idx]['correct_gap']
    last_verb = None
    for c in chips_sorted:
        if c['correct_gap'] != gap:
            continue
        if c['type'] == 'verb':
            last_verb = c
    return last_verb


def article_display(kind, article_word):
    if kind == 'der_word':
        return 'der'
    w = article_word.lower()
    for s in sorted(EIN_WORD_STEMS, key=len, reverse=True):
        if w.startswith(s):
            return s
    return None


def classify(ex, chips_sorted, idx, c, gender_dict):
    """Returns (case, kind, final_gender, final_number, predicted) if this
    bare_noun chip is a validated article+noun split candidate, else None."""
    words = c['answer'].split()
    if len(words) != 2 or words[0].lower() not in ARTICLE_WORDS:
        return None
    if words[0].lower() == 'ein' and words[1].lower() == 'paar':
        return None
    article_word, noun_word = words

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

    if lexical_gender_for_sing:
        candidate = predict_form(kind, case, lexical_gender_for_sing, article_word)
        if candidate and candidate.lower() == article_word.lower():
            return (case, kind, lexical_gender_for_sing, 'Sing', candidate)
    candidate = predict_form(kind, case, 'Plur', article_word)
    if candidate and candidate.lower() == article_word.lower():
        return (case, kind, 'Plur', 'Plur', candidate)
    return None


def report(exercises, gender_dict):
    total = validated = unknown_gender = 0
    mismatches = []
    for ex in exercises:
        chips_sorted = sorted(ex['chips'], key=lambda c: (c['correct_gap'], c['order']))
        for idx, c in enumerate(chips_sorted):
            if c['type'] != 'bare_noun' or not c.get('answer') or ' ' not in c['answer']:
                continue
            words = c['answer'].split()
            if len(words) != 2 or words[0].lower() not in ARTICLE_WORDS:
                continue
            if words[0].lower() == 'ein' and words[1].lower() == 'paar':
                continue
            total += 1
            if not gender_dict.get(words[1]):
                unknown_gender += 1
                continue
            result = classify(ex, chips_sorted, idx, c, gender_dict)
            if result:
                validated += 1
            else:
                mismatches.append((ex['id'], c['answer']))
    print(f"total simple article+noun bare_noun phrases: {total}")
    print(f"unknown gender (skipped): {unknown_gender}")
    print(f"validated (predicted form matches actual): {validated}")
    print(f"mismatches: {len(mismatches)}")
    for m in mismatches[:20]:
        print(" ", m)


def apply_split(exercises, gender_dict):
    n_converted = 0
    for ex in exercises:
        chips_sorted = sorted(ex['chips'], key=lambda c: (c['correct_gap'], c['order']))
        for idx, c in enumerate(chips_sorted):
            if c['type'] != 'bare_noun' or not c.get('answer') or ' ' not in c['answer']:
                continue
            result = classify(ex, chips_sorted, idx, c, gender_dict)
            if not result:
                continue
            case, kind, final_gender, final_number, predicted = result
            article_word, noun_word = c['answer'].split()
            display = article_display(kind, article_word)
            new_chip = {
                "type": "noun_phrase",
                "article": {
                    "kind": kind,
                    "display": display,
                    "answer": article_word,
                    "case": case,
                    "gender": final_gender,
                    "number": final_number,
                },
                "adjectives": [],
                "noun": noun_word,
                "correct_gap": c["correct_gap"],
                "order": c["order"],
            }
            # replace in place within ex['chips'] (find by identity, not
            # position, since ex['chips'] isn't necessarily gap/order sorted)
            for i, orig in enumerate(ex["chips"]):
                if orig is c:
                    ex["chips"][i] = new_chip
                    break
            n_converted += 1
    return n_converted


def main():
    exercises = [json.loads(l) for l in open(SRC)]
    gender_dict, number_dict = build_gender_dict()

    if len(sys.argv) > 1 and sys.argv[1] == "apply":
        n = apply_split(exercises, gender_dict)
        print(f"converted {n} bare_noun chips to noun_phrase chips")
        with open(SRC, "w") as f:
            for ex in exercises:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        print("wrote", SRC)
    else:
        report(exercises, gender_dict)


if __name__ == "__main__":
    main()
