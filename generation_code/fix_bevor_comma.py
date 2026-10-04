import json, re, sys

SRC = "./exercises.jsonl"

# German requires a comma before a subordinate clause introduced by "bevor"
# regardless of clause order -- this was already correctly done when "bevor"
# starts the whole sentence, but 83 exercises have "bevor" mid-sentence with
# no comma, because its clause was never split into its own gap: it got
# lumped into whatever gap already held the PRECEDING subordinate clause.
# Fix: split that gap at "bevor", moving it (and everything after it in that
# gap) into a brand new gap, shifting every later gap up by one, and
# inserting a new "," skeleton token at the split point.


def find_bevor_chip(ex):
    for c in ex["chips"]:
        if c["type"] == "bare_noun" and c["answer"].lower() == "bevor":
            return c
    return None


def needs_fix(ex):
    ans = ex["answer"]
    m = re.search(r"\bbevor\b", ans, re.IGNORECASE)
    if not m or m.start() == 0:
        return False
    preceding = ans[:m.start()].rstrip()
    return not preceding.endswith(",")


def apply_fix(ex):
    bchip = find_bevor_chip(ex)
    if not bchip:
        return False
    g, o = bchip["correct_gap"], bchip["order"]

    for c in ex["chips"]:
        if c["correct_gap"] == g and c["order"] >= o:
            c["correct_gap"] = g + 1
            c["order"] = c["order"] - o
        elif c["correct_gap"] > g:
            c["correct_gap"] = c["correct_gap"] + 1

    ex["skeleton"] = ex["skeleton"][:g] + [{"type": "text", "display": ",", "answer": ","}] + ex["skeleton"][g:]

    ans = ex["answer"]
    m = re.search(r"\bbevor\b", ans, re.IGNORECASE)
    ex["answer"] = ans[:m.start()].rstrip() + ", " + ans[m.start():]

    # a handful of these were also missing a trailing period entirely (no
    # skeleton punctuation at all, sentence just stops) -- safe, generic fix
    # regardless of the bevor-comma issue: every complete sentence needs one.
    if not ex["skeleton"] or ex["skeleton"][-1]["answer"] != ".":
        ex["skeleton"].append({"type": "text", "display": ".", "answer": "."})
        ex["answer"] = ex["answer"].rstrip() + "."
    return True


def main():
    exercises = [json.loads(l) for l in open(SRC)]
    do_apply = len(sys.argv) > 1 and sys.argv[1] == "apply"

    fixed_ids = []
    for ex in exercises:
        if needs_fix(ex):
            old_answer = ex["answer"]
            if apply_fix(ex):
                fixed_ids.append((ex["id"], old_answer, ex["answer"]))

    print(f"{'applied' if do_apply else 'would apply'} fix to {len(fixed_ids)} exercises")
    for id_, old, new in fixed_ids[:10]:
        print(f"  id={id_}\n    old: {old}\n    new: {new}")

    if do_apply:
        with open(SRC, "w") as f:
            for ex in exercises:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        print("wrote", SRC)
        with open("./bevor_fixed_ids.json", "w") as f:
            json.dump([i for i, _, _ in fixed_ids], f)
        print("wrote list of fixed ids to bevor_fixed_ids.json")


if __name__ == "__main__":
    main()
