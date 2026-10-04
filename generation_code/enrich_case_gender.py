import json, time, requests, re, sys

MODEL = "mistral-small"
OLLAMA_URL = "http://localhost:11434/api/generate"
SRC = "./exercises.jsonl"
EXPL = "./explanations.js"
PATCHES_OUT = "./explanations_case_gender_patches.jsonl"

GENDER_WORDS = {"Masc": "masculine", "Fem": "feminine", "Neut": "neuter", "Plur": "plural"}
CASE_WORDS = {"Nom": "nominative", "Acc": "accusative", "Dat": "dative", "Gen": "genitive"}

PROMPT_TMPL = """You previously explained part of a German sentence for a B1 learner, but didn't explicitly state the grammatical case and gender of a noun phrase in it.

Full German sentence: {answer}
Chunk: "{chunk}"
Your original reason: "{old_reason}"

The noun phrase "{np_text}" is {gender} and in the {case} case. Rewrite the reason (2-3 sentences, same teaching style as before) to explicitly state that '{noun}' is {gender} and {case}, while keeping the useful content from your original reason.

Respond with ONLY the corrected reason text. No JSON, no quotes, no markdown, no extra commentary.
"""


def call(prompt, timeout=120):
    r = requests.post(OLLAMA_URL, json={
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.2}
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()["response"].strip().strip('"')


def effective_gender(article):
    # a Plur number always wins over whatever the gender field says -- German
    # plural nouns aren't masculine/feminine/neuter for agreement purposes,
    # they're just plural, but the corpus sometimes leaks the noun's lexical
    # singular gender into plural entries (same bug class as "den Kuchen").
    if article.get("number") == "Plur":
        return "Plur"
    return article.get("gender")


def effective_gender_case(chip):
    """Same either/or as chunkBadges() in index.html: a chip with a real
    article uses it; an article-less noun phrase (mass nouns like "viel
    Platz", or a bare object like "zwei Zimmern") carries gender/case
    directly on the chip itself instead."""
    art = chip.get("article")
    if art:
        return effective_gender(art), art.get("case")
    if chip.get("number") == "Plur":
        return "Plur", chip.get("case")
    return chip.get("gender"), chip.get("case")


def verify(new_reason, gender, case):
    low = new_reason.lower()
    has_gender = re.search(r"\b" + GENDER_WORDS[gender] + r"\b", low) is not None
    has_case = re.search(r"\b" + CASE_WORDS[case] + r"\b", low) is not None
    return has_gender and has_case


def find_target_chunk(chunks, noun_word, used_chunk_texts):
    for c in chunks:
        if id(c) in used_chunk_texts:
            continue
        words = re.findall(r"[a-zA-ZäöüßÄÖÜ]+", c["chunk"])
        if noun_word in words:
            return c
    return None


def build_candidates(exercises, expl, limit=None):
    candidates = []
    for ex in exercises:
        chunks = expl.get(str(ex["id"]))
        if not chunks:
            continue
        used = set()
        for c in ex["chips"]:
            if c["type"] != "noun_phrase" or not c.get("noun"):
                continue
            gender, case = effective_gender_case(c)
            if not gender or not case:
                continue
            target = find_target_chunk(chunks, c["noun"], used)
            if not target:
                continue
            reason_low = target["reason"].lower()
            has_gender = re.search(r"\b" + GENDER_WORDS[gender] + r"\b", reason_low) is not None
            has_case = re.search(r"\b" + CASE_WORDS[case] + r"\b", reason_low) is not None
            if has_gender and has_case:
                continue
            used.add(id(target))
            art = c.get("article")
            candidates.append({
                "id": ex["id"], "chunk": target["chunk"], "reason": target["reason"],
                "noun": c["noun"], "article_answer": art.get("answer") if art else None,
                "gender": gender, "case": case,
            })
            if limit and len(candidates) >= limit:
                return candidates
    return candidates


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != "apply" else None
    do_apply = "apply" in sys.argv

    answers = {}
    exercises = []
    for l in open(SRC):
        ex = json.loads(l)
        exercises.append(ex)
        answers[ex["id"]] = ex["answer"]

    expl = json.loads(open(EXPL).read()[len("const EXPLANATIONS = "):-1])

    print("scanning for candidates..." + (f" (limit {limit})" if limit else ""))
    candidates = build_candidates(exercises, expl, limit=limit)
    print(f"found {len(candidates)} candidate chunks to enrich")

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

    n_done = n_failed = 0
    t_start = time.time()
    with open(PATCHES_OUT, "a", buffering=1) as out_f:
        for cand in candidates:
            if (cand["id"], cand["chunk"]) in already_done:
                continue
            np_text = f"{cand['article_answer']} {cand['noun']}" if cand["article_answer"] else cand["noun"]
            prompt = PROMPT_TMPL.format(
                answer=answers[cand["id"]], chunk=cand["chunk"], old_reason=cand["reason"],
                np_text=np_text, noun=cand["noun"], gender=GENDER_WORDS[cand["gender"]], case=CASE_WORDS[cand["case"]],
            )
            accepted = None
            for attempt in range(1, 4):
                try:
                    text = call(prompt)
                except Exception as e:
                    print(f"id={cand['id']} attempt={attempt} error: {e}")
                    time.sleep(2)
                    continue
                if text and verify(text, cand["gender"], cand["case"]):
                    accepted = text
                    break
                time.sleep(1)

            if accepted:
                out_f.write(json.dumps({
                    "id": cand["id"], "chunk": cand["chunk"],
                    "old_reason": cand["reason"], "new_reason": accepted,
                }, ensure_ascii=False) + "\n")
                out_f.flush()
                n_done += 1
                elapsed = time.time() - t_start
                rate = n_done / elapsed if elapsed > 0 else 0
                print(f"id={cand['id']} enriched ({n_done}) | {elapsed/n_done:.1f}s/item avg")
            else:
                n_failed += 1
                print(f"id={cand['id']} could not produce a verified enrichment after retries")

    print(f"done: enriched {n_done}, failed {n_failed}")


if __name__ == "__main__":
    main()
