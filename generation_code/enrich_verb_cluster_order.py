import json, time, requests, re, sys
from itertools import groupby

MODEL = "mistral-small"
OLLAMA_URL = "http://localhost:11434/api/generate"
SRC = "./exercises.jsonl"
EXPL = "./explanations.js"
PATCHES_OUT = "./explanations_verb_cluster_patches.jsonl"

# double-infinitive verb clusters: a causative/perception verb (lassen, helfen,
# sehen, hoeren, fuehlen) combines with a bare infinitive of the main action,
# and BOTH stack, non-finite, at the very end of the clause -- main-action
# infinitive first, causative/perception verb last (e.g. "schneiden lassen",
# not "lassen schneiden"). This is the opposite order from participle+auxiliary
# ("habe...gesehen"), and the generic LLM explanation prompt has no idea this
# rule exists, so it either invents a wrong reason (e.g. "separable prefix")
# or just skips explaining the second verb's position entirely.
MODALS_AUX = {"wollen", "koennen", "können", "muessen", "müssen", "duerfen", "dürfen",
              "sollen", "moegen", "mögen", "haben", "sein", "werden"}
CAUSPERC = {"lassen", "helfen", "sehen", "hoeren", "hören", "fuehlen", "fühlen"}
# known mislabeled chip in this corpus: "gern" is tagged type 'verb' in a few
# exercises (a pre-existing data quirk, out of scope here) -- exclude it so it
# isn't mistaken for the main-action infinitive of a cluster
NOT_A_REAL_VERB = {"gern"}


def find_cluster_pairs(ex):
    chips = sorted(ex["chips"], key=lambda c: (c["correct_gap"], c["order"]))
    pairs = []
    for gap, grp in groupby(chips, key=lambda c: c["correct_gap"]):
        verbs = [c for c in grp if c["type"] == "verb"]
        for i in range(len(verbs) - 1):
            a, b = verbs[i], verbs[i + 1]
            if (b["display"] in CAUSPERC and b["answer"] == b["display"]
                    and a["answer"] == a["display"]
                    and a["display"] not in MODALS_AUX and a["display"] not in CAUSPERC
                    and a["display"] not in NOT_A_REAL_VERB
                    and b["order"] == a["order"] + 1):
                pairs.append((a, b))
    return pairs


def find_target_chunk(chunks, a_word, b_word, used):
    for c in chunks:
        if id(c) in used:
            continue
        words = re.findall(r"[a-zA-ZäöüßÄÖÜ]+", c["chunk"].lower())
        if a_word.lower() in words and b_word.lower() in words:
            return c
    # fall back: chunk containing just the causative/perception verb
    for c in chunks:
        if id(c) in used:
            continue
        words = re.findall(r"[a-zA-ZäöüßÄÖÜ]+", c["chunk"].lower())
        if b_word.lower() in words:
            return c
    return None


PROMPT_TMPL = """You previously explained part of a German sentence for a B1 learner, but missed (or got wrong) an important word-order rule.

Full German sentence: {answer}
The chunk in question: "{chunk}"
Your original reason: "{old_reason}"

This chunk contains a double-infinitive verb cluster: "{a_word}" + "{b_word}". "{b_word}" is a causative/perception verb (here meaning roughly "{b_gloss}") that combines with the bare infinitive "{a_word}" (the main action). In German, when these stack at the end of a clause, they are BOTH non-finite, and the order is main-action infinitive FIRST, then the causative/perception verb LAST -- i.e. "{a_word} {b_word}", the reverse of the usual participle+auxiliary order. Do not describe this as a separable prefix construction.

Rewrite the reason for this chunk (2-3 sentences, same teaching style as before) to explicitly state that "{a_word}" comes before "{b_word}" in this double-infinitive cluster, and briefly say why (both are non-finite, "{b_word}" is the causative/perception verb governing the bare infinitive "{a_word}"). Keep any correct, still-relevant case/gender content from the original reason if the chunk also contains a noun phrase.

Respond with ONLY the corrected reason text. No JSON, no quotes, no markdown, no extra commentary.
"""

GLOSS = {
    "lassen": "to have something done / to let", "helfen": "to help",
    "sehen": "to see", "hoeren": "to hear", "hören": "to hear",
    "fuehlen": "to feel", "fühlen": "to feel",
}


def call(prompt, timeout=120):
    r = requests.post(OLLAMA_URL, json={
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.2}
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()["response"].strip().strip('"')


def verify(new_reason, a_word, b_word):
    low = new_reason.lower()
    has_words = a_word.lower() in low and b_word.lower() in low
    has_order_word = re.search(r"\bbefore\b|\bfirst\b|\bprecedes\b", low) is not None
    return has_words and has_order_word


def build_candidates(exercises, expl, limit=None):
    candidates = []
    for ex in exercises:
        chunks = expl.get(str(ex["id"]))
        if not chunks:
            continue
        used = set()
        for a, b in find_cluster_pairs(ex):
            target = find_target_chunk(chunks, a["display"], b["display"], used)
            if not target:
                continue
            used.add(id(target))
            candidates.append({
                "id": ex["id"], "chunk": target["chunk"], "reason": target["reason"],
                "a_word": a["display"], "b_word": b["display"],
                "b_gloss": GLOSS.get(b["display"], b["display"]),
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

    print(f"found {len(candidates)} verb-cluster candidates ({len(already_done)} already patched, will skip those)")

    n_done = n_failed = 0
    with open(PATCHES_OUT, "a", buffering=1) as out_f:
        for cand in candidates:
            id_ = cand["id"]
            if (id_, cand["chunk"]) in already_done:
                continue
            prompt = PROMPT_TMPL.format(
                answer=answers[id_], chunk=cand["chunk"], old_reason=cand["reason"],
                a_word=cand["a_word"], b_word=cand["b_word"], b_gloss=cand["b_gloss"],
            )
            accepted = None
            for attempt in range(1, 4):
                try:
                    candidate_text = call(prompt)
                except Exception as e:
                    print(f"id={id_} attempt={attempt} error: {e}")
                    time.sleep(2)
                    continue
                if candidate_text and verify(candidate_text, cand["a_word"], cand["b_word"]):
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
                print(f"id={id_} ({cand['a_word']} {cand['b_word']}) enriched ({n_done})")
            else:
                n_failed += 1
                print(f"id={id_} could not produce a verified enrichment after retries")

    print(f"done: enriched {n_done}, failed {n_failed}")


if __name__ == "__main__":
    main()
