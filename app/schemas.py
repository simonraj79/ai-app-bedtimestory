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


class UsageAction(BaseModel):
    kind: str  # "story" or "question"
    email: str
    detail: str
    created_at: str


class UsageResponse(BaseModel):
    totals: UsageTotals
    users: list[UsageUser]
    daily: list[UsageDay]
    recent: list[UsageAction]
