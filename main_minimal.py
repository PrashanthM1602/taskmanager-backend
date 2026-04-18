# from fastapi import FastAPI, HTTPException, Depends
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.security import OAuth2PasswordRequestForm
# from sqlalchemy.orm import Session
# from sqlalchemy import create_engine, Column, Integer, String
# from sqlalchemy.orm import sessionmaker, declarative_base
# from jose import jwt
# from pydantic import BaseModel

# # ==============================
# # 🔥 DB SETUP (SIMPLE & WORKING)
# # ==============================
# DATABASE_URL = "sqlite:///./users.db"

# engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
# SessionLocal = sessionmaker(bind=engine)
# Base = declarative_base()

# # ==============================
# # 👤 USER MODEL
# # ==============================
# class User(Base):
#     __tablename__ = "users"
#     id = Column(Integer, primary_key=True, index=True)
#     email = Column(String, unique=True)
#     password = Column(String)

# # Create table
# Base.metadata.create_all(bind=engine)

# # ==============================
# # 🚀 APP
# # ==============================
# app = FastAPI()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# SECRET_KEY = "simplekey"
# ALGORITHM = "HS256"

# # ==============================
# # 🔹 DB DEPENDENCY
# # ==============================
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

# # ==============================
# # 📦 REQUEST MODEL
# # ==============================
# class RegisterRequest(BaseModel):
#     email: str
#     password: str

# # ==============================
# # 🚀 REGISTER (NO HASH - STABLE)
# # ==============================
# @app.post("/register")
# def register(request: RegisterRequest, db: Session = Depends(get_db)):

#     existing = db.query(User).filter(User.email == request.email).first()
#     if existing:
#         raise HTTPException(status_code=400, detail="User already exists")

#     new_user = User(
#         email=request.email,
#         password=request.password   # 🔥 NO HASH (removes all errors)
#     )

#     db.add(new_user)
#     db.commit()

#     return {"message": "User created successfully"}

# # ==============================
# # 🚀 LOGIN
# # ==============================
# @app.post("/login")
# def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):

#     user = db.query(User).filter(User.email == form_data.username).first()

#     if not user or user.password != form_data.password:
#         raise HTTPException(status_code=401, detail="Invalid credentials")

#     token = jwt.encode({"sub": user.email}, SECRET_KEY, algorithm=ALGORITHM)

#     return {"access_token": token}

# # ==============================
# # TEST
# # ==============================
# @app.get("/")
# def home():
#     return {"message": "Auth working ✅"}