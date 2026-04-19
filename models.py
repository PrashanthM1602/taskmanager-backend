from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime
from database import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    status = Column(String, default="pending")

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
     # 🔥 NEW FIELD (for parent-child relationship)
    parent_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)


from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from database import Base

class StickyNote(Base):
    __tablename__ = "sticky_notes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    color = Column(String, default="#ffeb3b")

    created_at = Column(DateTime, default=datetime.utcnow)

from sqlalchemy import Column, Integer, String
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)

class PDFData(Base):
    __tablename__ = "pdf_data"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False)