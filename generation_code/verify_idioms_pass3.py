import json, time, requests, re, sys

MODEL = "mistral-small"
OLLAMA_URL = "http://localhost:11434/api/generate"
SRC = "./exercises.jsonl"
CANDIDATES = "./all_idioms_detected.jsonl"
PASS2 = "./idiom_candidates_verified.jsonl"
OUT = "./idiom_candidates_verified_pass3.jsonl"
LOG = "./verify_idioms_pass3.log"

BATCH_SIZE = 15

# third pass -- even the strict second pass let through real noise:
# "die Wahrheit sagen" (tell the truth), "kommt aus" (come from), "die Zeit
# finden" (find the time -- English uses the SAME idiom), and garbled
# fragments grabbed mid-relative-clause ("immer gehorche", "gern folge")
# that aren't coherent lexical units at all. This pass targets those
# specific failure patterns directly.
PROMPT_TMPL = """Final strict check on German idiom candidates. Reject (false) for ANY of these reasons:
1. English also commonly uses the exact same idiom/phrasing, so word-for-word translation is NOT confusing (e.g. "die Zeit finden" = "find the time" -- English says this too; "Recht haben" ~ "have a point" is close enough in spirit).
2. It's still just ordinary vocabulary with a directly matching English verb (e.g. "die Wahrheit sagen" = "tell the truth", "kommt aus" = "come from", "das Zimmer aufräumen" = "tidy the room").
3. The "phrase" is a garbled or arbitrary fragment grabbed from the middle of a clause, not a coherent lexical unit on its own (e.g. "immer gehorche", "gern folge" -- these are just adverb+verb next to each other inside a relative clause, not a fixed expression).
4. It's a single ordinary reflexive verb like "sich fühlen", "sich irren" that a learner just memorizes as one vocabulary item, not a multi-word idiom.

Only ACCEPT (true) if it's a genuine, self-contained idiom/collocation where literal word-for-word translation would produce something an English speaker would find WRONG or surprising, AND the phrase is a coherent standalone lexical chunk (e.g. "warten auf", "am Herzen liegen", "einen Spaziergang machen", "Urlaub machen", "sich daran gewöhnen", "darauf aufmerksam machen", "Recht haben" where "have the right" would be actively misleading).

Candidates:
{items}

Respond ONLY with a JSON array, one element per candidate IN ORDER, no markdown fences, no extra text. Each element: {{"id": <id>, "genuinely_idiomatic": true|false}}
"""


def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def call(prompt, timeout=180):
    r = requests.post(OLLAMA_URL, json={
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.1}
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()["response"]


def parse(text):
    cleaned = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    data = json.loads(cleaned)
    assert isinstance(data, list)
    return data


def main():
    exercises = {json.loads(l)["id"]: json.loads(l) for l in open(SRC)}
    candidates_by_id = {json.loads(l)["id"]: json.loads(l) for l in open(CANDIDATES)}

    pass2 = [json.loads(l) for l in open(PASS2)]
    # only re-check items that survived pass 2 AND have a non-null gloss
    # (a null gloss on the original detection is itself a red flag)
    survivors = [r for r in pass2 if r.get("genuinely_idiomatic")
                 and candidates_by_id[r["id"]].get("gloss")]
    log(f"pass-2 survivors with a non-null gloss: {len(survivors)}")

    done_ids = set()
    if __import__("os").path.exists(OUT):
        for l in open(OUT):
            l = l.strip()
            if l:
                done_ids.add(json.loads(l)["id"])

    remaining = [c for c in survivors if c["id"] not in done_ids]
    log(f"=== starting pass 3: {len(done_ids)} already done, {len(remaining)} remaining ===")

    processed = 0
    t_start = time.time()

    with open(OUT, "a", buffering=1) as out_f:
        for i in range(0, len(remaining), BATCH_SIZE):
            batch = remaining[i:i + BATCH_SIZE]
            items = "\n".join(
                f'{{"id": {c["id"]}}}: phrase="{candidates_by_id[c["id"]]["idiom_phrase"]}" '
                f'gloss="{candidates_by_id[c["id"]]["gloss"]}" in sentence="{exercises[c["id"]]["answer"]}"'
                for c in batch
            )
            prompt = PROMPT_TMPL.format(items=items)

            result = None
            for attempt in range(1, 3):
                try:
                    text = call(prompt)
                    data = parse(text)
                    by_id = {d["id"]: d for d in data if "id" in d}
                    if all(c["id"] in by_id for c in batch):
                        result = data
                        break
                except Exception as e:
                    log(f"batch starting id={batch[0]['id']} attempt={attempt} error: {e}")
                    time.sleep(2)

            if result is None:
                log(f"batch starting id={batch[0]['id']} FAILED after retries, marking all as not-idiomatic (safe default)")
                result = [{"id": c["id"], "genuinely_idiomatic": False} for c in batch]

            for d in result:
                out_f.write(json.dumps(d, ensure_ascii=False) + "\n")
            processed += len(batch)

            if processed % (BATCH_SIZE * 10) == 0 or i == 0:
                elapsed = time.time() - t_start
                rate = processed / elapsed if elapsed > 0 else 0
                remaining_count = len(remaining) - processed
                eta_hours = (remaining_count / rate) / 3600 if rate > 0 else float("inf")
                log(f"progress: {len(done_ids) + processed}/{len(survivors)} | rate: {rate*3600:.0f}/h | ETA: {eta_hours:.1f}h")

    log(f"=== DONE: {len(done_ids) + processed}/{len(survivors)} ===")


if __name__ == "__main__":
    main()
