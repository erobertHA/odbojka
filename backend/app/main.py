import os
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Header, Request, Response as HTTPResponse, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field, StrictInt
from sqlalchemy import JSON, UniqueConstraint, Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./volleyball.db")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me-now")
SECRET_KEY = os.getenv("SECRET_KEY", "please-change-this-to-a-long-random-secret")
ALGORITHM = "HS256"
SITE_PASSWORD = "RobiJeCar"

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[str] = mapped_column(String(10), index=True)
    start_time: Mapped[str] = mapped_column(String(5))
    end_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    location: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    minimum_players: Mapped[int] = mapped_column(Integer, default=6)
    signup_deadline: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    responses: Mapped[list["Response"]] = relationship(back_populates="event", cascade="all, delete-orphan")


class Response(Base):
    __tablename__ = "responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    response: Mapped[str] = mapped_column(String(20))
    note: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    client_token: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    event: Mapped[Event] = relationship(back_populates="responses")


class Poll(Base):
    __tablename__ = "polls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    questions: Mapped[list] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    submissions: Mapped[list["PollSubmission"]] = relationship(back_populates="poll", cascade="all, delete-orphan")


class PollSubmission(Base):
    __tablename__ = "poll_submissions"
    __table_args__ = (UniqueConstraint("poll_id", "name_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    poll_id: Mapped[int] = mapped_column(ForeignKey("polls.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    name_key: Mapped[str] = mapped_column(String(160))
    answers: Mapped[list] = mapped_column(JSON)
    token: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    poll: Mapped[Poll] = relationship(back_populates="submissions")


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Volleyball RSVP API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
security = HTTPBearer(auto_error=False)


@app.middleware("http")
async def site_access(request: Request, call_next):
    if request.url.path not in {"/health", "/auth/unlock"}:
        try:
            payload = jwt.decode(request.cookies.get("site_access", ""), SECRET_KEY, algorithms=[ALGORITHM])
            if payload.get("scope") != "site_access":
                raise JWTError()
        except JWTError:
            return JSONResponse(status_code=401, content={"detail": "Za dostop vpiši geslo.", "locked": True})
    return await call_next(request)


class UnlockBody(BaseModel):
    password: str = Field(max_length=256)


@app.post("/auth/unlock")
def unlock(body: UnlockBody, request: Request, response: HTTPResponse):
    if not secrets.compare_digest(body.password.encode(), SITE_PASSWORD.encode()):
        raise HTTPException(status_code=401, detail="Napačno geslo.")
    token = jwt.encode({"scope": "site_access", "exp": datetime.now(timezone.utc) + timedelta(hours=12)},
                       SECRET_KEY, algorithm=ALGORITHM)
    response.set_cookie("site_access", token, httponly=True, samesite="strict",
                        secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https",
                        max_age=12 * 60 * 60, path="/")
    return {"ok": True}


@app.get("/auth/access")
def access():
    return {"ok": True}


def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class RSVPStatus(str, Enum):
    playing = "playing"
    drinks = "drinks"
    no = "no"


class LoginBody(BaseModel):
    username: str
    password: str


class EventBody(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: Optional[str] = None
    location: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    minimum_players: int = Field(default=6, ge=1, le=50)
    signup_deadline: Optional[str] = None


class RSVPBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    response: RSVPStatus
    note: Optional[str] = Field(default=None, max_length=300)
    client_token: Optional[str] = Field(default=None, max_length=64)

class AdminResponseBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    response: RSVPStatus
    note: Optional[str] = Field(default=None, max_length=300)



def event_to_dict(event: Event, include_tokens: bool = False):
    responses = sorted(event.responses, key=lambda r: (r.response, r.name.lower()))
    return {
        "id": event.id,
        "date": event.date,
        "start_time": event.start_time,
        "end_time": event.end_time,
        "location": event.location,
        "description": event.description,
        "minimum_players": event.minimum_players,
        "signup_deadline": event.signup_deadline,
        "active": event.active,
        "responses": [
            {
                "id": r.id,
                "name": r.name,
                "response": r.response,
                "note": r.note,
                **({"client_token": r.client_token} if include_tokens else {}),
            }
            for r in responses
        ],
    }


def make_token():
    expiry = datetime.now(timezone.utc) + timedelta(hours=12)
    return jwt.encode({"sub": ADMIN_USERNAME, "exp": expiry}, SECRET_KEY, algorithm=ALGORITHM)


def require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("sub") != ADMIN_USERNAME:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/auth/login")
def login(body: LoginBody):
    user_ok = secrets.compare_digest(body.username, ADMIN_USERNAME)
    pass_ok = secrets.compare_digest(body.password, ADMIN_PASSWORD)
    if not (user_ok and pass_ok):
        raise HTTPException(status_code=401, detail="Napačno uporabniško ime ali geslo.")
    return {"token": make_token()}


@app.get("/events/current")
def current_event(db: Session = Depends(db_session)):
    event = db.scalar(select(Event).where(Event.active == True).order_by(Event.date.asc(), Event.start_time.asc()))
    if not event:
        return None
    _ = event.responses
    return event_to_dict(event)


@app.post("/events/{event_id}/rsvp")
def rsvp(event_id: int, body: RSVPBody, db: Session = Depends(db_session)):
    event = db.get(Event, event_id)
    if not event or not event.active:
        raise HTTPException(status_code=404, detail="Termin ne obstaja ali ni več aktiven.")

    name = " ".join(body.name.strip().split())
    if not name:
        raise HTTPException(status_code=422, detail="Ime je obvezno.")

    own_response = None
    if body.client_token:
        own_response = db.scalar(
            select(Response).where(
                Response.event_id == event_id,
                Response.client_token == body.client_token
            )
        )

    matching_name = next(
        (
            response for response in event.responses
            if response.id != (own_response.id if own_response else None)
            and " ".join(response.name.strip().split()).casefold() == name.casefold()
        ),
        None,
    )

    if own_response and matching_name:
        raise HTTPException(status_code=409, detail="To ime je že prijavljeno.")

    if not own_response and matching_name:
        own_response = matching_name

    if own_response:
        created = False
        own_response.name = name
        own_response.response = body.response.value
        own_response.note = (body.note or "").strip() or None
        own_response.updated_at = datetime.now(timezone.utc)
        response_obj = own_response
    else:
        created = True
        response_obj = Response(
            event_id=event_id,
            name=name,
            response=body.response.value,
            note=(body.note or "").strip() or None,
            client_token=body.client_token or secrets.token_urlsafe(24),
        )
        db.add(response_obj)

    db.commit()
    db.refresh(response_obj)
    return {"client_token": response_obj.client_token, "created": created}


@app.get("/admin/events", dependencies=[Depends(require_admin)])
def admin_events(db: Session = Depends(db_session)):
    events = db.scalars(select(Event).order_by(Event.date.desc(), Event.start_time.desc())).all()
    for event in events:
        _ = event.responses
    return [event_to_dict(e, include_tokens=True) for e in events]


@app.post("/admin/events", dependencies=[Depends(require_admin)])
def create_event(body: EventBody, db: Session = Depends(db_session)):
    current = db.scalars(select(Event).where(Event.active == True)).all()
    for e in current:
        e.active = False

    event = Event(
        date=body.date,
        start_time=body.start_time,
        end_time=body.end_time,
        location=body.location.strip(),
        description=(body.description or "").strip() or None,
        minimum_players=body.minimum_players,
        signup_deadline=body.signup_deadline or None,
        active=True,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    _ = event.responses
    return event_to_dict(event)


@app.put("/admin/events/{event_id}", dependencies=[Depends(require_admin)])
def update_event(event_id: int, body: EventBody, db: Session = Depends(db_session)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Termin ne obstaja.")

    event.date = body.date
    event.start_time = body.start_time
    event.end_time = body.end_time
    event.location = body.location.strip()
    event.description = (body.description or "").strip() or None
    event.minimum_players = body.minimum_players
    event.signup_deadline = body.signup_deadline or None
    db.commit()
    db.refresh(event)
    _ = event.responses
    return event_to_dict(event)


@app.post("/admin/events/{event_id}/close", dependencies=[Depends(require_admin)])
def close_event(event_id: int, db: Session = Depends(db_session)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Termin ne obstaja.")
    event.active = False
    db.commit()
    return {"ok": True}


@app.put("/admin/responses/{response_id}", dependencies=[Depends(require_admin)])
def update_response(response_id: int, body: AdminResponseBody, db: Session = Depends(db_session)):
    response = db.get(Response, response_id)
    if not response:
        raise HTTPException(status_code=404, detail="Prijava ne obstaja.")

    name = " ".join(body.name.strip().split())
    if not name:
        raise HTTPException(status_code=422, detail="Ime je obvezno.")

    event = db.get(Event, response.event_id)
    duplicate = next(
        (
            item for item in event.responses
            if item.id != response.id
            and " ".join(item.name.strip().split()).casefold() == name.casefold()
        ),
        None,
    )

    if duplicate:
        raise HTTPException(status_code=409, detail="To ime je že prijavljeno.")

    response.name = name
    response.response = body.response.value
    response.note = (body.note or "").strip() or None
    response.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(response)
    return {"ok": True}


@app.delete("/admin/responses/{response_id}", dependencies=[Depends(require_admin)])
def delete_response(response_id: int, db: Session = Depends(db_session)):
    response = db.get(Response, response_id)
    if not response:
        raise HTTPException(status_code=404, detail="Prijava ne obstaja.")
    db.delete(response)
    db.commit()
    return {"ok": True}


# Poll questions are immutable after publication, so historical answers keep their meaning.
class PollQuestionBody(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    options: list[str] = Field(min_length=2, max_length=20)
    multiple: bool = False


class PollBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    questions: list[PollQuestionBody] = Field(min_length=1, max_length=20)


class PollVoteBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    answers: list[StrictInt | list[StrictInt]] = Field(min_length=1, max_length=20)


def poll_dict(poll: Poll):
    def utc(value):
        return value.replace(tzinfo=timezone.utc).isoformat() if value else None
    return {"id": poll.id, "title": poll.title, "questions": poll.questions,
            "active": poll.active, "created_at": utc(poll.created_at), "archived_at": utc(poll.archived_at)}


def poll_results(poll: Poll):
    return {**poll_dict(poll), "total": len(poll.submissions), "counts": [
        [sum(oi in (vote.answers[qi] if isinstance(vote.answers[qi], list) else [vote.answers[qi]]) for vote in poll.submissions) for oi in range(len(question["options"]))]
        for qi, question in enumerate(poll.questions)
    ]}


@app.get("/polls/active")
def active_polls(db: Session = Depends(db_session)):
    return [poll_dict(poll) for poll in db.scalars(select(Poll).where(Poll.active == True).order_by(Poll.created_at.desc(), Poll.id.desc())).all()]


@app.post("/polls/{poll_id}/vote", status_code=201)
def vote_poll(poll_id: int, body: PollVoteBody, db: Session = Depends(db_session)):
    # Serialize vote/archive writes on SQLite to avoid accepting a vote after archival.
    if engine.dialect.name == "sqlite":
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    poll = db.get(Poll, poll_id)
    if not poll or not poll.active:
        raise HTTPException(status_code=404, detail="Anketa ni več aktivna.")
    name = " ".join(body.name.split())
    if not name:
        raise HTTPException(status_code=422, detail="Vpiši svoje ime.")
    if len(body.answers) != len(poll.questions):
        raise HTTPException(status_code=422, detail="Odgovori na vsako vprašanje.")
    answers = []
    for question, answer in zip(poll.questions, body.answers):
        choices = answer if isinstance(answer, list) else [answer]
        if (not choices or len(choices) > len(question["options"])
                or len(set(choices)) != len(choices)
                or any(choice < 0 or choice >= len(question["options"]) for choice in choices)
                or (not question.get("multiple", False) and len(choices) != 1)):
            raise HTTPException(status_code=422, detail="Pri vsakem vprašanju izberi dovoljeno število različnih odgovorov.")
        answers.append(sorted(choices) if question.get("multiple", False) else choices[0])
    vote = PollSubmission(poll_id=poll.id, name=name, name_key=name.casefold(),
                          answers=answers, token=secrets.token_urlsafe(32))
    db.add(vote)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="To ime je na to anketo že odgovorilo.")
    return {"token": vote.token, "results": poll_results(poll)}


@app.get("/polls/{poll_id}/results")
def get_poll_results(poll_id: int, x_poll_token: str = Header(default="", max_length=64), db: Session = Depends(db_session)):
    poll = db.get(Poll, poll_id)
    if not poll or not poll.active:
        raise HTTPException(status_code=404, detail="Anketa ni več aktivna.")
    vote = db.scalar(select(PollSubmission).where(PollSubmission.poll_id == poll_id, PollSubmission.token == x_poll_token))
    if not vote:
        raise HTTPException(status_code=403, detail="Rezultati so na voljo po oddaji odgovora.")
    return poll_results(poll)


@app.get("/admin/polls", dependencies=[Depends(require_admin)])
def admin_polls(db: Session = Depends(db_session)):
    polls = db.scalars(select(Poll).order_by(Poll.created_at.desc(), Poll.id.desc())).all()
    return [{**poll_results(poll), "submissions": [
        {"id": vote.id, "name": vote.name, "answers": vote.answers,
         "created_at": vote.created_at.replace(tzinfo=timezone.utc).isoformat()}
        for vote in sorted(poll.submissions, key=lambda vote: vote.created_at)
    ]} for poll in polls]


@app.post("/admin/polls", dependencies=[Depends(require_admin)], status_code=201)
def create_poll(body: PollBody, db: Session = Depends(db_session)):
    title = body.title.strip()
    questions = []
    for question in body.questions:
        text = question.text.strip()
        options = [option.strip() for option in question.options]
        if not text or any(not option or len(option) > 200 for option in options):
            raise HTTPException(status_code=422, detail="Izpolni vprašanja in vse odgovore (največ 200 znakov na odgovor).")
        if len({option.casefold() for option in options}) != len(options):
            raise HTTPException(status_code=422, detail="Odgovori pri istem vprašanju morajo biti različni.")
        questions.append({"text": text, "options": options, "multiple": question.multiple})
    if not title:
        raise HTTPException(status_code=422, detail="Vnesi naslov ankete.")
    poll = Poll(title=title, questions=questions)
    db.add(poll)
    db.commit()
    return poll_dict(poll)


@app.post("/admin/polls/{poll_id}/archive", dependencies=[Depends(require_admin)])
def archive_poll(poll_id: int, db: Session = Depends(db_session)):
    if engine.dialect.name == "sqlite":
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    poll = db.get(Poll, poll_id)
    if not poll:
        raise HTTPException(status_code=404, detail="Anketa ne obstaja.")
    if poll.active:
        poll.active = False
        poll.archived_at = datetime.now(timezone.utc)
        db.commit()
    return {"ok": True}
