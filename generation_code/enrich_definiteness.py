import json, time, requests, re, sys

MODEL = "mistral-small"
OLLAMA_URL = "http://localhost:11434/api/generate"
SRC = "./exercises.jsonl"
EXPL = "./explanations.js"
CANDIDATES = "./definiteness_candidates.json"
PATCHES_OUT = "./explanations_definiteness_patches.jsonl"

PROMPT_TMPL = """You previously explained part of a German sentence for a B1 learner, but missed an important word-order rule.

Full German sentence: {answer}
The chunk in question: "{chunk}"
Your original reason: "{old_reason}"

This chunk contains the noun phrase "{np_text}", which is grammatically {definiteness}. In German, {definiteness} objects like this sit {relation} a free adverbial like "{adverbial_word}" in the middle field of the sentence -- the general rule is: definite objects come BEFORE Tekamolo-style adverbials (temporal/causal/modal/local expressions), while indefinite objects come AFTER them.

Rewrite the reason for this chunk (2-3 sentences, same teaching style as before) to explicitly state that "{np_text}" is {definiteness} and that this is why it sits {relation} "{adverbial_word}".

Respond with ONLY the corrected reason text. No JSON, no quotes, no markdown, no extra commentary.
"""


def call(prompt, timeout=120):
    r = requests.post(OLLAMA_URL, json={
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.2}
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()["response"].strip().strip('"')


def find_target_chunk(chunks, noun_word):
    for c in chunks:
        words = re.findall(r"[a-zA-ZäöüßÄÖÜ]+", c["chunk"])
        if noun_word in words:
            return c
    return None


def verify(new_reason, definiteness):
    # word-boundary aware: "indefinite" contains "definite" as a substring
    low = new_reason.lower()
    has_indef = re.search(r"\bindefinite\b", low) is not None
    has_def = re.search(r"\bdefinite\b", low) is not None and not has_indef
    if definiteness == "indefinite":
        return has_indef
    return has_def


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != "apply" else None
    do_apply = "apply" in sys.argv

    answers = {}
    for l in open(SRC):
        ex = json.loads(l)
        answers[ex["id"]] = ex["answer"]

    expl = json.loads(open(EXPL).read()[len("const EXPLANATIONS = "):-1])
    candidates = json.load(open(CANDIDATES))
    if limit:
        candidates = candidates[:limit]

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

    print(f"processing {len(candidates)} candidates ({len(already_done)} chunk-patches already done, will skip those)")

    n_done = n_skipped_no_chunk = n_failed = 0
    with open(PATCHES_OUT, "a", buffering=1) as out_f:
        for cand in candidates:
            id_ = cand["id"]
            chunks = expl.get(str(id_))
            if not chunks:
                continue
            for obj in cand["objects"]:
                noun_word = obj["noun"]
                if not noun_word:
                    continue
                target = find_target_chunk(chunks, noun_word)
                if not target:
                    n_skipped_no_chunk += 1
                    continue
                if (id_, target["chunk"]) in already_done:
                    continue

                definiteness = "definite" if obj["definite"] else "indefinite"
                np_text = f"{obj['article_answer']} {noun_word}" if obj["article_answer"] else noun_word
                prompt = PROMPT_TMPL.format(
                    answer=answers[id_], chunk=target["chunk"], old_reason=target["reason"],
                    np_text=np_text, definiteness=definiteness,
                    relation=obj["relation"], adverbial_word=obj["adverbial_word"],
                )
                accepted = None
                for attempt in range(1, 4):
                    try:
                        candidate_text = call(prompt)
                    except Exception as e:
                        print(f"id={id_} attempt={attempt} error: {e}")
                        time.sleep(2)
                        continue
                    if candidate_text and verify(candidate_text, definiteness):
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
                    print(f"id={id_} enriched ({n_done})")
                else:
                    n_failed += 1
                    print(f"id={id_} could not produce a verified enrichment after retries")

    print(f"done: enriched {n_done}, failed {n_failed}, skipped (no matching chunk) {n_skipped_no_chunk}")


if __name__ == "__main__":
    main()
