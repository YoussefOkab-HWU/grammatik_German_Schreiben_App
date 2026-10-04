import json, sys
sys.path.insert(0, ".")
from split_bare_noun_phrases import DER_WORD_TABLE, EIN_WORD_ENDINGS

SRC = "./exercises.jsonl"
NEXT_ID_START = 900000  # well clear of every existing id range used so far

# Each idiom: (infinitive, preposition, case, reflexive?, präsens-per-person,
# participle, aux). Präsens forms given for ich/du/er/wir/Sie -- enough
# person variety without hand-conjugating every German pronoun.
IDIOMS = [
    ("warten", "auf", "Acc", False, {"ich":"warte","du":"wartest","er":"wartet","wir":"warten","Sie":"warten"}, "gewartet", "haben"),
    ("sich freuen", "auf", "Acc", True, {"ich":"freue","du":"freust","er":"freut","wir":"freuen","Sie":"freuen"}, "gefreut", "haben"),
    ("sich ärgern", "über", "Acc", True, {"ich":"ärgere","du":"ärgerst","er":"ärgert","wir":"ärgern","Sie":"ärgern"}, "geärgert", "haben"),
    ("sich beschweren", "über", "Acc", True, {"ich":"beschwere","du":"beschwerst","er":"beschwert","wir":"beschweren","Sie":"beschweren"}, "beschwert", "haben"),
    ("nachdenken", "über", "Acc", False, {"ich":"denke nach","du":"denkst nach","er":"denkt nach","wir":"denken nach","Sie":"denken nach"}, "nachgedacht", "haben"),
    ("sich interessieren", "für", "Acc", True, {"ich":"interessiere","du":"interessierst","er":"interessiert","wir":"interessieren","Sie":"interessieren"}, "interessiert", "haben"),
    ("sich entscheiden", "für", "Acc", True, {"ich":"entscheide","du":"entscheidest","er":"entscheidet","wir":"entscheiden","Sie":"entscheiden"}, "entschieden", "haben"),
    ("kämpfen", "für", "Acc", False, {"ich":"kämpfe","du":"kämpfst","er":"kämpft","wir":"kämpfen","Sie":"kämpfen"}, "gekämpft", "haben"),
    ("denken", "an", "Acc", False, {"ich":"denke","du":"denkst","er":"denkt","wir":"denken","Sie":"denken"}, "gedacht", "haben"),
    ("sich erinnern", "an", "Acc", True, {"ich":"erinnere","du":"erinnerst","er":"erinnert","wir":"erinnern","Sie":"erinnern"}, "erinnert", "haben"),
    ("sich gewöhnen", "an", "Acc", True, {"ich":"gewöhne","du":"gewöhnst","er":"gewöhnt","wir":"gewöhnen","Sie":"gewöhnen"}, "gewöhnt", "haben"),
    ("glauben", "an", "Acc", False, {"ich":"glaube","du":"glaubst","er":"glaubt","wir":"glauben","Sie":"glauben"}, "geglaubt", "haben"),
    ("sich fürchten", "vor", "Dat", True, {"ich":"fürchte","du":"fürchtest","er":"fürchtet","wir":"fürchten","Sie":"fürchten"}, "gefürchtet", "haben"),
    ("teilnehmen", "an", "Dat", False, {"ich":"nehme teil","du":"nimmst teil","er":"nimmt teil","wir":"nehmen teil","Sie":"nehmen teil"}, "teilgenommen", "haben"),
    ("leiden", "an", "Dat", False, {"ich":"leide","du":"leidest","er":"leidet","wir":"leiden","Sie":"leiden"}, "gelitten", "haben"),
    ("zweifeln", "an", "Dat", False, {"ich":"zweifle","du":"zweifelst","er":"zweifelt","wir":"zweifeln","Sie":"zweifeln"}, "gezweifelt", "haben"),
    ("arbeiten", "an", "Dat", False, {"ich":"arbeite","du":"arbeitest","er":"arbeitet","wir":"arbeiten","Sie":"arbeiten"}, "gearbeitet", "haben"),
    ("bestehen", "aus", "Dat", False, {"ich":"bestehe","du":"bestehst","er":"besteht","wir":"bestehen","Sie":"bestehen"}, "bestanden", "haben"),
    ("sich verabschieden", "von", "Dat", True, {"ich":"verabschiede","du":"verabschiedest","er":"verabschiedet","wir":"verabschieden","Sie":"verabschieden"}, "verabschiedet", "haben"),
    ("träumen", "von", "Dat", False, {"ich":"träume","du":"träumst","er":"träumt","wir":"träumen","Sie":"träumen"}, "geträumt", "haben"),
    ("riechen", "nach", "Dat", False, {"ich":"rieche","du":"riechst","er":"riecht","wir":"riechen","Sie":"riechen"}, "gerochen", "haben"),
    ("schmecken", "nach", "Dat", False, {"ich":"schmecke","du":"schmeckst","er":"schmeckt","wir":"schmecken","Sie":"schmecken"}, "geschmeckt", "haben"),
    ("achten", "auf", "Acc", False, {"ich":"achte","du":"achtest","er":"achtet","wir":"achten","Sie":"achten"}, "geachtet", "haben"),
    ("sich kümmern", "um", "Acc", True, {"ich":"kümmere","du":"kümmerst","er":"kümmert","wir":"kümmern","Sie":"kümmern"}, "gekümmert", "haben"),
    ("bitten", "um", "Acc", False, {"ich":"bitte","du":"bittest","er":"bittet","wir":"bitten","Sie":"bitten"}, "gebeten", "haben"),
    ("sich bewerben", "um", "Acc", True, {"ich":"bewerbe","du":"bewirbst","er":"bewirbt","wir":"bewerben","Sie":"bewerben"}, "beworben", "haben"),
    ("hoffen", "auf", "Acc", False, {"ich":"hoffe","du":"hoffst","er":"hofft","wir":"hoffen","Sie":"hoffen"}, "gehofft", "haben"),
    ("sich verlassen", "auf", "Acc", True, {"ich":"verlasse","du":"verlässt","er":"verlässt","wir":"verlassen","Sie":"verlassen"}, "verlassen", "haben"),
    ("sich konzentrieren", "auf", "Acc", True, {"ich":"konzentriere","du":"konzentrierst","er":"konzentriert","wir":"konzentrieren","Sie":"konzentrieren"}, "konzentriert", "haben"),
    ("sich vorbereiten", "auf", "Acc", True, {"ich":"bereite vor","du":"bereitest vor","er":"bereitet vor","wir":"bereiten vor","Sie":"bereiten vor"}, "vorbereitet", "haben"),
    ("sich beteiligen", "an", "Dat", True, {"ich":"beteilige","du":"beteiligst","er":"beteiligt","wir":"beteiligen","Sie":"beteiligen"}, "beteiligt", "haben"),
    ("gehören", "zu", "Dat", False, {"ich":"gehöre","du":"gehörst","er":"gehört","wir":"gehören","Sie":"gehören"}, "gehört", "haben"),
    ("passen", "zu", "Dat", False, {"ich":"passe","du":"passt","er":"passt","wir":"passen","Sie":"passen"}, "gepasst", "haben"),
    ("gratulieren", "zu", "Dat", False, {"ich":"gratuliere","du":"gratulierst","er":"gratuliert","wir":"gratulieren","Sie":"gratulieren"}, "gratuliert", "haben"),
]

# object noun pools per idiom, hand-picked to fit the meaning, each with a
# VERIFIED gender/number (cross-checked against known_genders.py / common
# knowledge) so the generated article is guaranteed correct via the same
# declension tables used everywhere else this session
# (noun, gender, number, english)
NOUN_POOLS = {
    ("warten","auf"): [("Bus","Masc","Sing","bus"), ("Zug","Masc","Sing","train"), ("Antwort","Fem","Sing","answer"), ("Ergebnis","Neut","Sing","result")],
    ("sich freuen","auf"): [("Urlaub","Masc","Sing","vacation"), ("Wochenende","Neut","Sing","weekend"), ("Party","Fem","Sing","party"), ("Reise","Fem","Sing","trip")],
    ("sich ärgern","über"): [("Verspätung","Fem","Sing","delay"), ("Fehler","Masc","Sing","mistake"), ("Wetter","Neut","Sing","weather"), ("Lärm","Masc","Sing","noise")],
    ("sich beschweren","über"): [("Service","Masc","Sing","service"), ("Lärm","Masc","Sing","noise"), ("Qualität","Fem","Sing","quality"), ("Preis","Masc","Sing","price")],
    ("nachdenken","über"): [("Problem","Neut","Sing","problem"), ("Zukunft","Fem","Sing","future"), ("Angebot","Neut","Sing","offer"), ("Entscheidung","Fem","Sing","decision")],
    ("sich interessieren","für"): [("Musik","Fem","Sing","music"), ("Geschichte","Fem","Sing","history"), ("Sport","Masc","Sing","sports"), ("Kunst","Fem","Sing","art")],
    ("sich entscheiden","für"): [("Job","Masc","Sing","job"), ("Wohnung","Fem","Sing","apartment"), ("Auto","Neut","Sing","car"), ("Angebot","Neut","Sing","offer")],
    ("kämpfen","für"): [("Recht","Neut","Sing","right"), ("Freiheit","Fem","Sing","freedom"), ("Familie","Fem","Sing","family"), ("Zukunft","Fem","Sing","future")],
    ("denken","an"): [("Urlaub","Masc","Sing","vacation"), ("Zukunft","Fem","Sing","future"), ("Familie","Fem","Sing","family"), ("Termin","Masc","Sing","appointment")],
    ("sich erinnern","an"): [("Reise","Fem","Sing","trip"), ("Kindheit","Fem","Sing","childhood"), ("Termin","Masc","Sing","appointment"), ("Gespräch","Neut","Sing","conversation")],
    ("sich gewöhnen","an"): [("Klima","Neut","Sing","climate"), ("Lärm","Masc","Sing","noise"), ("Job","Masc","Sing","job"), ("Zeitplan","Masc","Sing","schedule")],
    ("glauben","an"): [("Erfolg","Masc","Sing","success"), ("Plan","Masc","Sing","plan"), ("Zukunft","Fem","Sing","future"), ("Idee","Fem","Sing","idea")],
    ("sich fürchten","vor"): [("Prüfung","Fem","Sing","exam"), ("Dunkelheit","Fem","Sing","darkness"), ("Zukunft","Fem","Sing","future"), ("Chef","Masc","Sing","boss")],
    ("teilnehmen","an"): [("Kurs","Masc","Sing","course"), ("Meeting","Neut","Sing","meeting"), ("Wettbewerb","Masc","Sing","competition"), ("Projekt","Neut","Sing","project")],
    ("leiden","an"): [("Krankheit","Fem","Sing","illness"), ("Kopfschmerzen","Masc","Plur","headache"), ("Stress","Masc","Sing","stress"), ("Erkältung","Fem","Sing","cold")],
    ("zweifeln","an"): [("Plan","Masc","Sing","plan"), ("Erfolg","Masc","Sing","success"), ("Entscheidung","Fem","Sing","decision"), ("Idee","Fem","Sing","idea")],
    ("arbeiten","an"): [("Projekt","Neut","Sing","project"), ("Bericht","Masc","Sing","report"), ("Lösung","Fem","Sing","solution"), ("Idee","Fem","Sing","idea")],
    ("bestehen","aus"): [("Team","Neut","Sing","team"), ("Gruppe","Fem","Sing","group"), ("Material","Neut","Sing","material"), ("Holz","Neut","Sing","wood")],
    ("sich verabschieden","von"): [("Familie","Fem","Sing","family"), ("Kollegen","Masc","Plur","colleagues"), ("Freund","Masc","Sing","friend"), ("Chef","Masc","Sing","boss")],
    ("träumen","von"): [("Reise","Fem","Sing","trip"), ("Erfolg","Masc","Sing","success"), ("Zukunft","Fem","Sing","future"), ("Haus","Neut","Sing","house")],
    ("riechen","nach"): [("Kaffee","Masc","Sing","coffee"), ("Regen","Masc","Sing","rain"), ("Rauch","Masc","Sing","smoke"), ("Blumen","Fem","Plur","flowers")],
    ("schmecken","nach"): [("Zitrone","Fem","Sing","lemon"), ("Salz","Neut","Sing","salt"), ("Honig","Masc","Sing","honey"), ("Minze","Fem","Sing","mint")],
    ("achten","auf"): [("Gesundheit","Fem","Sing","health"), ("Details","Neut","Plur","details"), ("Zeit","Fem","Sing","time"), ("Budget","Neut","Sing","budget")],
    ("sich kümmern","um"): [("Kinder","Neut","Plur","children"), ("Garten","Masc","Sing","garden"), ("Problem","Neut","Sing","problem"), ("Gäste","Masc","Plur","guests")],
    ("bitten","um"): [("Hilfe","Fem","Sing","help"), ("Geduld","Fem","Sing","patience"), ("Erlaubnis","Fem","Sing","permission"), ("Rat","Masc","Sing","advice")],
    ("sich bewerben","um"): [("Job","Masc","Sing","job"), ("Stelle","Fem","Sing","position"), ("Praktikum","Neut","Sing","internship"), ("Stipendium","Neut","Sing","scholarship")],
    ("hoffen","auf"): [("Erfolg","Masc","Sing","success"), ("Regen","Masc","Sing","rain"), ("Hilfe","Fem","Sing","help"), ("Besserung","Fem","Sing","improvement")],
    ("sich verlassen","auf"): [("Freund","Masc","Sing","friend"), ("Team","Neut","Sing","team"), ("Erfahrung","Fem","Sing","experience"), ("Plan","Masc","Sing","plan")],
    ("sich konzentrieren","auf"): [("Arbeit","Fem","Sing","work"), ("Prüfung","Fem","Sing","exam"), ("Aufgabe","Fem","Sing","task"), ("Projekt","Neut","Sing","project")],
    ("sich vorbereiten","auf"): [("Prüfung","Fem","Sing","exam"), ("Reise","Fem","Sing","trip"), ("Gespräch","Neut","Sing","conversation"), ("Interview","Neut","Sing","interview")],
    ("sich beteiligen","an"): [("Projekt","Neut","Sing","project"), ("Diskussion","Fem","Sing","discussion"), ("Wettbewerb","Masc","Sing","competition"), ("Studie","Fem","Sing","study")],
    ("gehören","zu"): [("Familie","Fem","Sing","family"), ("Team","Neut","Sing","team"), ("Gruppe","Fem","Sing","group"), ("Programm","Neut","Sing","program")],
    ("passen","zu"): [("Kleid","Neut","Sing","dress"), ("Jacke","Fem","Sing","jacket"), ("Situation","Fem","Sing","situation"), ("Plan","Masc","Sing","plan")],
    ("gratulieren","zu"): [("Geburtstag","Masc","Sing","birthday"), ("Erfolg","Masc","Sing","success"), ("Abschluss","Masc","Sing","graduation"), ("Sieg","Masc","Sing","victory")],
}

PERSON_PRONOUN = {"ich": "Ich", "du": "Du", "er": "Er", "wir": "Wir", "Sie": "Sie"}
REFLEXIVE_PRONOUN = {"ich": "mich", "du": "dich", "er": "sich", "wir": "uns", "Sie": "sich"}
AUX_PRAESENS = {"ich": "habe", "du": "hast", "er": "hat", "wir": "haben", "Sie": "haben"}

ENGLISH_SUBJECT = {"ich": "I", "du": "You", "er": "He", "wir": "We", "Sie": "You"}
ENGLISH_BE = {"ich": "am", "du": "are", "er": "is", "wir": "are", "Sie": "are"}
# progressive-tense gloss per idiom -- used uniformly across all three German
# tense structures as just a meaning hint, not a tense-matched translation
# (a minor cosmetic simplification; the actual thing being tested is the
# German sentence, not English tense agreement)
PROGRESSIVE_GLOSS = {
    ("warten","auf"): "waiting for", ("sich freuen","auf"): "looking forward to",
    ("sich ärgern","über"): "getting annoyed about", ("sich beschweren","über"): "complaining about",
    ("nachdenken","über"): "thinking over", ("sich interessieren","für"): "interested in",
    ("sich entscheiden","für"): "deciding on", ("kämpfen","für"): "fighting for",
    ("denken","an"): "thinking of", ("sich erinnern","an"): "remembering",
    ("sich gewöhnen","an"): "getting used to", ("glauben","an"): "believing in",
    ("sich fürchten","vor"): "afraid of", ("teilnehmen","an"): "participating in",
    ("leiden","an"): "suffering from", ("zweifeln","an"): "doubting",
    ("arbeiten","an"): "working on", ("bestehen","aus"): "consisting of",
    ("sich verabschieden","von"): "saying goodbye to", ("träumen","von"): "dreaming of",
    ("riechen","nach"): "smelling of", ("schmecken","nach"): "tasting of",
    ("achten","auf"): "paying attention to", ("sich kümmern","um"): "taking care of",
    ("bitten","um"): "asking for", ("sich bewerben","um"): "applying for",
    ("hoffen","auf"): "hoping for", ("sich verlassen","auf"): "relying on",
    ("sich konzentrieren","auf"): "concentrating on", ("sich vorbereiten","auf"): "preparing for",
    ("sich beteiligen","an"): "participating in", ("gehören","zu"): "belonging to",
    ("passen","zu"): "matching", ("gratulieren","zu"): "congratulating on",
}

def make_english(verb, prep, person, noun_en):
    subj = ENGLISH_SUBJECT[person]
    gloss = PROGRESSIVE_GLOSS[(verb, prep)]
    return f"{subj} {ENGLISH_BE[person]} {gloss} the {noun_en}."


def der_word_form(case, gender, number):
    g = "Plur" if number == "Plur" else gender
    return DER_WORD_TABLE[(case, g)]


def main():
    exercises = []
    ex_id = NEXT_ID_START
    target_total = 500
    per_idiom = max(1, target_total // len(IDIOMS))

    for verb, prep, case, reflexive, forms, participle, aux in IDIOMS:
        pool = NOUN_POOLS[(verb, prep)]
        persons = list(forms.keys())
        combo_i = 0
        made = 0
        while made < per_idiom:
            person = persons[combo_i % len(persons)]
            noun, gender, number, noun_en = pool[combo_i % len(pool)]
            structure = ["praesens", "perfekt", "modal"][combo_i % 3]
            combo_i += 1

            article = der_word_form(case, gender, number)
            pron = PERSON_PRONOUN[person]
            refl = REFLEXIVE_PRONOUN[person] if reflexive else None
            verb_bare = verb.replace("sich ", "")

            chips = [{"type": "bare_noun", "display": pron, "answer": pron, "correct_gap": 0, "order": 0}]
            order = 1
            if structure == "praesens":
                verb_form = forms[person]
                chips.append({"type": "verb", "display": verb_bare, "answer": verb_form.split()[0], "correct_gap": 0, "order": order}); order += 1
                if refl:
                    chips.append({"type": "pronoun", "display": "reflexive", "answer": refl, "correct_gap": 0, "order": order}); order += 1
                chips.append({"type": "preposition_req", "answer": prep, "correct_gap": 0, "order": order}); order += 1
                chips.append({"type": "noun_phrase", "article": {"kind": "der_word", "display": "der", "answer": article, "case": case, "gender": gender, "number": number}, "adjectives": [], "noun": noun, "correct_gap": 0, "order": order}); order += 1
                if len(verb_form.split()) > 1:
                    chips.append({"type": "verb_prefix", "display": verb_form.split()[1], "answer": verb_form.split()[1], "correct_gap": 0, "order": order}); order += 1
                answer = f"{pron} {verb_form.split()[0]} " + (f"{refl} " if refl else "") + f"{prep} {article} {noun}" + (f" {verb_form.split()[1]}" if len(verb_form.split()) > 1 else "") + "."
                english = make_english(verb, prep, person, noun_en)
            elif structure == "perfekt":
                aux_form = AUX_PRAESENS[person]
                chips.append({"type": "verb", "display": aux, "answer": aux_form, "correct_gap": 0, "order": order}); order += 1
                if refl:
                    chips.append({"type": "pronoun", "display": "reflexive", "answer": refl, "correct_gap": 0, "order": order}); order += 1
                chips.append({"type": "preposition_req", "answer": prep, "correct_gap": 0, "order": order}); order += 1
                chips.append({"type": "noun_phrase", "article": {"kind": "der_word", "display": "der", "answer": article, "case": case, "gender": gender, "number": number}, "adjectives": [], "noun": noun, "correct_gap": 0, "order": order}); order += 1
                chips.append({"type": "verb", "display": verb_bare, "answer": participle, "correct_gap": 0, "order": order}); order += 1
                answer = f"{pron} {aux_form} " + (f"{refl} " if refl else "") + f"{prep} {article} {noun} {participle}."
                english = f"{ENGLISH_SUBJECT[person]} {'has' if person == 'er' else 'have'} been {PROGRESSIVE_GLOSS[(verb, prep)]} the {noun_en}."
            else:  # modal (müssen)
                modal_forms = {"ich":"muss","du":"musst","er":"muss","wir":"müssen","Sie":"müssen"}
                chips.append({"type": "verb", "display": "müssen", "answer": modal_forms[person], "correct_gap": 0, "order": order}); order += 1
                if refl:
                    chips.append({"type": "pronoun", "display": "reflexive", "answer": refl, "correct_gap": 0, "order": order}); order += 1
                chips.append({"type": "preposition_req", "answer": prep, "correct_gap": 0, "order": order}); order += 1
                chips.append({"type": "noun_phrase", "article": {"kind": "der_word", "display": "der", "answer": article, "case": case, "gender": gender, "number": number}, "adjectives": [], "noun": noun, "correct_gap": 0, "order": order}); order += 1
                chips.append({"type": "verb", "display": verb_bare, "answer": verb_bare, "correct_gap": 0, "order": order}); order += 1
                answer = f"{pron} {modal_forms[person]} " + (f"{refl} " if refl else "") + f"{prep} {article} {noun} {verb_bare}."
                english = f"{ENGLISH_SUBJECT[person]} must be {PROGRESSIVE_GLOSS[(verb, prep)]} the {noun_en}."

            exercises.append({
                "id": ex_id, "category": "prep_verb_idiom", "answer": answer, "english": english,
                "skeleton": [{"type": "text", "display": ".", "answer": "."}],
                "chips": chips, "english_lead_end": 0,
            })
            ex_id += 1
            made += 1

    print(f"generated {len(exercises)} exercises")

    if "apply" in sys.argv:
        with open(SRC, "a") as f:
            for ex in exercises:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        print(f"appended to {SRC}")
    else:
        out = "scratch/dry_run_idiom_exercises.jsonl"
        with open(out, "w") as f:
            for ex in exercises:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        print(f"DRY RUN -- wrote to {out}, not touching {SRC}")


if __name__ == "__main__":
    main()
