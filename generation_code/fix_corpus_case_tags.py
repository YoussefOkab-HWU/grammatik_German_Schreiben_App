import json

SRC = "./exercises.jsonl"

# Manually verified via English translation (see conversation): these exercises
# tag a "den X" noun as dative-plural when the English confirms X is singular,
# meaning it's actually accusative-masculine-singular (identical surface form
# "den" for both readings is exactly why this got mistagged). Only the
# metadata (case/number) is wrong -- the actual answer text "den" is correct
# either way, so this fix touches labels only, not grading/text.
CONFIRMED_BUG_IDS = {
    71, 223, 558, 867, 909, 1051, 1314, 1395, 1572, 1630, 1653, 1743, 1766,
    1784, 1834, 2029, 2057, 2216, 2244, 2885, 3376, 3488, 3544, 4041, 4170,
    4253, 4473, 4492, 4825, 4833, 4893, 5054, 5741, 5948, 5988, 6226, 6588, 6920,
}

def main():
    lines = open(SRC).readlines()
    fixed = 0
    touched_ids = set()

    out_lines = []
    for l in lines:
        ex = json.loads(l)
        if ex["id"] in CONFIRMED_BUG_IDS:
            for c in ex["chips"]:
                if c["type"] != "noun_phrase" or not c.get("article"):
                    continue
                art = c["article"]
                if art.get("answer") == "den" and art.get("case") == "Dat" and art.get("number") == "Plur":
                    art["case"] = "Acc"
                    art["number"] = "Sing"
                    fixed += 1
                    touched_ids.add(ex["id"])
        out_lines.append(json.dumps(ex, ensure_ascii=False))

    missing = CONFIRMED_BUG_IDS - touched_ids
    if missing:
        print(f"WARNING: {len(missing)} confirmed-bug ids had no matching chip to fix: {missing}")

    with open(SRC, "w") as f:
        for l in out_lines:
            f.write(l + "\n")

    print(f"fixed {fixed} chip(s) across {len(touched_ids)} exercises")

if __name__ == "__main__":
    main()
