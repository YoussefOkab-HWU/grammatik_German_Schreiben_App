import json, time, requests, re, sys
from itertools import groupby

MODEL = "mistral-small"
OLLAMA_URL = "http://localhost:11434/api/generate"
SRC = "./exercises.jsonl"
EXPL = "./explanations.js"
PATCHES_OUT = "./explanations_reflexive_dative_patches.jsonl"

# "sich (dat) + accusative direct object + verb" -- a productive, general
# German pattern (dativus commodi / self-benefactive dative), not a closed
# arbitrary list like the verb+preposition idioms: "sich die Haare waschen"
# (wash one's hair), "sich ein Auto kaufen" (buy oneself a car), "sich etwas
# ansehen" (take a look at something). Learners default to reading "sich" as
# accusative self-reference ("looking at himself"), which is wrong whenever
# there's already a separate accusative object -- "sich" must then be dative.
REFLEXIVE_DISPLAYS = {"himself/herself/itself", "myself", "yourself", "ourselves", "yourselves",
    "themselves", "reflexive", "himself/herself"}
CLAUSE_BOUNDARY_WORDS = {"und", "aber", "oder", "weil", "dass", "wenn", "obwohl", "damit",
    "bevor", "nachdem", "sondern", "denn", "als", "waehrend", "während", "bis", "sobald", "falls"}
# accusative-of-time nouns ("jeden Freitag", "nächste Woche", "gestern Abend")
# get misread as the verb's direct object otherwise -- skip PAST them (rather
# than stopping the scan) so a genuine object further along still gets found,
# and so they're never themselves mistaken for one.
TEMPORAL_NOUNS = {"Woche", "Wochen", "Tag", "Tage", "Abend", "Abende", "Morgen", "Jahr", "Jahre",
    "Monat", "Monate", "Stunde", "Stunden", "Minute", "Minuten", "Sekunde", "Sekunden",
    "Nacht", "Naechte", "Nächte", "Wochenende", "Wochenenden",
    "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"}


def get_case(c):
    art = c.get("article")
    if art:
        return art.get("case")
    return c.get("case")


def find_reflexive_dative_pairs(ex):
    chips_sorted = sorted(ex["chips"], key=lambda c: (c["correct_gap"], c["order"]))
    pairs = []
    for gap, grp in groupby(chips_sorted, key=lambda c: c["correct_gap"]):
        grp = list(grp)
        for i, c in enumerate(grp):
            if not (c["type"] == "pronoun" and c.get("display") in REFLEXIVE_DISPLAYS and c["answer"].lower() == "sich"):
                continue
            for j in range(i + 1, len(grp)):
                nxt = grp[j]
                if nxt["type"] == "verb":
                    break
                if nxt["type"] == "bare_noun" and nxt["answer"].lower() in CLAUSE_BOUNDARY_WORDS:
                    break
                if nxt["type"] == "noun_phrase" and get_case(nxt) == "Acc":
                    if nxt.get("noun") in TEMPORAL_NOUNS:
                        continue  # keep scanning past it, don't match on it
                    prevj = grp[j - 1] if j > 0 else None
                    if not (prevj and prevj["type"] == "preposition_req"):
                        verbs_after = [v for v in grp[i:] if v["type"] == "verb"]
                        verbs_before = [v for v in grp[:i] if v["type"] == "verb"]
                        verb = (verbs_after[0]["display"] if verbs_after
                                else (verbs_before[-1]["display"] if verbs_before else None))
                        pairs.append((c, nxt, verb))
                    break
    return pairs


def find_target_chunk(chunks, noun_word, used):
    for c in chunks:
        if id(c) in used:
            continue
        words = re.findall(r"[a-zA-ZäöüßÄÖÜ]+", c["chunk"])
        if noun_word in words:
            return c
    return None


PROMPT_TMPL = """You previously explained part of a German sentence for a B1 learner, but missed an important grammar point.

Full German sentence: {answer}
The chunk in question: "{chunk}"
Your original reason: "{old_reason}"

This chunk contains the reflexive pronoun "sich" together with the noun phrase "{np_text}", which is accusative -- the direct object of "{verb}". Since the accusative slot is already taken by "{np_text}", "sich" here must be DATIVE, not accusative. It is a self-benefactive/dative-of-interest reflexive (roughly "for oneself" / "to oneself"), NOT a literal reflexive meaning "himself/herself" -- a learner should not read this as "looking at himself" or similar. This is a common, general German pattern (like "sich die Haare waschen", "sich etwas kaufen"), not a one-off idiom.

Rewrite the reason for this chunk (2-3 sentences, same teaching style as before) to explicitly state that "sich" is dative here (not accusative), because "{np_text}" already fills the accusative slot as the direct object of "{verb}". Keep any correct, still-relevant content from the original reason.

Respond with ONLY the corrected reason text. No JSON, no quotes, no markdown, no extra commentary.
"""


def call(prompt, timeout=120):
    r = requests.post(OLLAMA_URL, json={
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.2}
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()["response"].strip().strip('"')


def verify(new_reason):
    low = new_reason.lower()
    return "dative" in low and "sich" in low


def build_candidates(exercises, expl, limit=None):
    candidates = []
    for ex in exercises:
        chunks = expl.get(str(ex["id"]))
        if not chunks:
            continue
        used = set()
        for sich_chip, noun_chip, verb in find_reflexive_dative_pairs(ex):
            art = noun_chip.get("article")
            np_text = f"{art['answer']} {noun_chip['noun']}" if art else noun_chip["noun"]
            target = find_target_chunk(chunks, noun_chip["noun"], used)
            if not target:
                continue
            used.add(id(target))
            candidates.append({
                "id": ex["id"], "chunk": target["chunk"], "reason": target["reason"],
                "np_text": np_text, "verb": verb or "the verb",
            })
            if limit and len(candidates) >= limit:
                return candidates
    return candidates


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != "apply" else None

    exercises = [json.loads(l) for l in open(SRC)]
    answers = {ex["id"]: ex["answer"] for ex in exercises}
    expl = json.loads(open(EXPL).read()[len("const EXPLANATIONS = "):-1])

    candidates = build_candidates(exercises, expl, limit)

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

    print(f"found {len(candidates)} reflexive-dative candidates ({len(already_done)} already patched, will skip those)")

    n_done = n_failed = 0
    with open(PATCHES_OUT, "a", buffering=1) as out_f:
        for cand in candidates:
            id_ = cand["id"]
            if (id_, cand["chunk"]) in already_done:
                continue
            prompt = PROMPT_TMPL.format(
                answer=answers[id_], chunk=cand["chunk"], old_reason=cand["reason"],
                np_text=cand["np_text"], verb=cand["verb"],
            )
            accepted = None
            for attempt in range(1, 4):
                try:
                    candidate_text = call(prompt)
                except Exception as e:
                    print(f"id={id_} attempt={attempt} error: {e}")
                    time.sleep(2)
                    continue
                if candidate_text and verify(candidate_text):
                    accepted = candidate_text
                    break
                time.sleep(1)

            if accepted:
                out_f.write(json.dumps({
                    "id": id_, "chunk": cand["chunk"],
                    "old_reason": cand["reason"], "new_reason": accepted,
                }, ensure_ascii=False) + "\n")
                out_f.flush()
                n_done += 1
                print(f"id={id_} ({cand['np_text']} / {cand['verb']}) enriched ({n_done})")
            else:
                n_failed += 1
                print(f"id={id_} could not produce a verified enrichment after retries")

    print(f"done: enriched {n_done}, failed {n_failed}")


if __name__ == "__main__":
    main()
