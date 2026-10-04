import json, time, sys
sys.path.insert(0, ".")
from generate_explanations import gen_raw, parse_chunks
from check_coverage import check_one

SRC = "./exercises.jsonl"
BAD_IDS = "./bad_ids.jsonl"
FIXES_OUT = "./explanations_fixes.jsonl"
MAX_ATTEMPTS = 4

def main():
    answers = {}
    exercises = {}
    for l in open(SRC):
        ex = json.loads(l)
        exercises[ex["id"]] = ex
        answers[ex["id"]] = ex["answer"]

    bad_ids = [json.loads(l)["id"] for l in open(BAD_IDS) if l.strip()]

    already_fixed = set()
    try:
        for l in open(FIXES_OUT):
            l = l.strip()
            if not l:
                continue
            already_fixed.add(json.loads(l)["id"])
    except FileNotFoundError:
        pass
    bad_ids = [id_ for id_ in bad_ids if id_ not in already_fixed]
    print(f"attempting to fix {len(bad_ids)} bad ids ({len(already_fixed)} already fixed previously, skipping those)")

    fixed = 0
    still_bad = 0
    with open(FIXES_OUT, "a", buffering=1) as out_f:
        for id_ in bad_ids:
            ex = exercises[id_]
            result = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    text = gen_raw(ex)
                    chunks = parse_chunks(text)
                except Exception as e:
                    print(f"id={id_} attempt={attempt} parse/request error: {e}")
                    time.sleep(2)
                    continue
                reason = check_one(answers[id_], chunks)
                if reason is None:
                    result = chunks
                    break
                print(f"id={id_} attempt={attempt} still bad: {reason}")
                time.sleep(1)

            if result is not None:
                out_f.write(json.dumps({"id": id_, "chunks": result}, ensure_ascii=False) + "\n")
                out_f.flush()
                fixed += 1
                print(f"id={id_} FIXED")
            else:
                still_bad += 1
                print(f"id={id_} still unresolved after {MAX_ATTEMPTS} attempts, leaving for a later retry round")

    print(f"done: fixed {fixed}, still bad {still_bad}")

if __name__ == "__main__":
    main()
