import json, re, time, requests, sys

MODEL = "mistral-small"
OLLAMA_URL = "http://localhost:11434/api/generate"
CANDIDATES = "scratch/noarticle_candidates.json"
OUT = "./noarticle_classification.jsonl"

BATCH_SIZE = 15

PROMPT_TMPL = """You are classifying German words that appear capitalized inside example sentences from a B1 grammar app. For each word, decide:

- "common_noun": an ordinary common noun that should be tested for grammatical gender/case (e.g. Wetter, Job, Angst, Hund, Freund) -- INCLUDES nouns that happen to often appear without an article (mass nouns like Zeit, Geld, or plural nouns like Blumen, Jahre) as long as they're still ordinary countable/mass common nouns.
- "proper_noun": a place name, person's name/surname, or other proper noun that doesn't decline for gender/case in the usual way (e.g. Berlin, Italien, Müller, Deutschland).
- "fixed_expression": part of a frozen idiom/adverbial phrase where the word isn't functioning as a regular declinable noun in context (e.g. "Hause" in "nach Hause"/"zu Hause", "Mitternacht" in fixed time expressions) -- use this ONLY for genuinely frozen phrases, not just "this noun is often used with a preposition".
- "ambiguous_adverb": a word that's sometimes a plain adverb (no gender/case at all) and sometimes a real noun depending on context, and you cannot tell reliably from one example alone (e.g. "Morgen" could be "tomorrow" (adverb) or "the morning" (noun)).

For each "common_noun", also give:
- its grammatical gender: "Masc", "Fem", or "Neut" (the gender of the singular dictionary form, even if the word shown is plural)
- "number": "Sing" or "Plur" -- is the WORD AS SHOWN (in its exact given form, in that example sentence) singular or plural? (e.g. "Krimis" is already plural, "Monate" is already plural, "Wetter" is singular)

Words and one example sentence each:
{items}

Respond ONLY with a JSON array, no markdown fences, no extra text. Each element: {{"word": "...", "class": "common_noun"|"proper_noun"|"fixed_expression"|"ambiguous_adverb", "gender": "Masc"|"Fem"|"Neut"|null, "number": "Sing"|"Plur"|null}}
"""


def call(prompt, timeout=120):
    r = requests.post(OLLAMA_URL, json={
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.1}
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()["response"]


def parse(text):
    cleaned = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    data = json.loads(cleaned)
    assert isinstance(data, list)
    return data


def main():
    candidates = json.load(open(CANDIDATES))

    done_words = set()
    try:
        for l in open(OUT):
            l = l.strip()
            if l:
                done_words.add(json.loads(l)["word"])
    except FileNotFoundError:
        pass

    remaining = [c for c in candidates if c["word"] not in done_words]
    print(f"{len(done_words)} already classified, {len(remaining)} remaining")

    with open(OUT, "a", buffering=1) as out_f:
        for i in range(0, len(remaining), BATCH_SIZE):
            batch = remaining[i:i + BATCH_SIZE]
            items = "\n".join(f'- "{c["word"]}" (in: "{c["example"]}")' for c in batch)
            prompt = PROMPT_TMPL.format(items=items)
            result = None
            for attempt in range(1, 4):
                try:
                    text = call(prompt)
                    data = parse(text)
                    by_word = {d["word"]: d for d in data}
                    if all(c["word"] in by_word for c in batch):
                        result = data
                        break
                except Exception as e:
                    print(f"batch {i} attempt {attempt} error: {e}")
                    time.sleep(2)
            if result is None:
                print(f"batch {i} FAILED after retries, words: {[c['word'] for c in batch]}")
                continue
            for d in result:
                out_f.write(json.dumps(d, ensure_ascii=False) + "\n")
            print(f"batch {i // BATCH_SIZE + 1}/{(len(remaining) + BATCH_SIZE - 1) // BATCH_SIZE} done ({len(result)} words)")

    print("done")


if __name__ == "__main__":
    main()
