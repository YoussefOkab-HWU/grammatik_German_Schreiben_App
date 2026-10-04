import json, time, requests, re, sys

MODEL = "mistral-small"
OLLAMA_URL = "http://localhost:11434/api/generate"
SRC = "./exercises.jsonl"
CANDIDATES = "./all_idioms_detected.jsonl"
OUT = "./idiom_candidates_verified.jsonl"
LOG = "./verify_idioms.log"

BATCH_SIZE = 15

# stricter second pass: the first detection prompt was too permissive and
# flagged ordinary compositional verb+object phrases ("Geld spenden" = "to
# donate money", "die Steuer zahlen" = "to pay taxes") as if they were
# idioms, just because they're common collocations -- being a common
# collocation isn't the bar; being NON-LITERAL is.
PROMPT_TMPL = """You are strictly re-checking candidate German idioms flagged by a previous, overly permissive pass. For each one, answer: would translating it WORD-FOR-WORD into English produce something WRONG, CONFUSING, or NONSENSICAL -- not just "a different but equally natural verb choice"?

REJECT (answer false) if:
- It's an ordinary verb + direct object where the English translation uses an directly analogous verb (e.g. "Geld spenden" = "donate money", "die Steuer zahlen" = "pay the tax", "die Software aktualisieren" = "update the software", "das Ticket stornieren" = "cancel the ticket") -- these are NOT idioms, just normal vocabulary.
- It's just a prepositional phrase with a literal, predictable meaning (e.g. "nach dem Abendessen" = "after dinner", "an dem Strand" = "at the beach").
- It's a grammatical construction (passive voice, modal + infinitive) rather than a lexical phrase.
- The "phrase" is actually most of the whole sentence/clause, not a short lexical unit.

ACCEPT (answer true) only if a learner translating word-for-word would genuinely get it wrong or be confused (e.g. "warten auf" = "wait for" -- literal "wait on" is wrong in this sense; "Angst haben" = "to be afraid" -- literal "to have fear" is off; "am Herzen liegen" = "to matter a lot" -- literal "to lie at the heart" is baffling out of context; "einen Spaziergang machen" = "to take a walk" -- literal "to make a walk" is wrong).

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

    already_ids = set()
    for fname in ["explanations_idiom_patches.jsonl", "explanations_reflexive_dative_patches.jsonl", "explanations_verb_cluster_patches.jsonl"]:
        try:
            for l in open(f"./{fname}"):
                already_ids.add(json.loads(l)["id"])
        except FileNotFoundError:
            pass

    recs = [json.loads(l) for l in open(CANDIDATES)]
    candidates = [r for r in recs if r.get("has_idiom") and r.get("idiom_phrase")
                  and " " in r["idiom_phrase"].strip() and r["id"] not in already_ids]

    done_ids = set()
    if __import__("os").path.exists(OUT):
        for l in open(OUT):
            l = l.strip()
            if l:
                done_ids.add(json.loads(l)["id"])

    remaining = [c for c in candidates if c["id"] not in done_ids]
    log(f"=== starting verification: {len(candidates)} total candidates, {len(done_ids)} already done, {len(remaining)} remaining ===")

    processed = 0
    t_start = time.time()

    with open(OUT, "a", buffering=1) as out_f:
        for i in range(0, len(remaining), BATCH_SIZE):
            batch = remaining[i:i + BATCH_SIZE]
            items = "\n".join(
                f'{{"id": {c["id"]}}}: phrase="{c["idiom_phrase"]}" in sentence="{exercises[c["id"]]["answer"]}"'
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
                log(f"progress: {len(done_ids) + processed}/{len(candidates)} | rate: {rate*3600:.0f}/h | ETA: {eta_hours:.1f}h")

    log(f"=== DONE: {len(done_ids) + processed}/{len(candidates)} ===")


if __name__ == "__main__":
    main()
