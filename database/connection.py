import os
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 1. Definir la URL de la base de datos de forma segura
DATABASE_URL = ""

# Intentamos leer los secretos con tu estructura original
try:
    # Verificamos TU estructura exacta de secretos en Streamlit Cloud
    if "connections" in st.secrets and "database_url" in st.secrets.connections:
        DATABASE_URL = st.secrets.connections.database_url
        
        # Correcciones vitales para Neon
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
            
        if "sslmode" not in DATABASE_URL:
            separator = "&" if "?" in DATABASE_URL else "?"
            DATABASE_URL += f"{separator}sslmode=require"
            
        print("✅ Conectado a PostgreSQL (Nube/Neon).")
    else:
        raise ValueError("No se encontraron secretos de conexión [connections].")
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
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
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