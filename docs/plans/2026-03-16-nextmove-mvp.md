# NextMove MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build NextMove Phase 1 MVP — a Telegram bot + web app that converts student brain dumps into a prioritized daily task with AI scheduling.

**Architecture:** FastAPI backend with OpenAI parsing, matrix scoring, and scheduling engine. Next.js frontend. PostgreSQL + Redis. Telegram bot with full feature parity to web app.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, OpenAI API (gpt-4o), python-telegram-bot v20, Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, PostgreSQL 16, Redis, Docker Compose

---

## Phase A: Project Foundation

### Task 1: Repository & Docker Scaffold

**Files:**
- Create: `nextmove/docker-compose.yml`
- Create: `nextmove/backend/requirements.txt`
- Create: `nextmove/backend/app/main.py`
- Create: `nextmove/backend/app/config.py`
- Create: `nextmove/.env.example`
- Create: `nextmove/frontend/package.json`

**Step 1: Create root project directory and docker-compose**

```yaml
# docker-compose.yml
version: "3.9"
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: nextmove
      POSTGRES_PASSWORD: nextmove
      POSTGRES_DB: nextmove
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  worker:
    build: ./backend
    env_file: .env
    depends_on:
      - postgres
      - redis
    command: rq worker --url redis://redis:6379

volumes:
  pgdata:
```

**Step 2: Create backend requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.35
alembic==1.13.2
psycopg2-binary==2.9.9
pydantic==2.9.2
pydantic-settings==2.5.2
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.12
openai==1.50.0
python-telegram-bot==21.5
google-auth==2.35.0
google-auth-oauthlib==1.2.1
google-api-python-client==2.149.0
redis==5.1.1
rq==1.16.2
httpx==0.27.2
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-mock==3.14.0
python-dotenv==1.0.1
cryptography==43.0.1
```

**Step 3: Create backend Dockerfile**

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
```

**Step 4: Create config.py**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379"
    openai_api_key: str
    google_client_id: str
    google_client_secret: str
    telegram_bot_token: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    class Config:
        env_file = ".env"

settings = Settings()
```

**Step 5: Create main.py**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="NextMove API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 6: Create .env.example**

```
DATABASE_URL=postgresql://nextmove:nextmove@localhost:5432/nextmove
REDIS_URL=redis://localhost:6379
OPENAI_API_KEY=sk-...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
TELEGRAM_BOT_TOKEN=...
JWT_SECRET_KEY=your-secret-key-change-this
NEXTAUTH_SECRET=your-nextauth-secret
NEXTAUTH_URL=http://localhost:3000
```

**Step 7: Verify backend starts**

```bash
cd nextmove && docker-compose up postgres redis -d
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload
# Visit http://localhost:8000/health → {"status": "ok"}
```

**Step 8: Scaffold Next.js frontend**

```bash
cd nextmove
npx create-next-app@latest frontend --typescript --tailwind --app --src-dir --import-alias "@/*"
cd frontend && npm install next-auth @next-auth/prisma-adapter
```

**Step 9: Commit**

```bash
git init
git add .
git commit -m "feat: project scaffold — FastAPI backend + Next.js frontend + Docker"
```

---

### Task 2: Database Models & Migrations

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/task.py`
- Create: `backend/app/models/schedule.py`
- Create: `backend/app/models/calendar.py`
- Create: `backend/app/models/logs.py`
- Create: `backend/alembic.ini`
- Test: `backend/tests/test_models.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_models.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, User, Task

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_create_user(db):
    user = User(email="test@uni.edu", name="Alice", timezone="UTC")
    db.add(user)
    db.commit()
    assert user.id is not None
    assert user.email == "test@uni.edu"

def test_create_task(db):
    user = User(email="test@uni.edu", name="Alice", timezone="UTC")
    db.add(user)
    db.commit()
    task = Task(
        user_id=user.id,
        title="Finish ML assignment",
        effort="high",
        importance=4,
        status="pending"
    )
    db.add(task)
    db.commit()
    assert task.id is not None
    assert task.priority_index is None  # not yet scored

def test_task_status_values(db):
    user = User(email="test2@uni.edu", name="Bob", timezone="UTC")
    db.add(user)
    db.commit()
    for status in ["pending", "scheduled", "in_progress", "completed", "missed", "rescheduled"]:
        task = Task(user_id=user.id, title=f"Task {status}", effort="low", importance=1, status=status)
        db.add(task)
    db.commit()
```

**Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/test_models.py -v
# Expected: ImportError — models not defined yet
```

**Step 3: Create database.py**

```python
# backend/app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Step 4: Create models**

```python
# backend/app/models/__init__.py
from app.database import Base
from app.models.user import User
from app.models.task import Task
from app.models.schedule import ScheduleBlock
from app.models.calendar import CalendarEvent
from app.models.logs import ProductivityLog, NotificationLog

__all__ = ["Base", "User", "Task", "ScheduleBlock", "CalendarEvent", "ProductivityLog", "NotificationLog"]
```

```python
# backend/app/models/user.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, BigInteger, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    name = Column(String)
    hashed_password = Column(String, nullable=True)  # null if Google-only
    timezone = Column(String, default="UTC")
    google_access_token = Column(String, nullable=True)
    google_refresh_token = Column(String, nullable=True)
    telegram_chat_id = Column(BigInteger, nullable=True)
    uses_google_calendar = Column(Boolean, default=False)
    study_start_hour = Column(Integer, default=9)
    study_end_hour = Column(Integer, default=22)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks = relationship("Task", back_populates="user")
    schedule_blocks = relationship("ScheduleBlock", back_populates="user")
    calendar_events = relationship("CalendarEvent", back_populates="user")
```

```python
# backend/app/models/task.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class Task(Base):
    __tablename__ = "tasks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    raw_input = Column(Text, nullable=True)
    deadline = Column(DateTime, nullable=True)
    effort = Column(String, nullable=True)       # 'low', 'medium', 'high'
    importance = Column(Integer, nullable=True)  # 1-5
    context = Column(String, nullable=True)      # 'Study', 'Admin', 'Personal'
    priority_index = Column(Float, nullable=True)
    status = Column(String, default="pending")
    parent_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    google_event_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="tasks")
    schedule_blocks = relationship("ScheduleBlock", back_populates="task")
    subtasks = relationship("Task", backref="parent", remote_side="Task.parent_task_id")
    productivity_logs = relationship("ProductivityLog", back_populates="task")
```

```python
# backend/app/models/schedule.py
import uuid
from datetime import datetime
from sqlalchemy import Column, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class ScheduleBlock(Base):
    __tablename__ = "schedule_blocks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    is_google_synced = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="schedule_blocks")
    user = relationship("User", back_populates="schedule_blocks")
```

```python
# backend/app/models/calendar.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    is_all_day = Column(Boolean, default=False)
    recurrence_rule = Column(String, nullable=True)
    source = Column(String, default="manual")  # 'manual', 'nextmove', 'google_import'
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="calendar_events")
```

```python
# backend/app/models/logs.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class ProductivityLog(Base):
    __tablename__ = "productivity_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    scheduled_start = Column(DateTime, nullable=True)
    actual_start = Column(DateTime, nullable=True)
    actual_end = Column(DateTime, nullable=True)
    was_completed = Column(Boolean, nullable=True)
    procrastination_detected = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="productivity_logs")

class NotificationLog(Base):
    __tablename__ = "notification_log"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    type = Column(String)
    sent_at = Column(DateTime, default=datetime.utcnow)
    channel = Column(String, default="telegram")
```

**Step 5: Run tests to verify they pass**

```bash
cd backend && pytest tests/test_models.py -v
# Expected: 3 PASSED
```

**Step 6: Setup Alembic and create migration**

```bash
cd backend
alembic init alembic
# Edit alembic/env.py: import Base from app.models, set target_metadata = Base.metadata
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

**Step 7: Commit**

```bash
git add backend/app/models/ backend/app/database.py backend/alembic/ backend/tests/
git commit -m "feat: database models and initial migration"
```

---

### Task 3: Authentication System

**Files:**
- Create: `backend/app/services/auth.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/routers/auth.py`
- Test: `backend/tests/test_auth.py`

**Step 1: Write the failing tests**

```python
# backend/tests/test_auth.py
import pytest
from app.services.auth import (
    hash_password, verify_password, create_access_token, decode_token
)

def test_hash_and_verify_password():
    password = "mypassword123"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrongpassword", hashed)

def test_create_and_decode_token():
    token = create_access_token({"sub": "user-uuid-123"})
    payload = decode_token(token)
    assert payload["sub"] == "user-uuid-123"

def test_decode_invalid_token():
    with pytest.raises(Exception):
        decode_token("not.a.real.token")
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_auth.py -v
# Expected: ImportError
```

**Step 3: Implement auth service**

```python
# backend/app/services/auth.py
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires_minutes: int = None) -> str:
    expires = expires_minutes or settings.access_token_expire_minutes
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=expires)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}")
```

**Step 4: Create auth schemas**

```python
# backend/app/schemas/auth.py
from pydantic import BaseModel, EmailStr

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class GoogleAuthRequest(BaseModel):
    code: str  # OAuth authorization code
```

**Step 5: Create auth router**

```python
# backend/app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from app.services.auth import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=req.email, name=req.name, hashed_password=hash_password(req.password))
    db.add(user)
    db.commit()
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not user.hashed_password or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)
```

**Step 6: Add dependency to get current user**

```python
# backend/app/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.auth import decode_token
from app.models import User

bearer = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db)
) -> User:
    try:
        payload = decode_token(credentials.credentials)
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

**Step 7: Mount router in main.py**

```python
# Add to backend/app/main.py
from app.routers import auth
app.include_router(auth.router)
```

**Step 8: Run tests**

```bash
pytest tests/test_auth.py -v
# Expected: 3 PASSED
```

**Step 9: Commit**

```bash
git add backend/app/services/auth.py backend/app/schemas/ backend/app/routers/ backend/app/dependencies.py backend/tests/test_auth.py
git commit -m "feat: JWT auth with register/login endpoints"
```

---

## Phase B: AI Engine

### Task 4: AI Parsing Engine

**Files:**
- Create: `backend/app/services/ai_parser.py`
- Create: `backend/app/schemas/tasks.py`
- Test: `backend/tests/test_ai_parser.py`

**Step 1: Write the failing tests (mock OpenAI)**

```python
# backend/tests/test_ai_parser.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.ai_parser import parse_brain_dump, ParsedTask

@pytest.mark.asyncio
async def test_parse_single_task():
    mock_response = {
        "tasks": [
            {"title": "Finish ML assignment", "deadline": "2026-03-20", "effort": "high", "importance": 4, "context": "Study"}
        ]
    }
    with patch("app.services.ai_parser.openai_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=_mock_openai_response(mock_response))
        result = await parse_brain_dump("Finish ML assignment by Friday", user_timezone="UTC")
    assert len(result) == 1
    assert result[0].title == "Finish ML assignment"
    assert result[0].effort == "high"

@pytest.mark.asyncio
async def test_parse_multiple_tasks():
    mock_response = {
        "tasks": [
            {"title": "Finish ML assignment", "deadline": "2026-03-20", "effort": "high", "importance": 4, "context": "Study"},
            {"title": "Review lecture notes", "deadline": "2026-03-16", "effort": "low", "importance": 2, "context": "Study"}
        ]
    }
    with patch("app.services.ai_parser.openai_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=_mock_openai_response(mock_response))
        result = await parse_brain_dump(
            "Finish ML assignment by Friday and review lecture notes tonight",
            user_timezone="UTC"
        )
    assert len(result) == 2

def _mock_openai_response(data: dict):
    import json
    from unittest.mock import MagicMock
    msg = MagicMock()
    msg.content = json.dumps(data)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_ai_parser.py -v
# Expected: ImportError
```

**Step 3: Implement AI parser**

```python
# backend/app/services/ai_parser.py
import json
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from openai import AsyncOpenAI
from app.config import settings

openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

class ParsedTask(BaseModel):
    title: str
    deadline: Optional[str] = None      # ISO date string or None
    effort: str = "medium"              # 'low', 'medium', 'high'
    importance: int = 3                 # 1-5
    context: str = "Study"             # 'Study', 'Admin', 'Personal', 'Other'
    dependencies: list[str] = []        # titles of tasks this depends on

SYSTEM_PROMPT = """You are a task extraction assistant for a student productivity app.
Extract all tasks from the user's text. Return valid JSON only.

Rules:
- effort: 'low' (reading, review), 'medium' (problem sets, labs), 'high' (assignments, projects, exams)
- importance: 1 (nice to do) to 5 (critical / graded)
- context: 'Study', 'Admin', 'Personal', 'Other'
- deadline: ISO 8601 date string (YYYY-MM-DD) or null if not mentioned
- Interpret relative dates ('tonight', 'Friday', 'next week') from today's date provided

Return format:
{"tasks": [{"title": "...", "deadline": "...", "effort": "...", "importance": 1-5, "context": "...", "dependencies": []}]}"""

async def parse_brain_dump(text: str, user_timezone: str = "UTC") -> list[ParsedTask]:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    user_message = f"Today's date: {today}. Timezone: {user_timezone}.\n\nUser text: {text}"

    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        response_format={"type": "json_object"},
        temperature=0.1
    )

    raw = response.choices[0].message.content
    data = json.loads(raw)
    return [ParsedTask(**t) for t in data.get("tasks", [])]
```

**Step 4: Run tests**

```bash
pytest tests/test_ai_parser.py -v
# Expected: 2 PASSED
```

**Step 5: Commit**

```bash
git add backend/app/services/ai_parser.py backend/tests/test_ai_parser.py
git commit -m "feat: AI brain dump parser using OpenAI gpt-4o"
```

---

### Task 5: Matrix Scoring Engine

**Files:**
- Create: `backend/app/services/matrix_scorer.py`
- Test: `backend/tests/test_matrix_scorer.py`

**Step 1: Write the failing tests**

```python
# backend/tests/test_matrix_scorer.py
from datetime import datetime, timedelta
from app.services.matrix_scorer import score_task, TaskInput

def test_urgent_important_task_scores_high():
    task = TaskInput(
        deadline=datetime.utcnow() + timedelta(hours=12),
        effort="high",
        importance=5,
        dependency_count=2
    )
    score = score_task(task)
    assert score > 7.0

def test_low_priority_task_scores_low():
    task = TaskInput(
        deadline=datetime.utcnow() + timedelta(days=30),
        effort="low",
        importance=1,
        dependency_count=0
    )
    score = score_task(task)
    assert score < 3.0

def test_no_deadline_task():
    task = TaskInput(
        deadline=None,
        effort="medium",
        importance=3,
        dependency_count=0
    )
    score = score_task(task)
    assert 0.0 <= score <= 10.0

def test_score_formula_weights():
    # High urgency (deadline in 1 hour) + max importance + no effort + no dep
    task = TaskInput(
        deadline=datetime.utcnow() + timedelta(hours=1),
        effort="low",
        importance=5,
        dependency_count=0
    )
    score = score_task(task)
    # Urgency ~10, Importance=10, Effort=2 (inverted: low=2), Dep=0
    # P = 0.35*10 + 0.30*10 + 0.20*2 + 0.15*0 = 3.5 + 3.0 + 0.4 = 6.9
    assert 6.0 < score < 8.0
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_matrix_scorer.py -v
```

**Step 3: Implement matrix scorer**

```python
# backend/app/services/matrix_scorer.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

EFFORT_MAP = {"low": 2, "medium": 5, "high": 9}

class TaskInput(BaseModel):
    deadline: Optional[datetime]
    effort: str = "medium"
    importance: int = 3      # 1-5
    dependency_count: int = 0

def _urgency_score(deadline: Optional[datetime]) -> float:
    """Returns 0-10. Higher = more urgent."""
    if deadline is None:
        return 3.0  # default mid-low urgency for tasks without deadlines
    hours_remaining = (deadline - datetime.utcnow()).total_seconds() / 3600
    if hours_remaining <= 0:
        return 10.0
    elif hours_remaining <= 24:
        return 9.0
    elif hours_remaining <= 48:
        return 7.5
    elif hours_remaining <= 72:
        return 6.0
    elif hours_remaining <= 168:  # 1 week
        return 4.0
    elif hours_remaining <= 336:  # 2 weeks
        return 2.0
    else:
        return 1.0

def _importance_score(importance: int) -> float:
    """Maps 1-5 to 0-10."""
    return (importance - 1) / 4 * 10

def _effort_score(effort: str) -> float:
    """Maps effort to 0-10. High effort = high score (high effort tasks need more priority)."""
    return float(EFFORT_MAP.get(effort, 5))

def _dependency_score(count: int) -> float:
    """Tasks blocking more other tasks get higher scores."""
    return min(count * 2.5, 10.0)

def score_task(task: TaskInput) -> float:
    U = _urgency_score(task.deadline)
    I = _importance_score(task.importance)
    E = _effort_score(task.effort)
    D = _dependency_score(task.dependency_count)
    return round(0.35 * U + 0.30 * I + 0.20 * E + 0.15 * D, 2)
```

**Step 4: Run tests**

```bash
pytest tests/test_matrix_scorer.py -v
# Expected: 4 PASSED
```

**Step 5: Commit**

```bash
git add backend/app/services/matrix_scorer.py backend/tests/test_matrix_scorer.py
git commit -m "feat: matrix scoring engine with urgency/importance/effort/dependency"
```

---

### Task 6: Scheduling Engine

**Files:**
- Create: `backend/app/services/scheduler.py`
- Test: `backend/tests/test_scheduler.py`

**Step 1: Write the failing tests**

```python
# backend/tests/test_scheduler.py
from datetime import datetime, timedelta
import pytest
from app.services.scheduler import (
    build_schedule, FreeSlot, TaskToSchedule, ScheduledBlock
)

def make_slot(hour_start, hour_end, date_offset=0):
    base = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    base += timedelta(days=date_offset)
    return FreeSlot(
        start=base.replace(hour=hour_start),
        end=base.replace(hour=hour_end)
    )

def test_high_effort_task_assigned_to_peak_slot():
    slots = [make_slot(9, 12), make_slot(14, 16), make_slot(20, 22)]
    tasks = [TaskToSchedule(id="1", title="Hard assignment", effort="high", priority_index=8.0, estimated_hours=2)]
    result = build_schedule(tasks, slots, study_start=9, study_end=22)
    assert len(result) == 1
    # Peak slot is 9-12am (morning), high effort goes there
    assert result[0].start.hour == 9

def test_low_effort_task_assigned_to_evening_slot():
    slots = [make_slot(9, 12), make_slot(20, 22)]
    tasks = [TaskToSchedule(id="1", title="Read chapter", effort="low", priority_index=3.0, estimated_hours=1)]
    result = build_schedule(tasks, slots, study_start=9, study_end=22)
    assert len(result) == 1
    # Low effort can go to evening
    assert result[0].start.hour >= 14  # not morning peak

def test_multiple_tasks_scheduled():
    slots = [make_slot(9, 12), make_slot(14, 16), make_slot(20, 22)]
    tasks = [
        TaskToSchedule(id="1", title="Exam prep", effort="high", priority_index=9.0, estimated_hours=2),
        TaskToSchedule(id="2", title="Review notes", effort="low", priority_index=3.0, estimated_hours=1),
    ]
    result = build_schedule(tasks, slots, study_start=9, study_end=22)
    assert len(result) == 2
    ids = [r.task_id for r in result]
    assert "1" in ids and "2" in ids

def test_no_double_booking():
    slots = [make_slot(9, 10)]
    tasks = [
        TaskToSchedule(id="1", title="Task A", effort="medium", priority_index=7.0, estimated_hours=1),
        TaskToSchedule(id="2", title="Task B", effort="medium", priority_index=6.0, estimated_hours=1),
    ]
    result = build_schedule(tasks, slots, study_start=9, study_end=22)
    # Only one task can fit in one 1-hour slot
    assert len(result) == 1
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_scheduler.py -v
```

**Step 3: Implement scheduling engine**

```python
# backend/app/services/scheduler.py
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Optional

EFFORT_HOURS_DEFAULT = {"low": 1, "medium": 2, "high": 3}

class FreeSlot(BaseModel):
    start: datetime
    end: datetime

    @property
    def duration_hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600

    def is_peak(self, study_start: int = 9) -> bool:
        """Morning = 6am to noon."""
        return self.start.hour >= 6 and self.start.hour < 12

    def is_mid(self) -> bool:
        """Afternoon = noon to 6pm."""
        return self.start.hour >= 12 and self.start.hour < 18

    def is_evening(self) -> bool:
        """Evening = 6pm onwards."""
        return self.start.hour >= 18

class TaskToSchedule(BaseModel):
    id: str
    title: str
    effort: str         # 'low', 'medium', 'high'
    priority_index: float
    estimated_hours: Optional[float] = None

    @property
    def hours_needed(self) -> float:
        if self.estimated_hours:
            return self.estimated_hours
        return EFFORT_HOURS_DEFAULT.get(self.effort, 2)

    def prefers_slot(self, slot: FreeSlot) -> bool:
        """Returns True if this task's effort matches the slot's energy level."""
        if self.effort == "high":
            return slot.is_peak()
        elif self.effort == "medium":
            return slot.is_mid()
        else:  # low
            return slot.is_evening() or slot.is_mid()

class ScheduledBlock(BaseModel):
    task_id: str
    task_title: str
    start: datetime
    end: datetime

def build_schedule(
    tasks: list[TaskToSchedule],
    free_slots: list[FreeSlot],
    study_start: int = 9,
    study_end: int = 22
) -> list[ScheduledBlock]:
    """
    Assigns tasks to free slots respecting energy-effort matching.
    Tasks sorted by priority. High-priority tasks get preferred slots first.
    Idempotent: same inputs → same output.
    """
    sorted_tasks = sorted(tasks, key=lambda t: t.priority_index, reverse=True)
    remaining_slots = [FreeSlot(start=s.start, end=s.end) for s in sorted(free_slots, key=lambda s: s.start)]
    result = []

    for task in sorted_tasks:
        hours = task.hours_needed
        # First pass: try preferred slots
        assigned = _try_assign(task, hours, remaining_slots, prefer_match=True)
        if not assigned:
            # Second pass: any available slot
            assigned = _try_assign(task, hours, remaining_slots, prefer_match=False)
        if assigned:
            result.append(assigned)

    return result

def _try_assign(
    task: TaskToSchedule,
    hours: float,
    slots: list[FreeSlot],
    prefer_match: bool
) -> Optional[ScheduledBlock]:
    duration = timedelta(hours=hours)
    for i, slot in enumerate(slots):
        if prefer_match and not task.prefers_slot(slot):
            continue
        if slot.duration_hours >= hours:
            block_start = slot.start
            block_end = block_start + duration
            # Consume time from slot
            slots[i] = FreeSlot(start=block_end, end=slot.end)
            if slots[i].duration_hours <= 0:
                slots.pop(i)
            return ScheduledBlock(task_id=task.id, task_title=task.title, start=block_start, end=block_end)
    return None
```

**Step 4: Run tests**

```bash
pytest tests/test_scheduler.py -v
# Expected: 4 PASSED
```

**Step 5: Commit**

```bash
git add backend/app/services/scheduler.py backend/tests/test_scheduler.py
git commit -m "feat: scheduling engine with energy-effort matching"
```

---

## Phase C: Tasks API & Brain Dump Endpoint

### Task 7: Tasks Router & Brain Dump Flow

**Files:**
- Create: `backend/app/routers/tasks.py`
- Create: `backend/app/schemas/tasks.py`
- Test: `backend/tests/test_tasks_api.py`

**Step 1: Write failing tests**

```python
# backend/tests/test_tasks_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app
from app.dependencies import get_current_user
from app.models import User
import uuid

mock_user = User(id=uuid.uuid4(), email="student@uni.edu", name="Alice", timezone="UTC")

def override_auth():
    return mock_user

app.dependency_overrides[get_current_user] = override_auth
client = TestClient(app)

def test_add_single_task():
    resp = client.post("/api/tasks", json={
        "title": "Study for exam",
        "effort": "high",
        "importance": 4
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Study for exam"
    assert data["status"] == "pending"
    assert "priority_index" in data

def test_get_today_tasks():
    resp = client.get("/api/tasks/today")
    assert resp.status_code == 200
    data = resp.json()
    assert "primary" in data
    assert "secondary" in data

@patch("app.routers.tasks.parse_brain_dump")
def test_brain_dump(mock_parse):
    from app.services.ai_parser import ParsedTask
    mock_parse.return_value = [
        ParsedTask(title="Finish ML assignment", deadline="2026-03-20", effort="high", importance=4),
        ParsedTask(title="Review notes", effort="low", importance=2)
    ]
    resp = client.post("/api/tasks/dump", json={"text": "Finish ML assignment by Friday and review notes tonight"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["tasks"]) == 2
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_tasks_api.py -v
```

**Step 3: Create schemas**

```python
# backend/app/schemas/tasks.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class TaskCreate(BaseModel):
    title: str
    deadline: Optional[datetime] = None
    effort: str = "medium"
    importance: int = 3
    context: Optional[str] = "Study"

class TaskResponse(BaseModel):
    id: uuid.UUID
    title: str
    deadline: Optional[datetime]
    effort: Optional[str]
    importance: Optional[int]
    context: Optional[str]
    priority_index: Optional[float]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class BrainDumpRequest(BaseModel):
    text: str

class BrainDumpResponse(BaseModel):
    tasks: list[TaskResponse]

class TodayResponse(BaseModel):
    primary: Optional[TaskResponse]
    secondary: list[TaskResponse]
```

**Step 4: Create tasks router**

```python
# backend/app/routers/tasks.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, Task
from app.schemas.tasks import TaskCreate, TaskResponse, BrainDumpRequest, BrainDumpResponse, TodayResponse
from app.services.ai_parser import parse_brain_dump
from app.services.matrix_scorer import score_task, TaskInput
from datetime import datetime

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

def compute_and_save_score(task: Task, db: Session) -> None:
    task_input = TaskInput(
        deadline=task.deadline,
        effort=task.effort or "medium",
        importance=task.importance or 3,
        dependency_count=0
    )
    task.priority_index = score_task(task_input)
    db.commit()

@router.post("", response_model=TaskResponse)
def add_task(req: TaskCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = Task(**req.model_dump(), user_id=user.id, status="pending")
    db.add(task)
    db.commit()
    db.refresh(task)
    compute_and_save_score(task, db)
    db.refresh(task)
    return task

@router.post("/dump", response_model=BrainDumpResponse)
async def brain_dump(req: BrainDumpRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    parsed = await parse_brain_dump(req.text, user_timezone=user.timezone)
    created = []
    for p in parsed:
        deadline = datetime.fromisoformat(p.deadline) if p.deadline else None
        task = Task(
            user_id=user.id,
            title=p.title,
            raw_input=req.text,
            deadline=deadline,
            effort=p.effort,
            importance=p.importance,
            context=p.context,
            status="pending"
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        compute_and_save_score(task, db)
        db.refresh(task)
        created.append(task)
    return BrainDumpResponse(tasks=created)

@router.get("/today", response_model=TodayResponse)
def get_today(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tasks = (
        db.query(Task)
        .filter(Task.user_id == user.id, Task.status.in_(["pending", "scheduled", "in_progress"]))
        .order_by(Task.priority_index.desc())
        .limit(4)
        .all()
    )
    primary = tasks[0] if tasks else None
    secondary = tasks[1:4] if len(tasks) > 1 else []
    return TodayResponse(primary=primary, secondary=secondary)

@router.get("", response_model=list[TaskResponse])
def list_tasks(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Task).filter(Task.user_id == user.id).order_by(Task.priority_index.desc()).all()

@router.post("/{task_id}/complete", response_model=TaskResponse)
def complete_task(task_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    task.status = "completed"
    db.commit()
    db.refresh(task)
    return task
```

**Step 5: Register router in main.py**

```python
from app.routers import auth, tasks
app.include_router(auth.router)
app.include_router(tasks.router)
```

**Step 6: Run tests**

```bash
pytest tests/test_tasks_api.py -v
# Expected: 3 PASSED
```

**Step 7: Commit**

```bash
git add backend/app/routers/tasks.py backend/app/schemas/tasks.py backend/tests/test_tasks_api.py
git commit -m "feat: tasks API with brain dump, scoring, and today view"
```

---

## Phase D: Telegram Bot

### Task 8: Telegram Bot Core

**Files:**
- Create: `backend/app/telegram/__init__.py`
- Create: `backend/app/telegram/bot.py`
- Create: `backend/app/telegram/handlers/start.py`
- Create: `backend/app/telegram/handlers/today.py`
- Create: `backend/app/telegram/handlers/dump.py`
- Create: `backend/app/routers/telegram.py`
- Test: `backend/tests/test_telegram_handlers.py`

**Step 1: Write failing tests**

```python
# backend/tests/test_telegram_handlers.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.telegram.handlers.today import format_today_message

def test_format_today_with_tasks():
    from app.schemas.tasks import TaskResponse
    from datetime import datetime
    import uuid
    primary = TaskResponse(
        id=uuid.uuid4(), title="Finish ML assignment",
        deadline=None, effort="high", importance=4,
        context="Study", priority_index=8.5, status="pending",
        created_at=datetime.utcnow()
    )
    secondary = [
        TaskResponse(id=uuid.uuid4(), title="Review notes", deadline=None, effort="low",
                     importance=2, context="Study", priority_index=3.0, status="pending",
                     created_at=datetime.utcnow())
    ]
    msg = format_today_message(primary, secondary)
    assert "Finish ML assignment" in msg
    assert "Review notes" in msg
    assert "🎯" in msg

def test_format_today_no_tasks():
    msg = format_today_message(None, [])
    assert "no tasks" in msg.lower() or "all clear" in msg.lower()
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_telegram_handlers.py -v
```

**Step 3: Create bot.py**

```python
# backend/app/telegram/bot.py
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters
from app.config import settings

DUMP_STATE = 1

def create_application() -> Application:
    from app.telegram.handlers.start import start_command
    from app.telegram.handlers.today import today_command
    from app.telegram.handlers.dump import dump_command, receive_dump, cancel

    app = Application.builder().token(settings.telegram_bot_token).build()

    dump_conv = ConversationHandler(
        entry_points=[CommandHandler("dump", dump_command)],
        states={DUMP_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_dump)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(dump_conv)
    return app
```

**Step 4: Create handlers**

```python
# backend/app/telegram/handlers/today.py
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.schemas.tasks import TaskResponse

def format_today_message(primary: Optional[TaskResponse], secondary: list[TaskResponse]) -> str:
    if not primary:
        return "✅ All clear! You have no pending tasks. Add some with /dump"
    lines = [f"🎯 *Today's focus:*\n{primary.title}"]
    if primary.effort:
        lines.append(f"   Effort: {primary.effort.capitalize()}")
    if secondary:
        lines.append("\n📋 *Also on deck:*")
        for i, t in enumerate(secondary, 1):
            lines.append(f"   {i}. {t.title}")
    return "\n".join(lines)

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This will be wired to DB via chat_id lookup
    await update.message.reply_text(
        "Fetching your tasks...",
        parse_mode="Markdown"
    )
```

```python
# backend/app/telegram/handlers/start.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📋 Today's task", callback_data="today")],
        [InlineKeyboardButton("🧠 Brain dump", callback_data="dump")],
        [InlineKeyboardButton("✅ My tasks", callback_data="tasks")],
    ]
    markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Welcome to *NextMove*!\n\nI'll help you focus on what matters most today.",
        reply_markup=markup,
        parse_mode="Markdown"
    )
```

```python
# backend/app/telegram/handlers/dump.py
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

DUMP_STATE = 1

async def dump_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧠 *Brain dump mode*\n\nTell me everything on your plate. Deadlines, assignments, anything.\n\nType it all out in one message:",
        parse_mode="Markdown"
    )
    return DUMP_STATE

async def receive_dump(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text("⏳ Parsing your tasks...")
    # Wire to AI parser + DB in full implementation
    await update.message.reply_text(f"✅ Got it! I'll process: \"{text[:50]}...\" and schedule your tasks.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END
```

**Step 5: Create Telegram webhook router**

```python
# backend/app/routers/telegram.py
from fastapi import APIRouter, Request
from telegram import Update
from app.telegram.bot import create_application

router = APIRouter(prefix="/api/telegram", tags=["telegram"])
_app = None

def get_bot_app():
    global _app
    if _app is None:
        _app = create_application()
    return _app

@router.post("/webhook")
async def telegram_webhook(request: Request):
    body = await request.json()
    update = Update.de_json(body, get_bot_app().bot)
    await get_bot_app().process_update(update)
    return {"ok": True}
```

**Step 6: Run tests**

```bash
pytest tests/test_telegram_handlers.py -v
# Expected: 2 PASSED
```

**Step 7: Commit**

```bash
git add backend/app/telegram/ backend/app/routers/telegram.py backend/tests/test_telegram_handlers.py
git commit -m "feat: Telegram bot core with start, today, and brain dump handlers"
```

---

## Phase E: Calendar Integration

### Task 9: Built-in Calendar API

**Files:**
- Create: `backend/app/routers/calendar.py`
- Create: `backend/app/schemas/calendar.py`
- Test: `backend/tests/test_calendar_api.py`

**Step 1: Write failing tests**

```python
# backend/tests/test_calendar_api.py
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from app.main import app
from app.dependencies import get_current_user
from app.models import User
import uuid

mock_user = User(id=uuid.uuid4(), email="student@uni.edu", name="Alice", timezone="UTC")
app.dependency_overrides[get_current_user] = lambda: mock_user
client = TestClient(app)

def test_create_calendar_event():
    start = datetime.utcnow() + timedelta(hours=1)
    end = start + timedelta(hours=2)
    resp = client.post("/api/calendar/events", json={
        "title": "Study session",
        "start_time": start.isoformat(),
        "end_time": end.isoformat()
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Study session"
    assert "id" in data

def test_list_calendar_events():
    resp = client.get("/api/calendar/events")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

def test_delete_calendar_event():
    start = datetime.utcnow() + timedelta(hours=3)
    end = start + timedelta(hours=1)
    create_resp = client.post("/api/calendar/events", json={
        "title": "Temp event",
        "start_time": start.isoformat(),
        "end_time": end.isoformat()
    })
    event_id = create_resp.json()["id"]
    del_resp = client.delete(f"/api/calendar/events/{event_id}")
    assert del_resp.status_code == 200
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_calendar_api.py -v
```

**Step 3: Create schemas and router**

```python
# backend/app/schemas/calendar.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class CalendarEventCreate(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime
    is_all_day: bool = False
    recurrence_rule: Optional[str] = None

class CalendarEventResponse(BaseModel):
    id: uuid.UUID
    title: str
    start_time: datetime
    end_time: datetime
    is_all_day: bool
    source: str

    class Config:
        from_attributes = True
```

```python
# backend/app/routers/calendar.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, CalendarEvent
from app.schemas.calendar import CalendarEventCreate, CalendarEventResponse

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

@router.get("/events", response_model=list[CalendarEventResponse])
def list_events(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(CalendarEvent).filter(CalendarEvent.user_id == user.id).order_by(CalendarEvent.start_time).all()

@router.post("/events", response_model=CalendarEventResponse)
def create_event(req: CalendarEventCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    event = CalendarEvent(**req.model_dump(), user_id=user.id, source="manual")
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

@router.delete("/events/{event_id}")
def delete_event(event_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    event = db.query(CalendarEvent).filter(CalendarEvent.id == event_id, CalendarEvent.user_id == user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(event)
    db.commit()
    return {"ok": True}
```

**Step 4: Register router, run tests**

```bash
pytest tests/test_calendar_api.py -v
# Expected: 3 PASSED
```

**Step 5: Commit**

```bash
git add backend/app/routers/calendar.py backend/app/schemas/calendar.py backend/tests/test_calendar_api.py
git commit -m "feat: built-in calendar CRUD API"
```

---

### Task 10: Google Calendar Integration

**Files:**
- Create: `backend/app/services/calendar_google.py`
- Test: `backend/tests/test_google_calendar.py`

**Step 1: Write failing tests**

```python
# backend/tests/test_google_calendar.py
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from app.services.calendar_google import get_free_slots, FreeSlotResult

def test_get_free_slots_returns_gaps():
    # Simulate a calendar with one event 10am-11am on a day
    mock_service = MagicMock()
    day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    event_start = day.replace(hour=10).isoformat() + "Z"
    event_end = day.replace(hour=11).isoformat() + "Z"
    mock_service.events().list().execute.return_value = {
        "items": [{"start": {"dateTime": event_start}, "end": {"dateTime": event_end}}]
    }
    slots = get_free_slots(
        service=mock_service,
        calendar_id="primary",
        date=day,
        study_start=9,
        study_end=17
    )
    # Should return: 9-10am and 11am-5pm
    assert len(slots) == 2
    assert slots[0].start.hour == 9
    assert slots[0].end.hour == 10
    assert slots[1].start.hour == 11
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_google_calendar.py -v
```

**Step 3: Implement Google Calendar service**

```python
# backend/app/services/calendar_google.py
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from app.config import settings

class FreeSlotResult(BaseModel):
    start: datetime
    end: datetime

def get_credentials(access_token: str, refresh_token: str) -> Credentials:
    return Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret
    )

def get_google_service(access_token: str, refresh_token: str):
    creds = get_credentials(access_token, refresh_token)
    return build("calendar", "v3", credentials=creds)

def get_free_slots(
    service,
    calendar_id: str,
    date: datetime,
    study_start: int = 9,
    study_end: int = 22
) -> list[FreeSlotResult]:
    day_start = date.replace(hour=study_start, minute=0, second=0, microsecond=0)
    day_end = date.replace(hour=study_end, minute=0, second=0, microsecond=0)

    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=day_start.isoformat() + "Z",
        timeMax=day_end.isoformat() + "Z",
        singleEvents=True,
        orderBy="startTime"
    ).execute()
    events = events_result.get("items", [])

    # Build busy intervals
    busy = []
    for e in events:
        start_str = e["start"].get("dateTime", e["start"].get("date"))
        end_str = e["end"].get("dateTime", e["end"].get("date"))
        busy.append((datetime.fromisoformat(start_str.replace("Z", "")),
                     datetime.fromisoformat(end_str.replace("Z", ""))))

    # Find free slots
    free = []
    cursor = day_start
    for b_start, b_end in sorted(busy):
        if cursor < b_start:
            free.append(FreeSlotResult(start=cursor, end=b_start))
        cursor = max(cursor, b_end)
    if cursor < day_end:
        free.append(FreeSlotResult(start=cursor, end=day_end))

    return free

def create_calendar_event(service, title: str, start: datetime, end: datetime, calendar_id: str = "primary") -> str:
    body = {
        "summary": title,
        "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
        "description": "Scheduled by NextMove"
    }
    created = service.events().insert(calendarId=calendar_id, body=body).execute()
    return created["id"]
```

**Step 4: Run tests**

```bash
pytest tests/test_google_calendar.py -v
# Expected: 1 PASSED
```

**Step 5: Commit**

```bash
git add backend/app/services/calendar_google.py backend/tests/test_google_calendar.py
git commit -m "feat: Google Calendar free slot detection and event creation"
```

---

## Phase F: Notification Engine

### Task 11: Morning Brief & Procrastination Detection

**Files:**
- Create: `backend/app/services/notifier.py`
- Create: `backend/app/workers/notification_jobs.py`
- Test: `backend/tests/test_notifier.py`

**Step 1: Write failing tests**

```python
# backend/tests/test_notifier.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.notifier import build_morning_brief, build_procrastination_prompt
from app.schemas.tasks import TaskResponse
from datetime import datetime
import uuid

def make_task(title, effort="medium"):
    return TaskResponse(
        id=uuid.uuid4(), title=title, deadline=None,
        effort=effort, importance=3, context="Study",
        priority_index=5.0, status="scheduled",
        created_at=datetime.utcnow()
    )

def test_morning_brief_message():
    primary = make_task("Finish stats assignment", "high")
    secondary = [make_task("Review chapter 3", "low")]
    msg = build_morning_brief("Alice", primary, secondary)
    assert "Alice" in msg
    assert "Finish stats assignment" in msg
    assert "Review chapter 3" in msg

def test_morning_brief_no_tasks():
    msg = build_morning_brief("Bob", None, [])
    assert "Bob" in msg
    assert "nothing" in msg.lower() or "clear" in msg.lower() or "no tasks" in msg.lower()

def test_procrastination_prompt():
    task = make_task("Study for econ midterm", "high")
    msg = build_procrastination_prompt(task)
    assert "econ midterm" in msg.lower() or "Study for econ midterm" in msg
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_notifier.py -v
```

**Step 3: Implement notifier**

```python
# backend/app/services/notifier.py
from typing import Optional
from app.schemas.tasks import TaskResponse

def build_morning_brief(name: str, primary: Optional[TaskResponse], secondary: list[TaskResponse]) -> str:
    greeting = f"Good morning, {name}! ☀️\n\n"
    if not primary:
        return greeting + "You have no pending tasks today. Add some with /dump 🎉"
    lines = [greeting, f"🎯 *Today's focus:*\n*{primary.title}*"]
    if primary.effort:
        lines.append(f"_(effort: {primary.effort})_")
    if secondary:
        lines.append("\n📋 *Also scheduled:*")
        for t in secondary:
            lines.append(f"• {t.title}")
    lines.append("\nYou've got this! Use /done to log completions. 💪")
    return "\n".join(lines)

def build_procrastination_prompt(task: TaskResponse) -> str:
    return (
        f"👀 Hey, you were supposed to start *{task.title}* a while ago.\n\n"
        f"What's going on?\n\n"
        f"[I'm on it ✅] [I'm stuck 🤔] [Reschedule 📅]"
    )

def build_pretask_nudge(task: TaskResponse) -> str:
    return (
        f"⏰ Starting in 15 minutes:\n*{task.title}*\n\n"
        f"Get ready — clear your space, silence your phone. You've got this."
    )

def build_evening_wrapup(completed_count: int, missed_count: int) -> str:
    if completed_count == 0 and missed_count == 0:
        return "🌙 Evening check-in: No tasks were scheduled today."
    parts = [f"🌙 *Day wrap-up:*"]
    if completed_count:
        parts.append(f"✅ Completed: {completed_count} task{'s' if completed_count > 1 else ''}")
    if missed_count:
        parts.append(f"⏭️ Rescheduled: {missed_count} task{'s' if missed_count > 1 else ''}")
    parts.append("\nSee you tomorrow! 🌟")
    return "\n".join(parts)
```

**Step 4: Run tests**

```bash
pytest tests/test_notifier.py -v
# Expected: 3 PASSED
```

**Step 5: Commit**

```bash
git add backend/app/services/notifier.py backend/tests/test_notifier.py
git commit -m "feat: notification message builders for morning brief and procrastination"
```

---

## Phase G: Web Frontend

### Task 12: Next.js App Setup + Auth

**Files:**
- Create: `frontend/app/layout.tsx`
- Create: `frontend/app/(auth)/login/page.tsx`
- Create: `frontend/lib/auth.ts`
- Create: `frontend/app/api/auth/[...nextauth]/route.ts`

**Step 1: Install dependencies**

```bash
cd frontend
npm install next-auth @auth/core axios
npm install -D @types/node
```

**Step 2: Create NextAuth config**

```typescript
// frontend/lib/auth.ts
import GoogleProvider from "next-auth/providers/google"
import CredentialsProvider from "next-auth/providers/credentials"
import type { NextAuthOptions } from "next-auth"

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
      authorization: {
        params: {
          scope: "openid email profile https://www.googleapis.com/auth/calendar"
        }
      }
    }),
    CredentialsProvider({
      name: "Email",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" }
      },
      async authorize(credentials) {
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(credentials)
        })
        if (!res.ok) return null
        const data = await res.json()
        return { id: data.user_id, email: credentials!.email, accessToken: data.access_token }
      }
    })
  ],
  callbacks: {
    async jwt({ token, account, user }) {
      if (account) token.accessToken = account.access_token
      if (user) token.backendToken = (user as any).accessToken
      return token
    },
    async session({ session, token }) {
      (session as any).accessToken = token.backendToken || token.accessToken
      return session
    }
  },
  pages: {
    signIn: "/login"
  }
}
```

```typescript
// frontend/app/api/auth/[...nextauth]/route.ts
import NextAuth from "next-auth"
import { authOptions } from "@/lib/auth"
const handler = NextAuth(authOptions)
export { handler as GET, handler as POST }
```

**Step 3: Create login page**

```tsx
// frontend/app/(auth)/login/page.tsx
"use client"
import { signIn } from "next-auth/react"
import { useState } from "react"

export default function LoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [isLogin, setIsLogin] = useState(true)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    await signIn("credentials", { email, password, callbackUrl: "/dashboard" })
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950">
      <div className="w-full max-w-sm p-8 bg-zinc-900 rounded-2xl shadow-xl border border-zinc-800">
        <h1 className="text-2xl font-bold text-white mb-2">NextMove</h1>
        <p className="text-zinc-400 text-sm mb-8">Focus on what matters today.</p>

        <button
          onClick={() => signIn("google", { callbackUrl: "/dashboard" })}
          className="w-full py-3 px-4 bg-white text-black rounded-xl font-medium hover:bg-zinc-100 transition mb-4"
        >
          Continue with Google
        </button>

        <div className="relative my-4">
          <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-zinc-700" /></div>
          <div className="relative flex justify-center text-xs text-zinc-500"><span className="px-2 bg-zinc-900">or</span></div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="email" placeholder="Email" value={email}
            onChange={e => setEmail(e.target.value)}
            className="w-full px-4 py-3 bg-zinc-800 text-white rounded-xl border border-zinc-700 focus:outline-none focus:border-zinc-500 text-sm"
          />
          <input
            type="password" placeholder="Password" value={password}
            onChange={e => setPassword(e.target.value)}
            className="w-full px-4 py-3 bg-zinc-800 text-white rounded-xl border border-zinc-700 focus:outline-none focus:border-zinc-500 text-sm"
          />
          <button type="submit" className="w-full py-3 bg-indigo-600 text-white rounded-xl font-medium hover:bg-indigo-500 transition">
            {isLogin ? "Sign In" : "Create Account"}
          </button>
        </form>

        <p className="text-center text-zinc-500 text-sm mt-4">
          {isLogin ? "No account? " : "Have an account? "}
          <button onClick={() => setIsLogin(!isLogin)} className="text-indigo-400 hover:underline">
            {isLogin ? "Sign up" : "Sign in"}
          </button>
        </p>
      </div>
    </div>
  )
}
```

**Step 4: Commit**

```bash
git add frontend/
git commit -m "feat: Next.js auth setup with Google OAuth and credentials provider"
```

---

### Task 13: Dashboard — Today's Task View

**Files:**
- Create: `frontend/app/dashboard/page.tsx`
- Create: `frontend/components/TodayCard.tsx`
- Create: `frontend/components/SecondaryTasks.tsx`
- Create: `frontend/lib/api.ts`

**Step 1: Create API client**

```typescript
// frontend/lib/api.ts
import { getSession } from "next-auth/react"

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

async function authFetch(path: string, options: RequestInit = {}) {
  const session = await getSession()
  const token = (session as any)?.accessToken
  return fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {})
    }
  })
}

export const api = {
  getTodayTasks: () => authFetch("/api/tasks/today").then(r => r.json()),
  completeTask: (id: string) => authFetch(`/api/tasks/${id}/complete`, { method: "POST" }).then(r => r.json()),
  brainDump: (text: string) => authFetch("/api/tasks/dump", { method: "POST", body: JSON.stringify({ text }) }).then(r => r.json()),
  listTasks: () => authFetch("/api/tasks").then(r => r.json()),
}
```

**Step 2: Create TodayCard component**

```tsx
// frontend/components/TodayCard.tsx
"use client"
import { useState } from "react"
import { api } from "@/lib/api"

interface Task {
  id: string
  title: string
  effort?: string
  importance?: number
  context?: string
  priority_index?: number
  status: string
}

export function TodayCard({ task, onComplete }: { task: Task; onComplete: () => void }) {
  const [completing, setCompleting] = useState(false)

  async function handleComplete() {
    setCompleting(true)
    await api.completeTask(task.id)
    onComplete()
  }

  const effortColors = { low: "text-emerald-400", medium: "text-amber-400", high: "text-rose-400" }
  const effortColor = effortColors[task.effort as keyof typeof effortColors] || "text-zinc-400"

  return (
    <div className="bg-gradient-to-br from-indigo-900/40 to-zinc-900 border border-indigo-800/50 rounded-3xl p-8">
      <p className="text-xs font-semibold text-indigo-400 uppercase tracking-widest mb-4">🎯 Today's Focus</p>
      <h2 className="text-3xl font-bold text-white mb-4 leading-tight">{task.title}</h2>
      <div className="flex gap-4 text-sm mb-8">
        {task.effort && <span className={effortColor}>⚡ {task.effort} effort</span>}
        {task.context && <span className="text-zinc-400">📚 {task.context}</span>}
      </div>
      <button
        onClick={handleComplete}
        disabled={completing}
        className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-2xl font-semibold text-lg transition disabled:opacity-50"
      >
        {completing ? "Marking done..." : "✅ Mark Complete"}
      </button>
    </div>
  )
}

export function EmptyState() {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-8 text-center">
      <div className="text-5xl mb-4">🎉</div>
      <h2 className="text-2xl font-bold text-white mb-2">All clear!</h2>
      <p className="text-zinc-400">No pending tasks. Use the brain dump below to add your commitments.</p>
    </div>
  )
}
```

**Step 3: Create Dashboard page**

```tsx
// frontend/app/dashboard/page.tsx
"use client"
import { useEffect, useState } from "react"
import { useSession } from "next-auth/react"
import { redirect } from "next/navigation"
import { api } from "@/lib/api"
import { TodayCard, EmptyState } from "@/components/TodayCard"

export default function DashboardPage() {
  const { data: session, status } = useSession()
  const [today, setToday] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [dumpText, setDumpText] = useState("")
  const [dumping, setDumping] = useState(false)

  if (status === "unauthenticated") redirect("/login")

  async function loadToday() {
    const data = await api.getTodayTasks()
    setToday(data)
    setLoading(false)
  }

  useEffect(() => { loadToday() }, [])

  async function handleDump(e: React.FormEvent) {
    e.preventDefault()
    if (!dumpText.trim()) return
    setDumping(true)
    await api.brainDump(dumpText)
    setDumpText("")
    setDumping(false)
    loadToday()
  }

  if (loading) return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
      <div className="text-zinc-400">Loading your tasks...</div>
    </div>
  )

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      <nav className="border-b border-zinc-900 px-6 py-4 flex items-center justify-between">
        <span className="font-bold text-lg">NextMove</span>
        <div className="flex gap-6 text-sm text-zinc-400">
          <a href="/dashboard" className="text-white">Today</a>
          <a href="/tasks" className="hover:text-white transition">Tasks</a>
          <a href="/schedule" className="hover:text-white transition">Schedule</a>
          <a href="/settings" className="hover:text-white transition">Settings</a>
        </div>
      </nav>

      <main className="max-w-2xl mx-auto px-4 py-10 space-y-6">
        {today?.primary ? (
          <TodayCard task={today.primary} onComplete={loadToday} />
        ) : (
          <EmptyState />
        )}

        {today?.secondary?.length > 0 && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
            <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-4">Also scheduled</p>
            <div className="space-y-3">
              {today.secondary.map((t: any) => (
                <div key={t.id} className="flex items-center justify-between py-2 border-b border-zinc-800 last:border-0">
                  <span className="text-zinc-200 text-sm">{t.title}</span>
                  <span className="text-xs text-zinc-500">{t.effort}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Brain dump */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
          <p className="text-sm font-semibold text-zinc-300 mb-3">🧠 Brain dump</p>
          <form onSubmit={handleDump} className="space-y-3">
            <textarea
              value={dumpText}
              onChange={e => setDumpText(e.target.value)}
              placeholder="Tell me everything on your plate... deadlines, assignments, anything."
              className="w-full h-28 bg-zinc-800 text-white rounded-xl px-4 py-3 text-sm border border-zinc-700 focus:outline-none focus:border-zinc-500 resize-none placeholder-zinc-600"
            />
            <button
              type="submit"
              disabled={dumping || !dumpText.trim()}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-sm font-semibold transition disabled:opacity-40"
            >
              {dumping ? "Processing..." : "Parse & Schedule →"}
            </button>
          </form>
        </div>
      </main>
    </div>
  )
}
```

**Step 4: Commit**

```bash
git add frontend/app/dashboard/ frontend/components/ frontend/lib/api.ts
git commit -m "feat: dashboard with today's task card and brain dump UI"
```

---

## Phase H: Wire Everything Together

### Task 14: End-to-End Integration & Scheduling Trigger

**Files:**
- Modify: `backend/app/routers/tasks.py` (add schedule trigger after brain dump)
- Create: `backend/app/services/schedule_runner.py`
- Test: `backend/tests/test_schedule_runner.py`

**Step 1: Write failing test**

```python
# backend/tests/test_schedule_runner.py
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from app.services.schedule_runner import run_schedule_for_user

def test_run_schedule_creates_blocks(db_session, mock_user):
    # Add 2 tasks
    from app.models import Task
    t1 = Task(user_id=mock_user.id, title="Study", effort="high", importance=4, status="pending", priority_index=8.0)
    t2 = Task(user_id=mock_user.id, title="Review", effort="low", importance=2, status="pending", priority_index=3.0)
    db_session.add_all([t1, t2])
    db_session.commit()

    with patch("app.services.schedule_runner.get_free_slots_for_user") as mock_slots:
        base = datetime.utcnow().replace(hour=9, minute=0, second=0, microsecond=0)
        mock_slots.return_value = [
            {"start": base, "end": base + timedelta(hours=4)},
            {"start": base + timedelta(hours=6), "end": base + timedelta(hours=8)}
        ]
        run_schedule_for_user(mock_user, db_session)

    from app.models import ScheduleBlock
    blocks = db_session.query(ScheduleBlock).filter_by(user_id=mock_user.id).all()
    assert len(blocks) == 2
```

**Step 2: Implement schedule runner**

```python
# backend/app/services/schedule_runner.py
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.models import User, Task, ScheduleBlock
from app.services.scheduler import build_schedule, FreeSlot, TaskToSchedule
from app.services.calendar_google import get_free_slots as google_free_slots, get_google_service
from app.services.calendar_builtin import get_builtin_free_slots

def get_free_slots_for_user(user: User, date: datetime) -> list[FreeSlot]:
    if user.uses_google_calendar and user.google_access_token:
        service = get_google_service(user.google_access_token, user.google_refresh_token)
        slots = google_free_slots(service, "primary", date, user.study_start_hour, user.study_end_hour)
    else:
        slots = get_builtin_free_slots(user.id, date, user.study_start_hour, user.study_end_hour)
    return [FreeSlot(start=s.start, end=s.end) for s in slots]

def run_schedule_for_user(user: User, db: Session, date: datetime = None) -> None:
    if date is None:
        date = datetime.utcnow()

    tasks = db.query(Task).filter(
        Task.user_id == user.id,
        Task.status.in_(["pending", "rescheduled"])
    ).order_by(Task.priority_index.desc()).all()

    if not tasks:
        return

    free_slots = get_free_slots_for_user(user, date)
    tasks_to_schedule = [
        TaskToSchedule(id=str(t.id), title=t.title, effort=t.effort or "medium", priority_index=t.priority_index or 5.0)
        for t in tasks
    ]
    scheduled = build_schedule(tasks_to_schedule, free_slots, user.study_start_hour, user.study_end_hour)

    # Clear existing future blocks for user
    db.query(ScheduleBlock).filter(
        ScheduleBlock.user_id == user.id,
        ScheduleBlock.start_time >= datetime.utcnow()
    ).delete()

    task_map = {str(t.id): t for t in tasks}
    for block in scheduled:
        task = task_map.get(block.task_id)
        if task:
            sb = ScheduleBlock(
                task_id=task.id, user_id=user.id,
                start_time=block.start, end_time=block.end
            )
            db.add(sb)
            task.status = "scheduled"

    db.commit()
```

**Step 3: Create built-in calendar free slots service**

```python
# backend/app/services/calendar_builtin.py
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import CalendarEvent
from app.services.scheduler import FreeSlot
import uuid

def get_builtin_free_slots(
    user_id: uuid.UUID,
    date: datetime,
    study_start: int = 9,
    study_end: int = 22,
    db: Session = None
) -> list[FreeSlot]:
    """Find free time blocks for a user on a given day using built-in calendar."""
    day_start = date.replace(hour=study_start, minute=0, second=0, microsecond=0)
    day_end = date.replace(hour=study_end, minute=0, second=0, microsecond=0)

    if db is None:
        return [FreeSlot(start=day_start, end=day_end)]

    events = db.query(CalendarEvent).filter(
        CalendarEvent.user_id == user_id,
        CalendarEvent.start_time >= day_start,
        CalendarEvent.start_time < day_end
    ).order_by(CalendarEvent.start_time).all()

    free = []
    cursor = day_start
    for e in events:
        if cursor < e.start_time:
            free.append(FreeSlot(start=cursor, end=e.start_time))
        cursor = max(cursor, e.end_time)
    if cursor < day_end:
        free.append(FreeSlot(start=cursor, end=day_end))

    return free
```

**Step 4: Trigger schedule after brain dump**

```python
# Modify backend/app/routers/tasks.py — add after creating tasks in /dump endpoint:
from app.services.schedule_runner import run_schedule_for_user
# After db.commit() for all parsed tasks:
run_schedule_for_user(user, db)
```

**Step 5: Commit**

```bash
git add backend/app/services/schedule_runner.py backend/app/services/calendar_builtin.py backend/tests/test_schedule_runner.py
git commit -m "feat: schedule runner wires AI parse → matrix score → calendar assignment"
```

---

## Phase I: Final Polish & Testing

### Task 15: Full Test Suite & Integration Smoke Test

**Step 1: Run full test suite**

```bash
cd backend && pytest -v --tb=short
# All tests should pass
```

**Step 2: Manual smoke test**

```bash
# Start everything
docker-compose up -d

# Register a user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@uni.edu","password":"test123","name":"Alice"}'

# Brain dump
curl -X POST http://localhost:8000/api/tasks/dump \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"text":"I need to finish my stats assignment by Thursday and study for econ midterm next Tuesday"}'

# Get today's task
curl http://localhost:8000/api/tasks/today \
  -H "Authorization: Bearer <token>"
```

**Step 3: Set Telegram webhook (dev)**

```bash
# Start ngrok
ngrok http 8000

# Set webhook
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<ngrok-url>/api/telegram/webhook"
```

**Step 4: Final commit**

```bash
git add .
git commit -m "feat: NextMove MVP — AI task parsing, scheduling, Telegram bot, web dashboard"
```

---

## Summary — What Gets Built

| Phase | Deliverable |
|---|---|
| A | Docker scaffold, DB models, JWT auth |
| B | AI parser (OpenAI), matrix scorer, scheduling engine |
| C | Tasks REST API, brain dump endpoint |
| D | Telegram bot (start, today, brain dump, procrastination) |
| E | Built-in calendar + Google Calendar integration |
| F | Notification messages (morning brief, nudges) |
| G | Next.js web app (login, dashboard, today card) |
| H | Full pipeline: dump → parse → score → schedule → calendar |
| I | Test suite, smoke test, webhook setup |
