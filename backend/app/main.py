import os
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./volleyball.db")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me-now")
SECRET_KEY = os.getenv("SECRET_KEY", "please-change-this-to-a-long-random-secret")
ALGORITHM = "HS256"

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
