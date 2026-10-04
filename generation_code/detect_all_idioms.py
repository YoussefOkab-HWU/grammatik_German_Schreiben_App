import json, time, requests, re, sys

MODEL = "mistral-small"
OLLAMA_URL = "http://localhost:11434/api/generate"
SRC = "./exercises.jsonl"
OUT = "./all_idioms_detected.jsonl"
LOG = "./detect_all_idioms.log"

BATCH_SIZE = 12

PROMPT_TMPL = """You are reviewing German sentences for a B1 grammar app. For EACH sentence below, decide if it contains a FIXED IDIOM or COLLOCATION that a learner must memorize as a whole unit -- where the meaning is not obvious from translating the words literally/individually. This includes:
- verb + preposition idioms (warten auf, sich freuen auf, bitten um)
- verb + fixed phrase idioms (am Herzen liegen = "to matter a lot to someone", literally "to lie at the heart")
- noun + verb collocations (einen Spaziergang machen = "to take a walk", Urlaub machen = "to go on vacation", eine Entscheidung treffen = "to make a decision", Angst haben = "to be afraid", Recht haben = "to be right")

Do NOT flag ordinary compositional phrases where the literal translation already makes sense (e.g. "ein Buch lesen" = "to read a book" -- not idiomatic, skip it).

Sentences:
{items}

Respond ONLY with a JSON array, one element per sentence IN ORDER, no markdown fences, no extra text. Each element: {{"id": <id>, "has_idiom": true|false, "idiom_phrase": "the exact fixed phrase as it appears in the sentence, or null", "gloss": "short English meaning, or null"}}
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
    exercises = [json.loads(l) for l in open(SRC)]
    total = len(exercises)

    done_ids = set()
    if __import__("os").path.exists(OUT):
        for l in open(OUT):
            l = l.strip()
            if not l:
                continue
            try:
                done_ids.add(json.loads(l)["id"])
            except Exception:
                pass

    remaining = [ex for ex in exercises if ex["id"] not in done_ids]
    log(f"=== starting run: {len(done_ids)}/{total} already done, {len(remaining)} remaining ===")

    processed = 0
    t_start = time.time()

    with open(OUT, "a", buffering=1) as out_f:
        for i in range(0, len(remaining), BATCH_SIZE):
            batch = remaining[i:i + BATCH_SIZE]
            items = "\n".join(f'{{"id": {ex["id"]}}}: "{ex["answer"]}"' for ex in batch)
            prompt = PROMPT_TMPL.format(items=items)

            result = None
            for attempt in range(1, 3):
                try:
                    text = call(prompt)
                    data = parse(text)
                    by_id = {d["id"]: d for d in data if "id" in d}
                    if all(ex["id"] in by_id for ex in batch):
                        result = data
                        break
                except Exception as e:
                    log(f"batch starting id={batch[0]['id']} attempt={attempt} error: {e}")
                    time.sleep(2)

            if result is None:
                log(f"batch starting id={batch[0]['id']} FAILED after retries, marking all as no-idiom to avoid retry loop")
                result = [{"id": ex["id"], "has_idiom": False, "idiom_phrase": None, "gloss": None} for ex in batch]

            for d in result:
                out_f.write(json.dumps(d, ensure_ascii=False) + "\n")
            processed += len(batch)

            if processed % (BATCH_SIZE * 10) == 0 or i == 0:
                elapsed = time.time() - t_start
                rate = processed / elapsed if elapsed > 0 else 0
                remaining_count = len(remaining) - processed
                eta_hours = (remaining_count / rate) / 3600 if rate > 0 else float("inf")
                log(f"progress: {len(done_ids) + processed}/{total} | this run: {processed}/{len(remaining)} in {elapsed/3600:.2f}h | rate: {rate*3600:.0f}/h | ETA: {eta_hours:.1f}h")

    log(f"=== DONE: {len(done_ids) + processed}/{total} ===")


if __name__ == "__main__":
    main()
