import json, time, requests, sys

MODEL = "mistral-small"
OLLAMA_URL = "http://localhost:11434/api/generate"
SRC = "./exercises.jsonl"
BAD_CASE_IN = "./bad_case_ids.jsonl"
PATCHES_OUT = "./explanations_case_patches.jsonl"

CASE_NAME = {"Acc": "accusative", "Dat": "dative", "Gen": "genitive", "Nom": "nominative"}

PROMPT_TMPL = """You previously explained part of a German sentence for a B1 learner, but made a factual error about grammatical case.

Full German sentence: {answer}
The chunk in question: "{chunk}"
Your original (INCORRECT) reason: "{old_reason}"

The correct case here is {correct_case} -- your original reason stated the wrong case. Rewrite ONLY the reason for this chunk, correcting the case, in 1-2 sentences, same teaching style as before, mentioning why {correct_case} is correct.

Respond with ONLY the corrected reason text. No JSON, no quotes, no extra commentary, no markdown.
"""

def call(prompt, timeout=120):
    r = requests.post(OLLAMA_URL, json={
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.2}
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()["response"].strip().strip('"')

def main():
    answers = {}
    for l in open(SRC):
        ex = json.loads(l)
        answers[ex["id"]] = ex["answer"]

    bad = [json.loads(l) for l in open(BAD_CASE_IN) if l.strip()]
    print(f"fixing case errors in {len(bad)} flagged exercises")

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
    if already_done:
        print(f"resuming: {len(already_done)} patches already done, skipping those")

    n_patches = 0
    with open(PATCHES_OUT, "a", buffering=1) as out_f:
        for rec in bad:
            id_ = rec["id"]
            for m in rec["mistakes"]:
                if (id_, m["chunk"]) in already_done:
                    continue
                prompt = PROMPT_TMPL.format(
                    answer=answers[id_],
                    chunk=m["chunk"],
                    old_reason=m["reason"],
                    correct_case=CASE_NAME[m["expected_case"]],
                )
                new_reason = None
                for attempt in range(1, 3):
                    try:
                        new_reason = call(prompt)
                        if new_reason:
                            break
                    except Exception as e:
                        print(f"id={id_} chunk={m['chunk']!r} attempt={attempt} error: {e}")
                        time.sleep(2)
                if not new_reason:
                    print(f"id={id_} chunk={m['chunk']!r} FAILED, skipping")
                    continue
                out_f.write(json.dumps({
                    "id": id_, "chunk": m["chunk"],
                    "old_reason": m["reason"], "new_reason": new_reason,
                }, ensure_ascii=False) + "\n")
                out_f.flush()
                n_patches += 1
                print(f"id={id_} patched chunk={m['chunk']!r}")

    print(f"done: wrote {n_patches} patches to {PATCHES_OUT}")

if __name__ == "__main__":
    main()
