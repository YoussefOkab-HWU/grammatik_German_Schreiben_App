import json, sys
sys.path.insert(0, ".")
from split_bare_noun_phrases import DER_WORD_TABLE, EIN_WORD_ENDINGS

# "someone else's action affects MY (or your/his/our/their) belongings" --
# the possessive-dative pattern (dativus (in)commodi), explicitly NOT body
# parts: "Der Nachbar hat mir das Auto zerkratzt" (not "mein Auto"). Covers
# both disadvantage (damage/theft) and advantage (repair/cleaning) senses,
# since the pattern isn't limited to damage -- it's "a third party's action
# affected property associated with the dative-marked person," either way.

OUT_DRY = "scratch/dry_run_dative_possession_exercises.jsonl"
OUT_LIVE = "./exercises.jsonl"
START_ID = 920000

# subject doing the action -- explicitly a DIFFERENT person than the
# dative-affected one, since this pattern requires a third party
SUBJECTS = [
    ("der", "Masc", "Nachbar", "the neighbor"),
    ("die", "Fem", "Nachbarin", "the (female) neighbor"),
    ("mein", "Masc", "Freund", "my friend"),
    ("meine", "Fem", "Freundin", "my (female) friend"),
    ("der", "Masc", "Handwerker", "the repairman"),
    ("der", "Masc", "Dieb", "the thief"),
    ("meine", "Fem", "Schwester", "my sister"),
    ("mein", "Masc", "Bruder", "my brother"),
    ("die", "Fem", "Kollegin", "the (female) colleague"),
    ("der", "Masc", "Mitbewohner", "the roommate"),
    ("das", "Neut", "Kind", "the child"),
]

# (infinitive, 3sg present, 3pl present, participle, aux, separable_prefix_or_None)
VERBS = [
    ("kaputtmachen", "macht", "machen", "kaputtgemacht", "haben", "kaputt"),  # treated as separable "kaputt machen"
    ("zerkratzen", "zerkratzt", "zerkratzen", "zerkratzt", "haben", None),
    ("zerbrechen", "zerbricht", "zerbrechen", "zerbrochen", "haben", None),
    ("beschädigen", "beschädigt", "beschädigen", "beschädigt", "haben", None),
    ("stehlen", "stiehlt", "stehlen", "gestohlen", "haben", None),
    ("verlieren", "verliert", "verlieren", "verloren", "haben", None),
    ("beschmutzen", "beschmutzt", "beschmutzen", "beschmutzt", "haben", None),
    ("reparieren", "repariert", "reparieren", "repariert", "haben", None),
    ("waschen", "wäscht", "waschen", "gewaschen", "haben", None),
    ("putzen", "putzt", "putzen", "geputzt", "haben", None),
    ("aufräumen", "räumt", "räumen", "aufgeräumt", "haben", "auf"),
    ("abholen", "holt", "holen", "abgeholt", "haben", "ab"),
    ("streichen", "streicht", "streichen", "gestrichen", "haben", None),
]

# (noun, gender) -- kept as a lookup for gender only; which nouns pair with
# which verb is now decided per-verb below (VERB_NOUN_POOLS), since a blanket
# cross-product produces nonsense like "tidies up your phone" or "washes
# your laptop"
PROPERTY_NOUN_GENDER = {
    "Auto": "Neut", "Fahrrad": "Neut", "Handy": "Neut", "Laptop": "Masc",
    "Wohnung": "Fem", "Haus": "Neut", "Garten": "Masc", "Briefkasten": "Masc",
    "Zaun": "Masc", "Fenster": "Neut", "Tür": "Fem", "Küche": "Fem",
    "Zimmer": "Neut", "Tasche": "Fem", "Koffer": "Masc", "Jacke": "Fem",
    "Regenschirm": "Masc", "Uhr": "Fem", "Kamera": "Fem", "Buch": "Neut",
    "Sofa": "Neut", "Teppich": "Masc", "Schlüssel": "Masc", "Fernseher": "Masc",
    "Rasen": "Masc", "Balkon": "Masc",
}

# only nouns that are a plausible object for each specific verb
VERB_NOUN_POOLS = {
    "kaputtmachen": ["Auto", "Fahrrad", "Handy", "Laptop", "Fenster", "Tür", "Uhr", "Kamera", "Fernseher", "Regenschirm"],
    "zerkratzen": ["Auto", "Fahrrad", "Handy", "Laptop", "Tür", "Kamera", "Fernseher"],
    "zerbrechen": ["Handy", "Fenster", "Uhr", "Kamera", "Fernseher"],
    "beschädigen": ["Auto", "Fahrrad", "Handy", "Laptop", "Haus", "Zaun", "Fenster", "Tür", "Koffer", "Kamera", "Fernseher", "Balkon"],
    "stehlen": ["Auto", "Fahrrad", "Handy", "Laptop", "Tasche", "Koffer", "Uhr", "Kamera", "Regenschirm", "Schlüssel", "Fernseher"],
    "verlieren": ["Auto", "Fahrrad", "Handy", "Laptop", "Tasche", "Koffer", "Jacke", "Regenschirm", "Uhr", "Kamera", "Schlüssel", "Buch"],
    "beschmutzen": ["Auto", "Fahrrad", "Wohnung", "Garten", "Tür", "Küche", "Zimmer", "Tasche", "Jacke", "Sofa", "Teppich", "Balkon"],
    "reparieren": ["Auto", "Fahrrad", "Handy", "Laptop", "Zaun", "Fenster", "Tür", "Uhr", "Kamera", "Fernseher"],
    "waschen": ["Auto", "Fahrrad", "Fenster", "Tür", "Jacke", "Teppich"],
    "putzen": ["Auto", "Wohnung", "Haus", "Fenster", "Tür", "Küche", "Zimmer", "Teppich", "Balkon"],
    "aufräumen": ["Wohnung", "Haus", "Garten", "Küche", "Zimmer", "Balkon"],
    "abholen": ["Auto", "Fahrrad", "Handy", "Laptop", "Tasche", "Koffer", "Schlüssel"],
    "streichen": ["Haus", "Zaun", "Tür", "Zimmer", "Balkon"],
}

DATIVE_PRONOUNS = [
    ("mir", "me"), ("dir", "you"), ("ihm", "him/it"), ("uns", "us"),
    ("euch", "you all"), ("ihnen", "them"),
]

ENGLISH_VERB_PAST = {
    "kaputtmachen": "broke", "zerkratzen": "scratched", "zerbrechen": "shattered",
    "beschädigen": "damaged", "stehlen": "stole", "verlieren": "lost",
    "beschmutzen": "got dirt on", "reparieren": "fixed", "waschen": "washed",
    "putzen": "cleaned", "aufräumen": "tidied up", "abholen": "picked up",
    "streichen": "painted",
}
ENGLISH_VERB_PRESENT_3SG = {
    "kaputtmachen": "breaks", "zerkratzen": "scratches", "zerbrechen": "shatters",
    "beschädigen": "damages", "stehlen": "steals", "verlieren": "loses",
    "beschmutzen": "gets dirt on", "reparieren": "fixes", "waschen": "washes",
    "putzen": "cleans", "aufräumen": "tidies up", "abholen": "picks up",
    "streichen": "paints",
}
ENGLISH_VERB_INFINITIVE = {
    "kaputtmachen": "break", "zerkratzen": "scratch", "zerbrechen": "shatter",
    "beschädigen": "damage", "stehlen": "steal", "verlieren": "lose",
    "beschmutzen": "get dirt on", "reparieren": "fix", "waschen": "wash",
    "putzen": "clean", "aufräumen": "tidy up", "abholen": "pick up",
    "streichen": "paint",
}
ENGLISH_SUBJECT_GLOSS = {
    "Nachbar": "The neighbor", "Nachbarin": "The neighbor", "Freund": "My friend",
    "Freundin": "My friend", "Handwerker": "The repairman", "Dieb": "The thief",
    "Schwester": "My sister", "Bruder": "My brother", "Kollegin": "My colleague",
    "Mitbewohner": "My roommate", "Kind": "The child",
}
ENGLISH_DATIVE_POSSESSIVE = {"mir": "my", "dir": "your", "ihm": "his", "uns": "our", "euch": "your", "ihnen": "their"}
ENGLISH_PROPERTY_GLOSS = {
    "Auto": "car", "Fahrrad": "bike", "Handy": "phone", "Laptop": "laptop",
    "Wohnung": "apartment", "Haus": "house", "Garten": "garden", "Briefkasten": "mailbox",
    "Zaun": "fence", "Fenster": "window", "Tür": "door", "Küche": "kitchen",
    "Zimmer": "room", "Tasche": "bag", "Koffer": "suitcase", "Jacke": "jacket",
    "Regenschirm": "umbrella", "Uhr": "watch", "Kamera": "camera", "Buch": "book",
    "Sofa": "sofa", "Teppich": "carpet", "Schlüssel": "key", "Fernseher": "TV",
    "Rasen": "lawn", "Balkon": "balcony",
}


def subject_article_display(article_word):
    return {"der": "der", "die": "der", "das": "der", "mein": "mein", "meine": "mein"}[article_word]


def make_subject_chip(article, gender, noun, order):
    kind = "der_word" if article in ("der", "die", "das") else "ein_word"
    display = "der" if kind == "der_word" else "mein"
    return {
        "type": "noun_phrase",
        "article": {"kind": kind, "display": display, "answer": article, "case": "Nom", "gender": gender, "number": "Sing"},
        "adjectives": [], "noun": noun, "correct_gap": 0, "order": order,
    }


def make_property_chip(noun, gender, order):
    article = DER_WORD_TABLE[("Acc", gender)]
    return {
        "type": "noun_phrase",
        "article": {"kind": "der_word", "display": "der", "answer": article, "case": "Acc", "gender": gender, "number": "Sing"},
        "adjectives": [], "noun": noun, "correct_gap": 0, "order": order,
    }


def build_sentence(subj, verb, prop, dat_pronoun, structure, ex_id):
    art, gender_s, noun_s, _ = subj
    inf, s3sg, s3pl, part, aux, prefix = verb
    prop_noun, gender_p = prop
    dat_ans, dat_disp = dat_pronoun

    chips = []
    chips.append(make_subject_chip(art, gender_s, noun_s, 0))
    dat_chip = {"type": "pronoun", "display": dat_disp, "answer": dat_ans, "correct_gap": 0, "order": None}
    prop_chip = make_property_chip(prop_noun, gender_p, None)

    if structure == "perfekt":
        chips.append({"type": "verb", "display": "haben", "answer": "hat", "correct_gap": 0, "order": 1})
        dat_chip["order"] = 2
        prop_chip["order"] = 3
        chips.append(dat_chip)
        chips.append(prop_chip)
        chips.append({"type": "verb", "display": inf, "answer": part, "correct_gap": 0, "order": 4})
        subj_text = art.capitalize() if art in ("der", "die", "das") else art.capitalize()
        answer = f"{subj_text} {noun_s} hat {dat_ans} {prop_chip['article']['answer']} {prop_noun} {part}."
        english = f"{ENGLISH_SUBJECT_GLOSS[noun_s]} {ENGLISH_VERB_PAST[inf]} {ENGLISH_DATIVE_POSSESSIVE[dat_ans]} {ENGLISH_PROPERTY_GLOSS[prop_noun]}."

    elif structure == "praesens":
        verb_form = s3sg
        chips.append({"type": "verb", "display": inf, "answer": verb_form, "correct_gap": 0, "order": 1})
        dat_chip["order"] = 2
        prop_chip["order"] = 3
        chips.append(dat_chip)
        chips.append(prop_chip)
        if prefix:
            chips.append({"type": "verb_prefix", "display": prefix, "answer": prefix, "correct_gap": 0, "order": 4})
        subj_text = art.capitalize()
        prefix_txt = f" {prefix}" if prefix else ""
        answer = f"{subj_text} {noun_s} {verb_form} {dat_ans} {prop_chip['article']['answer']} {prop_noun}{prefix_txt}."
        english = f"{ENGLISH_SUBJECT_GLOSS[noun_s]} {ENGLISH_VERB_PRESENT_3SG[inf]} {ENGLISH_DATIVE_POSSESSIVE[dat_ans]} {ENGLISH_PROPERTY_GLOSS[prop_noun]}."

    else:  # modal
        modal_forms = {"muss": "müssen", "will": "wollen", "kann": "können"}
        modal_ans = ex_id % 3
        modal_word = ["muss", "will", "kann"][modal_ans]
        chips.append({"type": "verb", "display": modal_forms[modal_word], "answer": modal_word, "correct_gap": 0, "order": 1})
        dat_chip["order"] = 2
        prop_chip["order"] = 3
        chips.append(dat_chip)
        chips.append(prop_chip)
        inf_full = f"{prefix}{inf}" if prefix and not inf.startswith(prefix) else inf
        chips.append({"type": "verb", "display": inf, "answer": inf_full, "correct_gap": 0, "order": 4})
        subj_text = art.capitalize()
        modal_gloss = {"muss": "has to", "will": "wants to", "kann": "can"}[modal_word]
        answer = f"{subj_text} {noun_s} {modal_word} {dat_ans} {prop_chip['article']['answer']} {prop_noun} {inf_full}."
        english = f"{ENGLISH_SUBJECT_GLOSS[noun_s]} {modal_gloss} {ENGLISH_VERB_INFINITIVE[inf]} {ENGLISH_DATIVE_POSSESSIVE[dat_ans]} {ENGLISH_PROPERTY_GLOSS[prop_noun]}."

    return {
        "id": ex_id, "category": "dative_of_interest", "answer": answer, "english": english,
        "skeleton": [{"type": "text", "display": ".", "answer": "."}],
        "chips": chips,
    }


VERBS_BY_INF = {v[0]: v for v in VERBS}
BENEFIT_VERBS = {"reparieren", "waschen", "putzen", "aufräumen", "abholen", "streichen"}


def main():
    do_apply = len(sys.argv) > 1 and sys.argv[1] == "apply"
    structures = ["perfekt", "praesens", "modal"]

    # only generate from verb+noun pairs that are semantically plausible
    pairs = []
    for inf, nouns in VERB_NOUN_POOLS.items():
        verb = VERBS_BY_INF[inf]
        for noun in nouns:
            pairs.append((verb, (noun, PROPERTY_NOUN_GENDER[noun])))

    exercises = []
    ex_id = START_ID
    idx = 0
    target = 500
    while len(exercises) < target:
        pair_idx = idx % len(pairs)
        verb, prop = pairs[pair_idx]
        cycle = idx // len(pairs)
        # a thief never plausibly repairs/cleans/tidies your stuff -- keep
        # "Dieb" restricted to damage/theft-type verbs, not benefit ones
        eligible_subjects = [s for s in SUBJECTS if not (s[2] == "Dieb" and verb[0] in BENEFIT_VERBS)]
        subj = eligible_subjects[(idx + cycle) % len(eligible_subjects)]
        dat_pronoun = DATIVE_PRONOUNS[(idx + cycle * 2) % len(DATIVE_PRONOUNS)]
        structure = structures[(idx + cycle * 3) % len(structures)]
        ex = build_sentence(subj, verb, prop, dat_pronoun, structure, ex_id)
        exercises.append(ex)
        ex_id += 1
        idx += 1

    ids = [e["id"] for e in exercises]
    assert len(ids) == len(set(ids)), "duplicate ids generated!"

    out_path = OUT_LIVE if do_apply else OUT_DRY
    mode = "a" if do_apply else "w"
    with open(out_path, mode) as f:
        for ex in exercises:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"{'appended to' if do_apply else 'wrote dry-run to'} {out_path}: {len(exercises)} exercises")


if __name__ == "__main__":
    main()
