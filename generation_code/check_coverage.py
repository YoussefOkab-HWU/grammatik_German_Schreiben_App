import json, re, sys

SRC = "./exercises.jsonl"
OUT = "./explanations.jsonl"
FIXES = "./explanations_fixes.jsonl"
BAD_IDS_OUT = "./bad_ids.jsonl"

def words(s):
    return re.findall(r"[a-zA-ZäöüßÄÖÜ]+", s.lower())

def check_one(answer, chunks):
    if chunks is None:
        return "generation_failed"
    reconstructed = " ".join(c["chunk"] for c in chunks)
    if words(answer) != words(reconstructed):
        return "coverage_mismatch"
    return None

def main():
    answers = {}
    for l in open(SRC):
        ex = json.loads(l)
        answers[ex["id"]] = ex["answer"]

    # last line wins per id, in case of duplicate entries from earlier fix passes
    latest = {}
    for l in open(OUT):
        l = l.strip()
        if not l:
            continue
        rec = json.loads(l)
        latest[rec["id"]] = rec

    # apply the fix-pass overlay on top -- otherwise an id that was already
    # successfully fixed keeps getting re-flagged forever, since the fix is
    # never written back into explanations.jsonl itself, and fix_coverage.py
    # would redo the (expensive, GPU-bound) fix from scratch every cycle
    try:
        for l in open(FIXES):
            l = l.strip()
            if not l:
                continue
            rec = json.loads(l)
            latest[rec["id"]] = rec
    except FileNotFoundError:
        pass

    bad = []
    for id_, rec in latest.items():
        reason = check_one(answers[id_], rec.get("chunks"))
        if reason:
            bad.append({"id": id_, "reason": reason})

    bad.sort(key=lambda b: b["id"])
    with open(BAD_IDS_OUT, "w") as f:
        for b in bad:
            f.write(json.dumps(b) + "\n")

    n_checked = len(latest)
    n_bad = len(bad)
    print(f"checked {n_checked} generated so far ({len(answers)} total in corpus)")
    print(f"bad: {n_bad} ({n_bad/n_checked*100:.2f}% of generated)" if n_checked else "bad: 0")
    reasons = {}
    for b in bad:
        reasons[b["reason"]] = reasons.get(b["reason"], 0) + 1
    for r, c in reasons.items():
        print(f"  {r}: {c}")
    print(f"wrote {n_bad} bad ids to {BAD_IDS_OUT}")

if __name__ == "__main__":
    main()
