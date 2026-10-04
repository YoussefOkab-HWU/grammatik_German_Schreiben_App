import json

SRC = "./exercises.jsonl"


def main():
    exercises = [json.loads(l) for l in open(SRC)]
    n_removed_empty = 0
    n_split = 0
    n_words_created = 0

    for ex in exercises:
        chips = ex["chips"]
        new_chips = []
        for c in chips:
            if c["type"] != "bare_noun" or c.get("answer") is None:
                new_chips.append(c)
                continue
            text = c["answer"].strip()
            if not text:
                # empty/whitespace-only chip -- a stray data artifact, drop it
                n_removed_empty += 1
                continue
            words = text.split()
            if len(words) <= 1:
                new_chips.append(c)
                continue
            # split into individual single-word bare_noun chips, bumping
            # every later chip in the same gap to make room
            for other in chips:
                if other is c:
                    continue
                if other["correct_gap"] == c["correct_gap"] and other["order"] > c["order"]:
                    other["order"] += len(words) - 1
            for i, w in enumerate(words):
                new_chips.append({
                    "type": "bare_noun",
                    "display": w,
                    "answer": w,
                    "correct_gap": c["correct_gap"],
                    "order": c["order"] + i,
                })
            n_split += 1
            n_words_created += len(words)

        ex["chips"] = new_chips

    # re-normalize order values to clean integers per gap
    for ex in exercises:
        by_gap = {}
        for c in ex["chips"]:
            by_gap.setdefault(c["correct_gap"], []).append(c)
        for gap, gap_chips in by_gap.items():
            gap_chips.sort(key=lambda c: c["order"])
            for i, c in enumerate(gap_chips):
                c["order"] = i

    print(f"removed {n_removed_empty} empty/whitespace bare_noun chips")
    print(f"split {n_split} multi-word bare_noun chips into {n_words_created} individual word chips")

    with open(SRC, "w") as f:
        for ex in exercises:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print("wrote", SRC)


if __name__ == "__main__":
    main()
