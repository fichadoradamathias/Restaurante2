from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

# check_same_thread=False es necesario para SQLite en Streamlit
DATABASE_URL = "sqlite:///./data/db.sqlite"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)