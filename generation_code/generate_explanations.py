import json, requests, time, re, sys, os

MODEL = "mistral-small"
OLLAMA_URL = "http://localhost:11434/api/generate"
SRC = "./exercises.jsonl"
OUT = "./explanations.jsonl"
LOG = "./explanations_progress.log"

PROMPT_TMPL = """You are a German grammar teacher explaining word order to a B1 English-speaking learner.

German sentence: {answer}
English meaning: {english}

Break the German sentence into its natural phrase-chunks, in left-to-right order, exactly as they appear. For EACH chunk, give a SHORT, SPECIFIC reason for why it sits in that exact position and (if it's a preposition+noun chunk) why that specific preposition and case are used there -- not a generic label like "Temporal" or "Object", but the actual grammatical reasoning a teacher would say out loud (e.g. "vor + Dative here means 'ago' when counting back from now, not 'in front of', which is why Stunden is dative not accusative" or "the finite verb bin must be the second overall element in a main clause, right after the subject Ich").

Respond ONLY with a JSON array, no other text, no markdown fences. Each element: {{"chunk": "the exact German text of this chunk", "reason": "the specific explanation, 1-2 sentences"}}

Chunks must together reconstruct the full sentence in order (including punctuation attached to the last chunk is fine to omit).
"""

def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def gen_raw(ex, timeout=180):
    prompt = PROMPT_TMPL.format(answer=ex["answer"], english=ex["english"])
    r = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2}
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()["response"]

def parse_chunks(text):
    cleaned = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    data = json.loads(cleaned)
    assert isinstance(data, list) and len(data) > 0
    for item in data:
        assert "chunk" in item and "reason" in item
    return data

def main():
    exercises = [json.loads(l) for l in open(SRC)]
    total = len(exercises)

    done_ids = set()
    if os.path.exists(OUT):
        for l in open(OUT):
            l = l.strip()
            if not l:
                continue
            try:
                done_ids.add(json.loads(l)["id"])
            except Exception:
                pass

    log(f"=== starting run: {len(done_ids)}/{total} already done, {total - len(done_ids)} remaining ===")

    remaining = [ex for ex in exercises if ex["id"] not in done_ids]
    processed_this_run = 0
    t_start = time.time()

    with open(OUT, "a", buffering=1) as out_f:
        for ex in remaining:
            attempt = 0
            result = None
            while attempt < 2 and result is None:
                attempt += 1
                try:
                    text = gen_raw(ex)
                    chunks = parse_chunks(text)
                    result = {"id": ex["id"], "chunks": chunks}
                except Exception as e:
                    log(f"WARN id={ex['id']} attempt={attempt} failed: {e}")
                    time.sleep(2)
            if result is None:
                result = {"id": ex["id"], "chunks": None, "error": "failed after retries"}
                log(f"ERROR id={ex['id']} giving up after retries, recording as failed")

            out_f.write(json.dumps(result, ensure_ascii=False) + "\n")
            out_f.flush()
            processed_this_run += 1
            done_count = len(done_ids) + processed_this_run

            if processed_this_run % 10 == 0 or processed_this_run == 1:
                elapsed = time.time() - t_start
                rate = processed_this_run / elapsed
                remaining_count = total - done_count
                eta_hours = (remaining_count / rate) / 3600 if rate > 0 else float("inf")
                pct = 100 * done_count / total
                log(f"progress: {done_count}/{total} ({pct:.2f}%) | this run: {processed_this_run} in {elapsed/3600:.2f}h | "
                    f"rate: {rate*3600:.1f}/h | ETA remaining: {eta_hours:.1f}h")

    log(f"=== DONE: {len(done_ids) + processed_this_run}/{total} ===")

if __name__ == "__main__":
    main()
