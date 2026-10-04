import json

BASE = "./explanations.jsonl"
FIXES = "./explanations_fixes.jsonl"
CLUSTER_PATCHES = "./explanations_cluster_patches.jsonl"
CASE_PATCHES = "./explanations_case_patches.jsonl"
ORDER_PATCHES = "./explanations_order_patches.jsonl"
CASE_GENDER_PATCHES = "./explanations_case_gender_patches.jsonl"
IDIOM_PATCHES = "./explanations_idiom_patches.jsonl"
VERB_CLUSTER_PATCHES = "./explanations_verb_cluster_patches.jsonl"
REFLEXIVE_DATIVE_PATCHES = "./explanations_reflexive_dative_patches.jsonl"
ALL_IDIOMS_PATCHES = "./explanations_all_idioms_patches.jsonl"
OUT_JS = "./explanations.js"


def load_jsonl(path):
    try:
        return [json.loads(l) for l in open(path) if l.strip()]
    except FileNotFoundError:
        return []


def main():
    by_id = {}
    for rec in load_jsonl(BASE):
        by_id[rec["id"]] = rec.get("chunks")

    # full-record overlays: last one wins per id
    for rec in load_jsonl(FIXES):
        by_id[rec["id"]] = rec.get("chunks")
    for rec in load_jsonl(CLUSTER_PATCHES):
        by_id[rec["id"]] = rec.get("chunks")

    # chunk-level overlays: find the matching chunk by its literal text and
    # replace just its reason, leaving everything else in that exercise's
    # chunk list untouched
    patch_counts = {}
    for patch_file, counter_name in (
        (CASE_PATCHES, "case"), (ORDER_PATCHES, "order"), (CASE_GENDER_PATCHES, "case_gender"),
        (IDIOM_PATCHES, "idiom"), (VERB_CLUSTER_PATCHES, "verb_cluster"),
        (REFLEXIVE_DATIVE_PATCHES, "reflexive_dative"), (ALL_IDIOMS_PATCHES, "all_idioms"),
    ):
        patch_counts[counter_name] = 0
        for rec in load_jsonl(patch_file):
            chunks = by_id.get(rec["id"])
            if not chunks:
                continue
            for c in chunks:
                if c["chunk"] == rec["chunk"]:
                    c["reason"] = rec["new_reason"]
                    patch_counts[counter_name] += 1
                    break

    n_with_chunks = sum(1 for v in by_id.values() if v)
    n_missing = sum(1 for v in by_id.values() if not v)
    print(f"merged {len(by_id)} exercise explanations")
    print(f"  {n_with_chunks} have usable chunks, {n_missing} failed generation entirely")
    print("  applied patches: " + ", ".join(f"{v} {k}" for k, v in patch_counts.items()))

    # drop entries with no usable chunks -- the app should just fall back to
    # the old heuristic panel for those rather than rendering nothing useful
    final = {str(id_): chunks for id_, chunks in by_id.items() if chunks}

    with open(OUT_JS, "w") as f:
        f.write("const EXPLANATIONS = ")
        f.write(json.dumps(final, ensure_ascii=False))
        f.write(";")
    print(f"wrote {OUT_JS}")


if __name__ == "__main__":
    main()
