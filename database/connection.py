import os
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 1. Definir la URL de la base de datos de forma segura
DATABASE_URL = ""

# Intentamos leer los secretos de manera defensiva
try:
    # Buscamos la variable de entorno estándar de Neon
    if "NEON_DATABASE_URL" in st.secrets:
        DATABASE_URL = st.secrets["NEON_DATABASE_URL"]
        
        # Corrección de protocolo para SQLAlchemy
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
            
        # Requisito obligatorio para Neon (SSL)
        if "sslmode" not in DATABASE_URL:
            separator = "&" if "?" in DATABASE_URL else "?"
            DATABASE_URL += f"{separator}sslmode=require"
            
        print("✅ Conectado a PostgreSQL (Nube/Neon).")
    else:
        raise ValueError("No se encontró NEON_DATABASE_URL.")
except Exception as e:
    # BLOQUE FALLBACK: Si falla lo anterior, usamos SQLite local
    DATA_DIR = "data"
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    db_path = os.path.join(os.getcwd(), DATA_DIR, "db.sqlite")
    DATABASE_URL = f"sqlite:///{db_path}"
    print(f"⚠️ Usando SQLite local en: {DATABASE_URL}")

# 2. Configurar el motor
if "sqlite" in DATABASE_URL:
    # Configuración específica para SQLite
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    # Configuración para PostgreSQL (Neon)
    engine = create_engine(
        DATABASE_URL, 
        pool_pre_ping=True
    )

# 3. Sesión
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    from database.models import Base
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Base de datos inicializada correctamente.")
    except Exception as e:
        print(f"❌ Error al inicializar la BD: {e}")