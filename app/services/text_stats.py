"""Readability, read-aloud time and genre for a finished story.

Both Flesch formulas are two divisions and four constants, so nothing here needs
textstat, nltk or pyphen - a dependency would buy an import, not an answer. The
syllable count is the one inexact number in the module; see count_syllables.
"""

import re

# Read ALOUD, not silently. A silent adult manages ~230 wpm, but this text gets
# read to a child in a dark room, so a silent rate would report roughly half the
# time the parent is actually about to spend.
READ_ALOUD_WPM = 130

# Letters plus internal apostrophes, so "don't" is one word while numbers and
# bare punctuation are none. Not ASCII-only: "Zoe" arrives as "Zoë" often enough,
# and the model writes curly apostrophes, so both quote characters are accepted.
WORD_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*")
SENTENCE_END_RE = re.compile(r"[.!?]+")
VOWEL_RUN_RE = re.compile(r"[aeiouy]+")
NON_LETTER_RE = re.compile(r"[^a-z]")

# The closed set of labels analyse() can return, and - because ties are broken by
# position - the priority order. "Bedtime" is last on purpose: it is the fallback
# every story qualifies for, so it should only win when nothing else scored.
GENRES = (
    "Animals",
    "Fantasy",
    "Space",
    "Sea",
    "Nature",
    "Vehicles",
    "Family",
    "Adventure",
    "Bedtime",
)

# Single lowercase words only - each one is interpolated straight into a regex.
# A word belongs to exactly one genre, so a hit is never double-counted.
GENRE_WORDS = {
    "Animals": ("animal", "bear", "bird", "bunny", "cat", "cow", "deer", "dog",
                "duck", "elephant", "fox", "frog", "hedgehog", "horse", "kitten",
                "lion", "monkey", "mouse", "nest", "owl", "panda", "paw", "pony",
                "puppy", "rabbit", "sheep", "squirrel", "tail", "tiger",
                "turtle", "wolf"),
    "Fantasy": ("castle", "dragon", "elf", "enchanted", "fairy", "giant",
                "kingdom", "knight", "magic", "magical", "mermaid", "potion",
                "prince", "princess", "spell", "troll", "unicorn", "wand",
                "witch", "wizard"),
    "Space": ("alien", "astronaut", "comet", "galaxy", "meteor", "moon", "orbit",
              "planet", "rocket", "satellite", "spaceship", "star", "telescope",
              "universe"),
    "Sea": ("beach", "coral", "crab", "dolphin", "fish", "harbour", "island",
            "lighthouse", "ocean", "sailor", "sand", "sea", "seashell",
            "seaweed", "shell", "shore", "starfish", "tide", "wave", "whale"),
    "Nature": ("blossom", "cloud", "flower", "forest", "garden", "hill", "leaf",
               "leaves", "meadow", "mountain", "pond", "rain", "river", "sky",
               "snow", "stream", "sun", "tree", "valley", "wind"),
    "Vehicles": ("aeroplane", "bicycle", "bike", "bus", "car", "digger",
                 "engine", "ferry", "plane", "ship", "tractor", "train",
                 "truck", "wheel"),
    "Family": ("aunt", "baby", "brother", "cousin", "dad", "daddy", "family",
               "father", "grandma", "grandpa", "granny", "home", "mother",
               "mum", "mummy", "sister", "uncle"),
    "Adventure": ("adventure", "brave", "cave", "chest", "compass", "discover",
                  "explore", "explorer", "hidden", "journey", "map", "mystery",
                  "path", "pirate", "quest", "secret", "trail", "treasure",
                  "voyage"),
}

# "Bedtime" deliberately has NO lexicon and is never scored - it is only the
# label used when nothing else matched.
#
# It had one, and it made the whole feature useless. STORY_SYSTEM_PROMPT ends
# every story with "the child safe, warm and falling asleep", so bed / sleepy /
# cozy / tucked / night appear in ALL of them - and swamped the words that
# actually say what a story is about. Measured over the real table: 7 stories,
# 7 labelled "Bedtime", including one whose theme was "a rabbit with a very soft
# blanket" - where blanket, bed, cozy, goodnight and sleep beat rabbit.
#
# A feature present in 100% of items carries no information. Bedtime is the
# constant here, not a genre, so it cannot be allowed to compete with the signal.
FALLBACK_GENRE = "Bedtime"

MAX_GENRE_HITS = 5

# A word in the theme counts for this many in the story.
#
# The theme is what the reader actually asked for; the story text is mostly
# scenery, and there is a lot more of it. Unweighted, "a rabbit with a very soft
# blanket" came out as Space, because a moon and a star were mentioned more often
# than the rabbit was, and "a little turtle carrying a lantern" came out as
# Nature on the strength of a pond, the sun and a leaf.
#
# 3 is enough for a named subject to hold its own against a paragraph of
# background without letting a single stray theme word override a story that is
# clearly about something else - "a lantern that guides fireflies home" matches
# `home` (Family), and Nature still wins it on the strength of the actual text.
THEME_WEIGHT = 3


def count_syllables(word: str) -> int:
    """Count vowel groups. This is a heuristic - Python ships no syllable dictionary.

    It is right for ordinary story words and wrong in four known ways. An "-le"
    ending comes out one short ("little" and "turtle" both score 1). Two vowels
    that straddle a syllable break count as one group, also short ("lion" and
    "poem" both score 1). Treating y as a vowel splits some long words too far,
    so they come out one long ("everywhere" scores 4, not 3). Names are a guess
    either way ("Anaya" scores 2, not 3). The formulas below use the total across
    hundreds of words, and the errors do not all point the same way, so a handful
    of them moves the score by a fraction of a point - but do not quote this for
    a single word as if it were exact.
    """
    letters = NON_LETTER_RE.sub("", word.lower())
    syllables = len(VOWEL_RUN_RE.findall(letters))
    if letters.endswith("e"):
        syllables -= 1  # silent trailing e: "cake" is one syllable, not two
    return max(syllables, 1)  # anything said aloud takes at least one


def pick_genre(text: str, theme: str = "") -> tuple[str, list[str]]:
    """Highest score wins; ties go to whichever comes first in GENRES.

    A word found in the theme scores THEME_WEIGHT, a word found in the story
    scores 1, and a word in both scores each. See THEME_WEIGHT for why.
    """
    lowered, theme_lowered = text.lower(), theme.lower()
    # Every story this app writes is a bedtime story, so nothing matching is not
    # a failure to classify - it is the honest answer, with no words to show for it.
    best_genre, best_hits, best_score = FALLBACK_GENRE, [], 0
    for genre in GENRES:
        words = GENRE_WORDS.get(genre)
        if not words:
            continue  # the fallback has no lexicon and never competes
        found, score = [], 0
        for word in words:
            # \b on both sides, or "starling" scores Space and "seal" scores Sea.
            # The optional s takes the plural without reaching into a longer word.
            pattern = rf"\b{word}s?\b"
            in_story = re.search(pattern, lowered)
            in_theme = re.search(pattern, theme_lowered)
            if in_story:
                score += 1
            if in_theme:
                score += THEME_WEIGHT
            if in_story or in_theme:
                # -1 sorts theme words to the front: the subject the reader asked
                # for is the most useful hit to show them, whether or not the
                # story happened to repeat it.
                found.append((-1 if in_theme else in_story.start(), word))
        found.sort()  # report hits in the order a reader meets them
        # Strictly greater, so an earlier genre keeps a tie and the label is
        # reproducible for the same text.
        if score > best_score:
            best_genre, best_hits, best_score = genre, found, score
    return best_genre, [word for _, word in best_hits[:MAX_GENRE_HITS]]


def analyse(text: str, theme: str = "") -> dict:
    """Word, sentence and syllable counts, both Flesch scores, read-aloud time, genre.

    `theme` is what the reader typed and is only used to pick the genre, where it
    carries THEME_WEIGHT times the pull of the same word in the story. It defaults
    to empty so text can still be analysed on its own.
    """
    words = WORD_RE.findall(text)
    word_count = len(words)

    # Both formulas divide by the word count, and text with no words has no
    # readability to report. Answer with zeros rather than raising: a caller that
    # passes "" gets a dict back, not a 500. sentence_count stays 1 even here so
    # that every result carries a divisor a caller can use without checking it.
    if word_count == 0:
        return {
            "word_count": 0,
            "sentence_count": 1,
            "syllable_count": 0,
            "reading_seconds": 0,
            "reading_ease": 0.0,
            "grade_level": 0.0,
            "genre": FALLBACK_GENRE,
            "genre_hits": [],
        }

    # A story with no full stop at all is one sentence, not none - zero here
    # would divide by zero two lines below.
    sentences = [part for part in SENTENCE_END_RE.split(text) if part.strip()]
    sentence_count = max(len(sentences), 1)
    syllable_count = sum(count_syllables(word) for word in words)

    words_per_sentence = word_count / sentence_count
    syllables_per_word = syllable_count / word_count

    # Clamped to 0-100: the raw formula runs past 100 on the very short sentences
    # a five-year-old's story is made of, and a number outside its own advertised
    # range reads as a bug to whoever is looking at it.
    reading_ease = 206.835 - 1.015 * words_per_sentence - 84.6 * syllables_per_word
    reading_ease = min(100.0, max(0.0, reading_ease))
    # NOT clamped: a negative grade level is a real reading - "easier than the
    # scale goes" - and flooring it would make an easy story and a very easy one
    # look identical. How to present a negative is the caller's decision.
    grade_level = 0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59

    genre, genre_hits = pick_genre(text, theme)
    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "syllable_count": syllable_count,
        "reading_seconds": round(word_count / READ_ALOUD_WPM * 60),
        "reading_ease": round(reading_ease, 1),
        "grade_level": round(grade_level, 1),
        "genre": genre,
        "genre_hits": genre_hits,
    }
