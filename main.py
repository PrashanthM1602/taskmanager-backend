from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter
import strawberry
from database import engine, SessionLocal
from models import Base, Task
from datetime import datetime
from typing import Optional, List

from PyPDF2 import PdfReader
from groq import Groq
import json
from datetime import datetime, timedelta
from io import BytesIO
from fastapi import UploadFile, File
import schemas
from fastapi import Depends



# ============================
# GraphQL Types
# ============================

@strawberry.type
class TaskType:
    id: int
    title: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    due_date: Optional[datetime]
    parent_id: Optional[int]

    # 🔥 NEW
    subtasks: Optional[List["TaskType"]] = None


@strawberry.type
class ProductivityAnalyticsType:
    total_tasks: int
    completed_tasks: int
    pending_tasks: int
    average_completion_time_hours: float
    productivity_score: float
    delay_percentage: float
    on_time_rate: float


# ============================
# Query
# ============================

@strawberry.type
class Query:

    @strawberry.field
    def tasks(self) -> List[TaskType]:
        db = SessionLocal()
        all_tasks = db.query(Task).all()
        db.close()

        parents = [t for t in all_tasks if t.parent_id is None]
        children = [t for t in all_tasks if t.parent_id is not None]

        result = []

        for parent in parents:
            parent.subtasks = [
                child for child in children if child.parent_id == parent.id
            ]
            result.append(parent)

        return result

    @strawberry.field
    def productivity_analytics(self) -> ProductivityAnalyticsType:
        db = SessionLocal()
        tasks = db.query(Task).all()
        db.close()

        if not tasks:
            return ProductivityAnalyticsType(
                total_tasks=0,
                completed_tasks=0,
                pending_tasks=0,
                average_completion_time_hours=0.0,
                productivity_score=0.0,
                delay_percentage=0.0,
                on_time_rate=0.0,
            )

        total_tasks = len(tasks)
        completed_tasks = len([t for t in tasks if t.status == "completed"])
        pending_tasks = len([t for t in tasks if t.status == "pending"])

        # ============================
        # Average Completion Time
        # ============================

        completion_times = []

        for task in tasks:
            if task.completed_at is not None:
                diff = task.completed_at - task.created_at
                completion_times.append(diff.total_seconds() / 3600)

        avg_completion = (
            sum(completion_times) / len(completion_times)
           if completion_times else 0.0
         )

        # ============================
        # Productivity Score
        # ============================

        productivity_score = (
            (completed_tasks / total_tasks) * 100
            if total_tasks > 0 else 0
        )

        # ============================
        # Delay Analysis
        # ============================

        delayed_count = 0

        for task in tasks:
            if (
                task.status == "completed"
                and task.due_date is not None
                and task.completed_at is not None
                and task.completed_at > task.due_date
            ):
                delayed_count += 1

        delay_percentage = (
            (delayed_count / completed_tasks) * 100
            if completed_tasks > 0 else 0
        )

        on_time_rate = 100 - delay_percentage

        return ProductivityAnalyticsType(
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            pending_tasks=pending_tasks,
            average_completion_time_hours=avg_completion,
            productivity_score=productivity_score,
            delay_percentage=delay_percentage,
            on_time_rate=on_time_rate,
        )


# ============================
# Mutation
# ============================

@strawberry.type
class Mutation:

    @strawberry.mutation
    def create_task(
        self,
        title: str,
        due_date: Optional[datetime] = None
    ) -> TaskType:

        db = SessionLocal()

        new_task = Task(
            title=title,
            due_date=due_date,
        )

        db.add(new_task)
        db.commit()
        db.refresh(new_task)
        db.close()

        return new_task

    @strawberry.mutation
    def complete_task(self, task_id: int) -> TaskType:
        db = SessionLocal()

        task = db.query(Task).filter(Task.id == task_id).first()

        if not task:
            db.close()
            raise Exception("Task not found")

        task.status = "completed"
        task.completed_at = datetime.utcnow()

        db.commit()
        db.refresh(task)
        db.close()

        return task

    @strawberry.mutation
    def delete_task(self, task_id: int) -> bool:
     db = SessionLocal()

     try:
        task = db.query(Task).filter(Task.id == task_id).first()

        if not task:
            db.close()
            raise Exception("Task not found")

        # 🔥 If parent → delete all children first
        db.query(Task).filter(Task.parent_id == task_id).delete()

        # 🔥 Then delete parent
        db.delete(task)

        db.commit()
        return True

     except Exception as e:
        db.rollback()
        raise Exception(str(e))

     finally:
        db.close()

# ============================
# Schema
# ============================

schema = strawberry.Schema(query=Query, mutation=Mutation)


# ============================
# FastAPI App
# ============================


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()  # ✅ FIRST create app

app.add_middleware(   # ✅ THEN add CORS
    CORSMiddleware,
    allow_origins=[
    "https://taskmanger-rouge-six.vercel.app"
],  # for now (later restrict)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")


# ============================
# Create Tables
# ============================

Base.metadata.create_all(bind=engine)

import os
from dotenv import load_dotenv

load_dotenv()

# 🔥 Replace with your real key
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

pdf_store = {}

# 🔹 Extract text (simple & stable)
def extract_text(file_bytes):
    text = ""
    try:
        reader = PdfReader(BytesIO(file_bytes))
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as e:
        print("PDF read error:", e)

    return text.strip()


# 🔹 Smart duration
def smart_duration(title):
    title = title.lower()

    if "install" in title:
        return 30
    elif "setup" in title:
        return 20
    elif "learn" in title:
        return 30
    elif "create" in title:
        return 40
    elif "analyze" in title:
        return 25
    else:
        return 15


def generate_timeline(tasks, start_date, end_date):
    start = datetime.strptime(start_date, "%d/%m/%Y")
    end = datetime.strptime(end_date, "%d/%m/%Y")

    total_days = (end - start).days + 1
    total_tasks = len(tasks)

    if total_days <= 0:
        total_days = 1

    # 🔥 SMART DISTRIBUTION
    base = total_tasks // total_days
    extra = total_tasks % total_days

    enriched_tasks = []
    task_index = 0
    current_date = start

    for day in range(total_days):
        # distribute extra tasks to first few days
        tasks_today = base + (1 if day < extra else 0)

        for _ in range(tasks_today):
            if task_index >= total_tasks:
                break

            task = tasks[task_index]

            duration = task.get("duration_minutes") or smart_duration(task["title"])

            enriched_tasks.append({
                "title": task["title"],
                "duration_minutes": duration,
                "date": current_date.strftime("%d/%m/%Y"),
                "source": "ai"
            })

            task_index += 1

        current_date += timedelta(days=1)

    return enriched_tasks


# 🔹 Parent task
def build_parent_task(tasks,title):
    if not tasks:
        return {}

    return {
        "title": title,
        "start_date": tasks[0]["date"],
        "end_date": tasks[-1]["date"],
        "due_date": tasks[-1]["date"],
        "total_tasks": len(tasks),
        "source": "ai_group",
        "tasks": tasks
    }


# 🔹 Home
@app.get("/")
def home():
    return {"message": "AI PDF Task Engine Running 🚀"}


# 🔹 Upload PDF
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()

        text = extract_text(file_bytes)

        if not text:
            return {
                "error": "❌ This PDF has no readable text (scanned PDFs not supported)"
            }

        pdf_store["user"] = text

        return {
            "message": "PDF uploaded successfully",
            "preview": text[:200]
        }

    except Exception as e:
        return {"error": str(e)}


# 🔹 PDF → AI Tasks
@app.get("/pdf-to-tasks")
def pdf_to_tasks():

    text = pdf_store.get("user", "")

    if not text:
        return {"error": "No valid PDF uploaded"}

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "Return only valid JSON. No explanation."
                },
                {
                    "role": "user",
                    "content": f"""
From the given text:

1. Generate a short meaningful title (max 6 words)
2. Extract actionable tasks
3. Estimate duration (minutes)

Return ONLY JSON like:

{{
  "title": "",
  "tasks": [
    {{
      "title": "",
      "duration_minutes": 0
    }}
  ]
}}

Text:
{text[:2000]}
"""
                }
            ],
            temperature=0.2
        )

        result = response.choices[0].message.content.strip()
        result = result.replace("```json", "").replace("```", "").strip()

        data = json.loads(result)

        ai_title = data.get("title", "AI Generated Tasks")
        tasks_json = data.get("tasks", [])

        # 🔥 STEP 1: Apply scheduling
        start_date = datetime.now().strftime("%d/%m/%Y")

        # 🔥 YOU CAN HARDCODE OR PASS FROM FRONTEND
        end_date = (datetime.now() + timedelta(days=7)).strftime("%d/%m/%Y")

        tasks_with_time = generate_timeline(tasks_json, start_date, end_date)

        # 🔥 STEP 2: SAVE USING CORRECT FUNCTION (IMPORTANT)
        parent = save_ai_tasks_to_db(tasks_with_time, ai_title)

        # 🔥 STEP 3: Build response for UI
        parent_task = build_parent_task(tasks_with_time, ai_title)

        return {
            "message": "AI tasks saved successfully",
            "count": len(tasks_with_time),
            "ai_task_group": parent_task
        }

    except Exception as e:
        return {"error": str(e)}


@app.delete("/delete-all-tasks")
def delete_all_tasks():
    db = SessionLocal()

    try:
        db.query(Task).delete()
        db.commit()
        return {"message": "All tasks deleted"}

    except Exception as e:
        db.rollback()
        return {"error": str(e)}

    finally:
        db.close()

from datetime import datetime
from database import SessionLocal
from models import Task

def save_ai_tasks_to_db(tasks, ai_title):
    db = SessionLocal()

    try:
        # 👉 1. CREATE PARENT TASK
        parent = Task(
            title=ai_title,
            status="pending",
            due_date=None
        )

        db.add(parent)
        db.commit()
        db.refresh(parent)

        saved_children = []

        # 👉 2. CREATE CHILD TASKS
        for task in tasks:
            try:
                due_date = datetime.strptime(task["date"], "%d/%m/%Y")
            except:
                due_date = None

            new_task = Task(
                title=task["title"],
                status="pending",
                due_date=due_date,
                parent_id=parent.id   # 🔥 LINK CHILD → PARENT
            )

            db.add(new_task)
            saved_children.append(new_task)

        db.commit()

        # 👉 3. REFRESH CHILDREN
        for child in saved_children:
            db.refresh(child)

        return parent

    except Exception as e:
        db.rollback()
        print("❌ ERROR:", e)
        return None

    finally:
        db.close()

# ============================
# IMPORTS
# ============================
from pydantic import BaseModel
from typing import Optional

# ============================
# REQUEST MODEL
# ============================
class AskPDFRequest(BaseModel):
    question: Optional[str] = None
    mode: Optional[str] = None


# ============================
# PDF ASSISTANT API (SMART)
# ============================
@app.post("/ask-pdf")
def ask_pdf(request: AskPDFRequest):

    text = pdf_store.get("user", "")

    if not text:
        return {"error": "No PDF uploaded"}

    # ============================
    # 🔥 MODE INSTRUCTIONS (SMART)
    # ============================
    mode_instruction = ""

    if request.mode == "task":
      mode_instruction = (
        "Extract actionable tasks from the document.\n"
        "Include deadlines if mentioned.\n"
        "Format as bullet points.\n"
        "Each task should be clear and short."
     )

    elif request.mode == "insight":
       mode_instruction = (
          "Extract key insights, important ideas, and main concepts.\n"
          "Focus on understanding and meaning.\n"
          "Use clean bullet points."
      )

    elif request.mode == "study":
       mode_instruction = (
        "Explain the content in a very simple and beginner-friendly way.\n"
        "Use examples and simple language.\n"
        "Avoid technical complexity."
      )

    elif request.mode == "risk":
       mode_instruction = (
         "Identify deadlines, risks, warnings, or important constraints.\n"
            "Highlight anything time-sensitive or critical.\n"
            "Use bullet points."
        )

    # ============================
    # 🔥 SMART PROMPT BUILDING
    # ============================

    if request.question:
        user_prompt = f"""
You are answering a user's question based on a PDF.

Question:
{request.question}

Instructions:
{mode_instruction if mode_instruction else "Answer clearly and directly."}

Rules:
- Answer ONLY from PDF content
- Be structured (use bullets if needed)
- Keep answer clean and readable
"""
    else:
        user_prompt = f"""
Task:
{mode_instruction if mode_instruction else "Summarize the document clearly."}

Rules:
- Use structured format
- Avoid long paragraphs
- Be concise and useful
"""

    # ============================
    # 🔥 AI CALL
    # ============================
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional AI PDF assistant.\n"
                        "Strictly use only the provided PDF content.\n"
                        "If answer is not found, respond exactly with: 'Not found in document'.\n\n"
                        "Always format responses like:\n"
                        "- Use headings when needed\n"
                        "- Use bullet points\n"
                        "- Keep answers clean and readable\n"
                    )
                },
                {
                    "role": "user",
                    "content": f"""
PDF Content:
{text[:4000]}

{user_prompt}
"""
                }
            ],
            temperature=0.2  # 🔥 more precise
        )

        answer = response.choices[0].message.content.strip()

        # ============================
        # 🔥 CLEAN OUTPUT (IMPORTANT)
        # ============================
        answer = (
            answer
            .replace("**", "")
            .replace("###", "")
            .replace("##", "")
        )

        return {
            "mode": request.mode,
            "question": request.question,
            "answer": answer
        }

    except Exception as e:
        return {"error": str(e)}


from database import SessionLocal
from sqlalchemy.orm import Session

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


import models
from database import engine

models.Base.metadata.create_all(bind=engine)

@app.post("/notes", response_model=schemas.StickyResponse)
def create_note(note: schemas.StickyCreate, db: Session = Depends(get_db)):
    new_note = models.StickyNote(**note.dict())

    db.add(new_note)
    db.commit()
    db.refresh(new_note)

    return new_note

@app.get("/notes", response_model=list[schemas.StickyResponse])
def get_notes(db: Session = Depends(get_db)):
    return db.query(models.StickyNote).order_by(models.StickyNote.id.desc()).all()


@app.put("/notes/{note_id}", response_model=schemas.StickyResponse)
def update_note(note_id: int, note: schemas.StickyCreate, db: Session = Depends(get_db)):
    db_note = db.query(models.StickyNote).filter(models.StickyNote.id == note_id).first()

    if not db_note:
        return {"error": "Note not found"}

    db_note.title = note.title
    db_note.content = note.content
    db_note.color = note.color

    db.commit()
    db.refresh(db_note)

    return db_note

@app.delete("/notes/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db)):
    db_note = db.query(models.StickyNote).filter(models.StickyNote.id == note_id).first()

    if not db_note:
        return {"error": "Note not found"}

    db.delete(db_note)
    db.commit()

    return {"message": "Deleted successfully"}


# ==============================
# 🔐 AUTH (ADD THIS AT BOTTOM)
# ==============================

from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Session
from jose import jwt
from pydantic import BaseModel



from models import User
# ==============================
# 👤 USER MODEL
# ==============================
# class User(Base):
#     __tablename__ = "users"

#     id = Column(Integer, primary_key=True, index=True)
#     email = Column(String, unique=True)
#     password = Column(String)

# ==============================
# 🔐 CONFIG
# ==============================
SECRET_KEY = "simplekey"
ALGORITHM = "HS256"

# ==============================
# 📦 REQUEST MODEL
# ==============================
class RegisterRequest(BaseModel):
    email: str
    password: str

# ==============================
# 🚀 REGISTER
# ==============================
@app.post("/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):

    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    new_user = User(
        email=request.email,
        password=request.password
    )

    db.add(new_user)
    db.commit()

    return {"message": "User created successfully"}

# ==============================
# 🚀 LOGIN
# ==============================
@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):

    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or user.password != form_data.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = jwt.encode({"sub": user.email}, SECRET_KEY, algorithm=ALGORITHM)

    return {"access_token": token}