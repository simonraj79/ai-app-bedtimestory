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
