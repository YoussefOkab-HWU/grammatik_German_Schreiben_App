import json, time, requests, re, sys

MODEL = "mistral-small"
OLLAMA_URL = "http://localhost:11434/api/generate"
SRC = "./exercises.jsonl"
CANDIDATES = "./all_idioms_detected.jsonl"
PASS3 = "./idiom_candidates_verified_pass3.jsonl"
OUT = "./idiom_candidates_verified_pass4.jsonl"
LOG = "./verify_idioms_pass4.log"

BATCH_SIZE = 10

# fourth pass -- pass 3 still let through direct compositional matches:
# "das Zimmer lueften" (lueften=air out), "den Wein probieren" (probieren=
# taste/try), "die Wohnung tauschen" (tauschen=exchange), "an der Loesung
# arbeiten" (arbeiten an=work on -- same preposition as English!), "den
# Wasserzaehler ablesen" (ablesen=read off), "um den Block laufen" (laufen=
# walk/run, um=around) -- in every one of these the CORE VERB's single most
# common dictionary meaning already IS the English gloss's verb. Force that
# comparison explicitly instead of a holistic judgment call, which is where
# the model keeps being too lenient. Also reject candidates where the phrase
# doesn't actually match the words present in the sentence (garbled
# extraction) or the sentence itself looks structurally broken.
PROMPT_TMPL = """Final, mechanical check on German idiom candidates. For EACH one, do this explicitly:
STEP 1: What is the single most common English dictionary meaning of the core verb, on its own (ignore the object/preposition)?
STEP 2: Does that meaning already match (or closely synonym-match) the verb used in the given English gloss?
STEP 3: If yes -> REJECT (it's compositional, not idiomatic -- knowing the verb's normal meaning is enough to understand the phrase). If no, the core verb's normal meaning is clearly different from the gloss -> ACCEPT.

Examples of REJECT (core verb's normal meaning already matches the gloss):
- "lueften" normally means "to air out/ventilate" -> "das Zimmer lueften" = "to air out the room": SAME meaning -> REJECT
- "probieren" normally means "to try/taste" -> "den Wein probieren" = "to taste the wine": SAME meaning -> REJECT
- "tauschen" normally means "to exchange/swap" -> "die Wohnung tauschen" = "to exchange the apartment": SAME meaning -> REJECT
- "arbeiten an" normally means "to work on" (same preposition as English!) -> REJECT
- "ablesen" normally means "to read off" -> "den Wasserzaehler ablesen" = "to read the water meter": SAME -> REJECT

Examples of ACCEPT (core verb's normal meaning is clearly different from the gloss):
- "machen" normally means "to make/do", NOT "to go" -> "Urlaub machen" = "to go on vacation": DIFFERENT -> ACCEPT
- "liegen" normally means "to lie (down)", NOT "to matter" -> "am Herzen liegen" = "to matter a lot": DIFFERENT -> ACCEPT
- "treiben" normally means "to drive/propel", NOT "to do/practice" -> "Sport treiben" = "to do sports": DIFFERENT -> ACCEPT

Also REJECT if the given phrase's words don't actually appear together the way claimed in the sentence (garbled/mismatched extraction), or if the sentence itself looks grammatically broken/nonsensical.

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

    pass3 = [json.loads(l) for l in open(PASS3)]
    survivors = [r for r in pass3 if r.get("genuinely_idiomatic")]
    log(f"pass-3 survivors: {len(survivors)}")

    done_ids = set()
    if __import__("os").path.exists(OUT):
        for l in open(OUT):
            l = l.strip()
            if l:
                done_ids.add(json.loads(l)["id"])

    remaining = [c for c in survivors if c["id"] not in done_ids]
    log(f"=== starting pass 4: {len(done_ids)} already done, {len(remaining)} remaining ===")

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
