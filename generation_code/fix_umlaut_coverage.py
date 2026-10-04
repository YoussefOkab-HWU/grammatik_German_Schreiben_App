import json, re

SRC = "./exercises.jsonl"
OUT = "./explanations.jsonl"
FIXES = "./explanations_fixes.jsonl"
BAD_IDS_IN = "./bad_ids.jsonl"

def deumlaut(w):
    return w.replace("ä", "a").replace("ö", "o").replace("ü", "u")

def words(s):
    return re.findall(r"[a-zA-ZäöüßÄÖÜ]+", s.lower())

def try_fix_umlaut(answer, chunks):
    """If every chunk's text, word-for-word, only differs from the true
    answer by umlaut characters (ä/ö/ü flattened to a/o/u), restore the
    correct spelling directly -- no LLM needed, this is a deterministic
    text substitution, not a judgment call."""
    a_words = words(answer)
    r_words_per_chunk = [re.findall(r"[a-zA-ZäöüßÄÖÜ]+", c["chunk"]) for c in chunks]
    flat_r_words = [w for chunk_words in r_words_per_chunk for w in chunk_words]
    if len(a_words) != len(flat_r_words):
        return None
    if not all(deumlaut(a) == deumlaut(r.lower()) for a, r in zip(a_words, flat_r_words)):
        return None
    if a_words == [w.lower() for w in flat_r_words]:
        return None  # not actually a mismatch

    new_chunks = []
    a_idx = 0
    for c, chunk_words in zip(chunks, r_words_per_chunk):
        new_text = c["chunk"]
        for w in chunk_words:
            correct = a_words[a_idx]
            if w.lower() != correct:
                # replace this exact occurrence, preserving surrounding text/case pattern
                if w[0].isupper():
                    correct = correct[0].upper() + correct[1:]
                new_text = re.sub(re.escape(w), correct, new_text, count=1)
            a_idx += 1
        new_chunks.append({"chunk": new_text, "reason": c["reason"]})
    return new_chunks

def main():
    answers = {}
    for l in open(SRC):
        ex = json.loads(l)
        answers[ex["id"]] = ex["answer"]

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

    bad_ids = [json.loads(l)["id"] for l in open(BAD_IDS_IN) if l.strip()]

    fixed = 0
    with open(FIXES, "a", buffering=1) as out_f:
        for id_ in bad_ids:
            rec = latest.get(id_)
            if not rec or not rec.get("chunks"):
                continue
            new_chunks = try_fix_umlaut(answers[id_], rec["chunks"])
            if new_chunks is None:
                continue
            out_f.write(json.dumps({"id": id_, "chunks": new_chunks}, ensure_ascii=False) + "\n")
            out_f.flush()
            fixed += 1
            print(f"id={id_} umlaut-fixed (no LLM call needed)")

    print(f"done: fixed {fixed} via direct umlaut substitution")

if __name__ == "__main__":
    main()
