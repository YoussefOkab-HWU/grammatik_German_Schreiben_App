import json, time, requests, re, sys
sys.path.insert(0, ".")
from check_verb_order import check_explanation

MODEL = "mistral-small"
OLLAMA_URL = "http://localhost:11434/api/generate"
SRC = "./exercises.jsonl"
OUT = "./explanations.jsonl"
FIXES = "./explanations_fixes.jsonl"
IDS_IN = "./enrichment_needed_ids.json"
PATCHES_OUT = "./explanations_cluster_patches.jsonl"

CHECKABLE_TYPES = {"verb", "negation_nicht", "verb_prefix"}

# words that mark a clause boundary (subordinator / purpose "um...zu") --
# if one of these sits between two "verb" chips that share a gap, they are
# NOT a real stacked verb cluster, just two independent clauses that
# happen to share a gap index (e.g. "hole...um...zu lesen" is a main verb
# plus an unrelated purpose clause, not haben+participle style stacking).
# Asking the model to explain a fake relationship between them produces
# invented, wrong grammar (verified: it claimed "brauche" governs a
# "zu"-infinitive that actually belongs to the separate um-clause).
CLAUSE_MARKERS = {"um", "dass", "weil", "ob", "wenn", "als", "bevor",
                   "nachdem", "waehrend", "während", "obwohl", "damit"}

PROMPT_TMPL = """You are a German grammar teacher explaining verb placement to a B1 English-speaking learner.

Full German sentence: {answer}
English meaning: {english}

This sentence has a verb cluster (multiple verbs stacking together) in this exact order: {cluster_order}.

The chunk to explain: "{chunk}"

Write a specific, correct explanation (2-3 sentences) of WHY these verbs appear in EXACTLY this order -- {cluster_order}. Name the actual grammatical mechanism that applies here (for example: the past participle sits before the auxiliary/passive "worden" in a Perfekt or passive-Perfekt construction; a modal verb is followed by a bare infinitive at the very end; Oberfeldumstellung places the governing verb (haben/werden or their subjunctive forms) AFTER the double infinitive in a subordinate clause; a separable prefix reunites with its stem when the verb isn't in finite main-clause position; etc.) -- whichever genuinely applies to THIS sentence. Be concrete about these specific words, not a generic statement.

Respond with ONLY the explanation text. No JSON, no quotes, no markdown, no extra commentary.
"""


def get_clusters(ex):
    chips = sorted(ex["chips"], key=lambda c: (c["correct_gap"], c["order"]))
    by_gap = {}
    for c in chips:
        by_gap.setdefault(c["correct_gap"], []).append(c)
    clusters = []
    for gap, items in by_gap.items():
        verb_positions = [i for i, c in enumerate(items) if c["type"] == "verb"]
        if len(verb_positions) < 2:
            continue
        first, last = verb_positions[0], verb_positions[-1]
        between = items[first + 1:last]
        if any(c["type"] in ("bare_noun", "preposition_req") and c.get("answer", "").lower() in CLAUSE_MARKERS for c in between):
            continue  # not a real stacked cluster -- two independent clauses sharing a gap
        clusters.append([(items[i]["answer"] or items[i]["display"]) for i in verb_positions])
    return clusters


def call(prompt, timeout=120):
    r = requests.post(OLLAMA_URL, json={
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.2}
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()["response"].strip().strip('"')


def load_latest():
    latest = {}
    for l in open(OUT):
        l = l.strip()
        if not l:
            continue
        rec = json.loads(l)
        latest[rec["id"]] = rec
    try:
        for l in open(FIXES):
            l = l.strip()
            if not l:
                continue
            rec = json.loads(l)
            latest[rec["id"]] = rec
    except FileNotFoundError:
        pass
    return latest


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None

    exercises = {}
    for l in open(SRC):
        ex = json.loads(l)
        exercises[ex["id"]] = ex

    ids = json.load(open(IDS_IN))
    if limit:
        ids = ids[:limit]

    already_done = set()
    try:
        for l in open(PATCHES_OUT):
            l = l.strip()
            if not l:
                continue
            already_done.add(json.loads(l)["id"])
    except FileNotFoundError:
        pass
    ids = [id_ for id_ in ids if id_ not in already_done]

    latest = load_latest()
    print(f"enriching {len(ids)} exercises ({len(already_done)} already done, skipping)")

    n_done = 0
    with open(PATCHES_OUT, "a", buffering=1) as out_f:
        for id_ in ids:
            ex = exercises[id_]
            rec = latest.get(id_)
            if not rec or not rec.get("chunks"):
                continue
            clusters = get_clusters(ex)
            if not clusters:
                continue

            chunks = rec["chunks"]
            new_chunks = [dict(c) for c in chunks]
            for cluster_words in clusters:
                words_lower = [w.lower() for w in cluster_words]
                # find the LAST chunk containing any cluster word -- that's
                # where the cluster's own stacking mechanics live
                target_idx = None
                for i, c in enumerate(chunks):
                    chunk_words = re.findall(r"[a-zA-ZäöüßÄÖÜ]+", c["chunk"].lower())
                    if any(w in chunk_words for w in words_lower):
                        target_idx = i
                if target_idx is None:
                    continue

                prompt = PROMPT_TMPL.format(
                    answer=ex["answer"], english=ex["english"],
                    cluster_order=" -> ".join(cluster_words),
                    chunk=chunks[target_idx]["chunk"],
                )
                accepted_reason = None
                for attempt in range(1, 4):
                    try:
                        candidate = call(prompt)
                    except Exception as e:
                        print(f"id={id_} attempt={attempt} error: {e}")
                        time.sleep(2)
                        continue
                    if not candidate:
                        continue
                    # verify the enriched reason against ground truth before
                    # trusting it -- catches cases like claiming "will before
                    # werden" when the true subordinate-clause order reverses
                    # the main-clause modal+infinitive pattern
                    trial_chunks = [dict(c) for c in chunks]
                    trial_chunks[target_idx]["reason"] = candidate
                    mistakes = check_explanation(ex, trial_chunks)
                    if not mistakes:
                        accepted_reason = candidate
                        break
                    print(f"id={id_} attempt={attempt} enriched reason failed verification: {mistakes[0]['claim']} (actual: {mistakes[0]['actual']})")
                    time.sleep(1)

                if accepted_reason:
                    new_chunks[target_idx]["reason"] = accepted_reason
                else:
                    print(f"id={id_} could not produce a verified enrichment after retries, keeping original reason")

            out_f.write(json.dumps({"id": id_, "chunks": new_chunks}, ensure_ascii=False) + "\n")
            out_f.flush()
            n_done += 1
            print(f"id={id_} enriched ({n_done}/{len(ids)})")

    print(f"done: enriched {n_done}")


if __name__ == "__main__":
    main()
