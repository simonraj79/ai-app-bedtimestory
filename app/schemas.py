from pydantic import BaseModel


# --- App 1: Chat -------------------------------------------------------------

class AskRequest(BaseModel):
    question: str


class Interaction(BaseModel):
    id: int
    question: str
    answer: str
    model_name: str
    created_at: str


class AskResponse(BaseModel):
    answer: str
    history: list[Interaction]


# --- App 2: Bedtime Story ----------------------------------------------------

class StoryRequest(BaseModel):
    child_name: str
    theme: str
    length: str = "medium"  # Defaulted so older clients keep working.


class Story(BaseModel):
    id: int
    child_name: str
    theme: str
    story: str
    model_name: str
    created_at: str
    # Every statistic is Optional and defaults to None because the stories
    # written before the stats columns existed hold NULLs. A required field here
    # would fail validation on those rows and 500 the whole /stories response -
    # the history of a story from months ago breaking tonight's page.
    word_count: int | None = None
    sentence_count: int | None = None
    reading_seconds: int | None = None
    reading_ease: float | None = None
    grade_level: float | None = None
    genre: str | None = None
    genre_hits: str | None = None  # comma-joined, see sql/006


class StoryResponse(BaseModel):
    story: str
    history: list[Story]


# --- Sign-in -----------------------------------------------------------------

class CurrentUser(BaseModel):
    id: int
    email: str
    name: str


# --- One reader's own numbers ------------------------------------------------
#
# Deliberately a separate shape from the admin models below, even though the
# questions overlap. The admin view answers "who is using this", which needs an
# email on every row; this one answers "what have I made", where an email would
# only ever be the reader's own. Sharing a model would mean every future admin
# field had to be checked for whether it leaks.

class MyGenre(BaseModel):
    genre: str
    stories: int


class MyChild(BaseModel):
    child_name: str
    stories: int


class MyStats(BaseModel):
    stories: int
    words: int
    reading_seconds: int          # total, read aloud
    avg_words: int | None = None  # None until at least one story is analysed
    avg_grade: float | None = None
    longest_words: int | None = None
    first_story: str | None = None
    last_story: str | None = None
    unanalysed: int               # stories written before stats existed
    genres: list[MyGenre]
    children: list[MyChild]


# --- Admin -------------------------------------------------------------------

class UsageTotals(BaseModel):
    users: int
    sign_ins: int
    stories: int
    questions: int


class UsageUser(BaseModel):
    id: int
    email: str
    name: str
    created_at: str
    last_seen_at: str
    sign_ins: int
    stories: int
    questions: int


class UsageDay(BaseModel):
    day: str
    sign_ins: int
    stories: int
    questions: int
    people: int  # distinct people active that day, not a sum of the above


class UsageGenre(BaseModel):
    genre: str
    stories: int
    avg_words: int
    avg_grade: float


class UsageAction(BaseModel):
    kind: str  # "story" or "question"
    email: str
    detail: str
    created_at: str


class UsageResponse(BaseModel):
    totals: UsageTotals
    users: list[UsageUser]
    daily: list[UsageDay]
    genres: list[UsageGenre]  # empty until stories have been analysed
    recent: list[UsageAction]
