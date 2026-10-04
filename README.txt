GRAMMATIK - GERMAN SENTENCE-BUILDING TRAINER (B1)
=================================================

A browser app for practising German grammar by building sentences.

Each exercise gives you an English sentence and a shuffled word bank of German
words in their base forms (e.g. "einschlafen", "haben/sein"). You write the
German sentence with the right word order, verb forms, cases and endings.

- 17,154 exercises in 27 grammar categories, aimed at the Goethe B1 level
- Articles, "nicht" and prepositions are never given; you work them out yourself
- Two modes: drag the words into place, or free-type the whole sentence
  (including your own commas)
- Colour-coded feedback on every word:
    red         word shouldn't be there
    yellow      right idea, wrong spelling or ending
    underlined  right word, wrong position
    missing     word never typed
- An explanation for every exercise: why each part of the sentence goes where it does
- Read-aloud in German and a microphone pronunciation check
- Ä / Ö / Ü / ß buttons and statistics on what you get right and wrong
- Nothing to install: it is a single web page

See screenshot.png for what an exercise looks like.


PLATFORM AND TESTING
--------------------
This app was created entirely on Linux (Ubuntu).

It has ONLY been tested on Linux, in Google Chrome. It has NOT been tested on
Windows or Mac yet. It is a plain web page with no installs and no
Linux-specific code, so it should work on Windows and Mac in a modern browser.
The browser table below is expected behaviour, not test results. If something
does not work on your system, please open an issue.


HOW TO USE IT
-------------
Online (easiest):
  Open the GitHub Pages link of this repository in Chrome or Edge.

On your own computer:
  1. Download this repository (green "Code" button -> "Download ZIP") and unzip it.
  2. Start a small local web server in the folder. This needs Python
     (https://www.python.org/downloads/), which is already installed on Mac and Linux:

         cd grammatik_German_Schreiben_App
         python3 -m http.server 8000

     On Windows, type "python" instead of "python3".
  3. Open http://localhost:8000 in Chrome or Edge.

  You can also open index.html directly by double-clicking it, but the browser
  will then not remember the microphone permission. The web server (or the
  GitHub Pages link) avoids that.

Your statistics are saved in your own browser on your own device. They are not
uploaded anywhere, and they do not carry over to another browser or computer.


BROWSER SUPPORT (expected, see "Platform and testing")
------------------------------------------------------
Feature                            Chrome / Edge (Win, Mac)   Safari (Mac)       Firefox
---------------------------------  -------------------------  -----------------  ---------------
Exercises, stats, Ä/Ö/Ü buttons    yes                        yes                yes
Speaker (read aloud in German)     yes                        yes                yes
Microphone pronunciation check     yes                        mostly works       not supported

Recommended: Chrome or Edge.
The speaker and microphone use the browser's built-in speech features. For the
best German voice, make sure a German voice is available (Chrome includes
"Google Deutsch").


GRAMMAR CATEGORIES
------------------
Category                                     Exercises   Example
-------------------------------------------  ---------   ---------------------------------------------------------
Konjunktiv II                                    2,405   Du würdest den DJ buchen.
Modal verb forms                                 2,350   Du musst den Hund baden.
Da-compounds (darauf, damit, darum ...)          2,000   Es geht darum, mehr zu üben.
Perfekt with "haben"                             1,066   Du hast das Auto gekauft.
Perfekt with "sein"                              1,042   Er ist beim Arzt eingeschlafen.
Relative clauses                                   800   Der Mann, der dort arbeitet, verdient gut.
Negation with "kein"                               661   Die Gäste haben kein Auto.
Dative of interest                                 500   Das Kind wäscht dir das Auto.
Negation with "nicht"                              485   Du liest das Buch nicht.
Verbs with fixed prepositions                      476   Ich warte auf den Bus.
Modal verb + infinitive                            424   Du darfst die Tür öffnen.
Order of two pronouns / objects                    407   Ich bringe ihr das Brot.
Subordinate clauses                                326   Du kommst später, weil es schon spät ist.
Dative prepositions                                320   Du passt zu dem Stil.
Two-way prepositions: motion (accusative)          320   Du gehst in den Park.
Two-way prepositions: location (dative)            320   Du bist in dem Park.
Adjective endings                                  320   Ihr seht den alten Turm.
Accusative prepositions                            320   Du bittest um den Rat.
"weil" vs. "denn"                                  317   Du kochst Pasta, weil du keine Zeit hast.
Reflexive pronouns                                 317   Du freust dich auf die Reise.
Indefinite and possessive articles                 299   Er möchte einen Kaffee trinken.
Separable verbs                                    292   Du holst das Paket ab.
Definite articles in different cases               278   Der Hund sucht nach dem Ball im Garten.
Passive voice                                      278   Das Buch ist gelesen worden.
Coordinating conjunctions                          277   Es regnet heute, aber ich treibe trotzdem Sport.
Sentences with several verbs                       277   Ich gehe ins Schwimmbad, weil ich schwimmen lernen möchte.
"sondern"                                          277   Es gibt kein Brot, sondern Brötchen.
-------------------------------------------  ---------
TOTAL                                           17,154


HOW THE SENTENCES WERE MADE
---------------------------
The exercises were produced with AI and then checked automatically against
fixed German grammar rules. Every sentence went through these steps:

1. Writing the sentences
   The core sentence set (German sentence + English translation, per category)
   was created with AI assistance during development.
   Two categories were built WITHOUT AI, from Python templates:
     - Dative of interest (500)
     - Verbs with fixed prepositions (476), built from a list of
       verb + preposition combinations that had already been checked

2. Turning sentences into exercises
   Each sentence is split into "chips": verbs in the infinitive, nouns with
   their article, prepositions, negation words and so on. Each chip stores
   the correct form and position. Extra grammar information is added, such as
   case and gender of noun phrases, definite vs. indefinite, verb clusters and
   reflexive datives.

3. Writing the explanations
   For every exercise, an AI model explains each part of the sentence, e.g.
   "bei meinem Friseur - bei always takes the dative."

   The model used for steps 2 and 3, and for fixing errors, is Mistral Small
   (24 billion parameters) from the French company Mistral AI. It is strong in
   European languages. It ran locally on my own computer through Ollama
   (https://ollama.com), so tens of thousands of AI calls cost nothing.

4. Checking the grammar (rule-based, not AI)
   AI models make mistakes, so the output was checked with Python scripts that
   know hard grammar facts:
     - Coverage: every word in the sentence must belong to a chip, including
       correct umlauts.
     - Cases:
         * Fixed-case prepositions are checked against a table:
           mit, bei, seit, von, zu, aus, nach ... always take the DATIVE
           für, durch, ohne, gegen, um ...       always take the ACCUSATIVE
           wegen, trotz, während, statt ...      always take the GENITIVE
         * Two-way prepositions (in, an, auf, über, unter, vor, hinter, neben,
           zwischen) are checked against the exercise:
           motion = accusative, location = dative.
         * Contractions are understood (im = in dem, zum = zu dem, ins = in das ...).
     - Word order: statements in the explanations, such as "'nicht' comes
       before the verb", are checked against the actual word positions in the
       sentence (verb position, "nicht", separable prefixes).
     - Idioms: checked in four passes, each stricter than the last. The final
       pass throws out "idioms" that are really just literal translations
       (e.g. "den Wein probieren" = "to taste the wine").

5. Fix and repeat
   Every exercise that failed a check was sent back to the AI with the
   specific error, fixed, and checked again. This check-and-fix cycle ran
   until the checks passed.

Even so, a dataset this large can still contain occasional mistakes. If you
find one, please open an issue with the exercise text.


FILES
-----
index.html        the app (layout, logic, speech, statistics)
exercises.js      all 17,154 exercises with their chips and English translations
explanations.js   the explanation for every exercise
screenshot.png    picture of an exercise
README.txt        this file
