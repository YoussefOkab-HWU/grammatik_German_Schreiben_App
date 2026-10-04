import json, time, requests, re, sys

MODEL = "mistral-small"
OLLAMA_URL = "http://localhost:11434/api/generate"
SRC = "./exercises.jsonl"
EXPL = "./explanations.js"
CANDIDATES = "./all_idioms_detected.jsonl"
PASS4 = "./idiom_candidates_verified_pass4.jsonl"
PATCHES_OUT = "./explanations_all_idioms_patches.jsonl"

PROMPT_TMPL = """You previously explained part of a German sentence for a B1 learner, but missed an important vocabulary point.

Full German sentence: {answer}
The chunk in question: "{chunk}"
Your original reason: "{old_reason}"

"{phrase}" is a FIXED idiom/collocation meaning "{gloss}" -- a learner translating it word-for-word would get the wrong meaning. This must be memorized as a unit, not built up from the individual words' normal meanings.

Rewrite the reason for this chunk (2-3 sentences, same teaching style as before) to explicitly call out that "{phrase}" is a fixed phrase meaning "{gloss}", while keeping any useful case/word-order content from your original reason.

Respond with ONLY the corrected reason text. No JSON, no quotes, no markdown, no extra commentary.
"""


def call(prompt, timeout=120):
    r = requests.post(OLLAMA_URL, json={
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.2}
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()["response"].strip().strip('"')


def find_target_chunk(chunks, phrase_words, used):
    best = None
    best_overlap = 0
    for c in chunks:
        if id(c) in used:
            continue
        chunk_words = set(re.findall(r"[a-zA-ZäöüßÄÖÜ]+", c["chunk"].lower()))
        overlap = len(chunk_words & phrase_words)
        if overlap > best_overlap:
            best_overlap = overlap
            best = c
    return best if best_overlap > 0 else None


def verify(new_reason):
    low = new_reason.lower()
    has_fixed = "fixed" in low
    has_phrase_word = re.search(r"phrase|expression|idiom|collocation", low) is not None
    return has_fixed and has_phrase_word


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != "apply" else None

    exercises = [json.loads(l) for l in open(SRC)]
    answers = {ex["id"]: ex["answer"] for ex in exercises}
    expl = json.loads(open(EXPL).read()[len("const EXPLANATIONS = "):-1])
    candidates_by_id = {json.loads(l)["id"]: json.loads(l) for l in open(CANDIDATES)}

    pass4 = [json.loads(l) for l in open(PASS4)]
    confirmed_ids = [r["id"] for r in pass4 if r.get("genuinely_idiomatic")]
    if limit:
        confirmed_ids = confirmed_ids[:limit]

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

    n_done = n_no_chunk = n_failed = 0
    with open(PATCHES_OUT, "a", buffering=1) as out_f:
        for id_ in confirmed_ids:
            chunks = expl.get(str(id_))
            if not chunks:
                continue
            cand = candidates_by_id[id_]
            phrase, gloss = cand["idiom_phrase"], cand["gloss"]
            phrase_words = set(w.lower() for w in re.findall(r"[a-zA-ZäöüßÄÖÜ]+", phrase))
            target = find_target_chunk(chunks, phrase_words, set())
            if not target:
                n_no_chunk += 1
                continue
            if (id_, target["chunk"]) in already_done:
                continue

            prompt = PROMPT_TMPL.format(
                answer=answers[id_], chunk=target["chunk"], old_reason=target["reason"],
                phrase=phrase, gloss=gloss,
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
                    "id": id_, "chunk": target["chunk"],
                    "old_reason": target["reason"], "new_reason": accepted,
                }, ensure_ascii=False) + "\n")
                out_f.flush()
                n_done += 1
                print(f"id={id_} ({phrase!r}) enriched ({n_done})")
            else:
                n_failed += 1
                print(f"id={id_} could not produce a verified enrichment after retries")

    print(f"done: enriched {n_done}, failed {n_failed}, no matching chunk {n_no_chunk}")


if __name__ == "__main__":
    main()
