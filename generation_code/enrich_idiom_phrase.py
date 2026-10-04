import json, time, requests, re, sys

MODEL = "mistral-small"
OLLAMA_URL = "http://localhost:11434/api/generate"
SRC = "./exercises.jsonl"
EXPL = "./explanations.js"
PATCHES_OUT = "./explanations_idiom_patches.jsonl"

# fixed verb+preposition idioms -- the preposition here is memorized as part
# of the verb, not chosen for its literal spatial/temporal meaning, so a B1
# learner needs this flagged explicitly rather than left implicit in a case
# explanation. Same 34-pair list used to generate the drill exercises in
# generate_prep_idiom_exercises.py.
IDIOM_VERBS = [
    "warten", "sich freuen", "sich ärgern", "sich beschweren", "nachdenken",
    "sich interessieren", "sich entscheiden", "kämpfen", "denken", "sich erinnern",
    "sich gewöhnen", "glauben", "sich fürchten", "teilnehmen", "leiden", "zweifeln",
    "arbeiten", "bestehen", "sich verabschieden", "träumen", "riechen", "schmecken",
    "achten", "sich kümmern", "bitten", "sich bewerben", "hoffen", "sich verlassen",
    "sich konzentrieren", "sich vorbereiten", "sich beteiligen", "gehören", "passen",
    "gratulieren",
]

PROGRESSIVE_GLOSS = {
    ("warten", "auf"): "waiting for", ("sich freuen", "auf"): "looking forward to",
    ("sich ärgern", "über"): "getting annoyed about", ("sich beschweren", "über"): "complaining about",
    ("nachdenken", "über"): "thinking over", ("sich interessieren", "für"): "interested in",
    ("sich entscheiden", "für"): "deciding on", ("kämpfen", "für"): "fighting for",
    ("denken", "an"): "thinking of", ("sich erinnern", "an"): "remembering",
    ("sich gewöhnen", "an"): "getting used to", ("glauben", "an"): "believing in",
    ("sich fürchten", "vor"): "afraid of", ("teilnehmen", "an"): "participating in",
    ("leiden", "an"): "suffering from", ("zweifeln", "an"): "doubting",
    ("arbeiten", "an"): "working on", ("bestehen", "aus"): "consisting of",
    ("sich verabschieden", "von"): "saying goodbye to", ("träumen", "von"): "dreaming of",
    ("riechen", "nach"): "smelling of", ("schmecken", "nach"): "tasting of",
    ("achten", "auf"): "paying attention to", ("sich kümmern", "um"): "taking care of",
    ("bitten", "um"): "asking for", ("sich bewerben", "um"): "applying for",
    ("hoffen", "auf"): "hoping for", ("sich verlassen", "auf"): "relying on",
    ("sich konzentrieren", "auf"): "concentrating on", ("sich vorbereiten", "auf"): "preparing for",
    ("sich beteiligen", "an"): "participating in", ("gehören", "zu"): "belonging to",
    ("passen", "zu"): "matching", ("gratulieren", "zu"): "congratulating on",
}

# keyed by bare verb (no "sich " prefix) since chip['display'] never includes it
IDIOM_PAIRS = {}
for verb_full in IDIOM_VERBS:
    bare = verb_full.replace("sich ", "")
    for (v, p), gloss in PROGRESSIVE_GLOSS.items():
        if v == verb_full:
            IDIOM_PAIRS[(bare, p)] = (verb_full, gloss)

PROMPT_TMPL = """You previously explained part of a German sentence for a B1 learner, but missed an important vocabulary point.

Full German sentence: {answer}
The chunk in question: "{chunk}"
Your original reason: "{old_reason}"

"{verb_full}" + "{prep}" is a FIXED verb+preposition phrase (like an English phrasal verb) meaning "{gloss}". The preposition "{prep}" here is memorized together with the verb as a set unit -- it is NOT chosen for its normal literal/spatial meaning, and a learner cannot predict it from the verb alone.

Rewrite the reason for this chunk (2-3 sentences, same teaching style as before) to explicitly call out that "{verb_full} {prep}" is a fixed phrase that must be memorized as a unit, meaning "{gloss}", while keeping any useful case/word-order content from your original reason.

Respond with ONLY the corrected reason text. No JSON, no quotes, no markdown, no extra commentary.
"""


def call(prompt, timeout=120):
    r = requests.post(OLLAMA_URL, json={
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.2}
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()["response"].strip().strip('"')


def governing_verb(chips_sorted, idx):
    gap = chips_sorted[idx]["correct_gap"]
    last_verb = None
    for c in chips_sorted:
        if c["correct_gap"] != gap:
            continue
        if c["type"] == "verb":
            last_verb = c
    return last_verb


def find_target_chunk(chunks, prep_word, used):
    for c in chunks:
        if id(c) in used:
            continue
        words = re.findall(r"[a-zA-ZäöüßÄÖÜ]+", c["chunk"].lower())
        if prep_word.lower() in words:
            return c
    return None


def verify(new_reason):
    low = new_reason.lower()
    has_fixed = "fixed" in low
    has_phrase_word = re.search(r"phrase|expression|idiom", low) is not None
    return has_fixed and has_phrase_word


def build_candidates(exercises, expl, limit=None):
    candidates = []
    for ex in exercises:
        chunks = expl.get(str(ex["id"]))
        if not chunks:
            continue
        chips_sorted = sorted(ex["chips"], key=lambda c: (c["correct_gap"], c["order"]))
        used = set()
        for idx, c in enumerate(chips_sorted):
            if c["type"] != "preposition_req":
                continue
            gov = governing_verb(chips_sorted, idx)
            if not gov:
                continue
            key = (gov["display"], c["answer"])
            if key not in IDIOM_PAIRS:
                continue
            verb_full, gloss = IDIOM_PAIRS[key]
            target = find_target_chunk(chunks, c["answer"], used)
            if not target:
                continue
            used.add(id(target))
            candidates.append({
                "id": ex["id"], "chunk": target["chunk"], "reason": target["reason"],
                "verb_full": verb_full, "prep": c["answer"], "gloss": gloss,
            })
            if limit and len(candidates) >= limit:
                return candidates
    return candidates


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != "apply" else None

    exercises = [json.loads(l) for l in open(SRC)]
    answers = {ex["id"]: ex["answer"] for ex in exercises}
    expl = json.loads(open(EXPL).read()[len("const EXPLANATIONS = "):-1])

    candidates = build_candidates(exercises, expl, limit)

    already_done = set()
    try:
        for l in open(PATCHES_OUT):
            l = l.strip()
            if not l:
                continue
            p = json.loads(l)
            already_done.add((p["id"], p["chunk"]))
    except FileNotFoundError:
        pass

    print(f"found {len(candidates)} idiom candidates ({len(already_done)} already patched, will skip those)")

    n_done = n_failed = 0
    with open(PATCHES_OUT, "a", buffering=1) as out_f:
        for cand in candidates:
            id_ = cand["id"]
            if (id_, cand["chunk"]) in already_done:
                continue
            prompt = PROMPT_TMPL.format(
                answer=answers[id_], chunk=cand["chunk"], old_reason=cand["reason"],
                verb_full=cand["verb_full"], prep=cand["prep"], gloss=cand["gloss"],
            )
            accepted = None
            for attempt in range(1, 4):
                try:
                    candidate_text = call(prompt)
                except Exception as e:
                    print(f"id={id_} attempt={attempt} error: {e}")
                    time.sleep(2)
                    continue
                if candidate_text and verify(candidate_text):
                    accepted = candidate_text
                    break
                time.sleep(1)

            if accepted:
                out_f.write(json.dumps({
                    "id": id_, "chunk": cand["chunk"],
                    "old_reason": cand["reason"], "new_reason": accepted,
                }, ensure_ascii=False) + "\n")
                out_f.flush()
                n_done += 1
                print(f"id={id_} ({cand['verb_full']} {cand['prep']}) enriched ({n_done})")
            else:
                n_failed += 1
                print(f"id={id_} could not produce a verified enrichment after retries")

    print(f"done: enriched {n_done}, failed {n_failed}")


if __name__ == "__main__":
    main()
