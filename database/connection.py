from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import streamlit as st
import os

# 1. Definir la URL de la base de datos de forma segura
DATABASE_URL = ""

# Intentamos leer los secretos de manera defensiva (try/except)
try:
    # Verificamos si existe la sección 'connections' y la key 'database_url'
    if "connections" in st.secrets and "database_url" in st.secrets.connections:
        DATABASE_URL = st.secrets.connections.database_url
        print("✅ Conectado a PostgreSQL (Nube/Neon).")
    else:
        # Si no hay secretos definidos, lanzamos una 'excepción' controlada para ir al 'except'
        raise ValueError("No se encontraron secretos de conexión.")
except Exception:
    # BLOQUE FALLBACK: Si falla lo anterior, usamos SQLite local
    DATA_DIR = "data"
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    # Ruta absoluta para evitar problemas
    db_path = os.path.join(os.getcwd(), DATA_DIR, "db.sqlite")
    DATABASE_URL = f"sqlite:///{db_path}"
    print(f"⚠️ No hay secretos configurados. Usando SQLite local en: {DATABASE_URL}")

# 2. Configurar el motor
if DATABASE_URL.startswith("postgresql"):
    engine = create_engine(
        DATABASE_URL, 
        pool_pre_ping=True
    )
else:
    # Configuración específica para SQLite
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
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