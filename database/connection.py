#from sqlalchemy import create_engine
#from sqlalchemy.orm import sessionmaker
#from .models import Base

   # check_same_thread=False es necesario para SQLite en Streamlit
#DATABASE_URL = "sqlite:///./data/db.sqlite"
#engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
#SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

#def init_db():
#    Base.metadata.create_all(bind=engine)



# database/connection.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import streamlit as st
import os

# 1. Definir la URL de la base de datos
# Streamlit guarda los secretos en st.secrets, si existe, usamos PostgreSQL
if "database_url" in st.secrets.connections:
    # Usar PostgreSQL en Streamlit Cloud (Producción)
    DATABASE_URL = st.secrets.connections.database_url
    print("Usando PostgreSQL en la nube (Neon).")
else:
    # Usar SQLite localmente (Desarrollo)
    DATA_DIR = "data"
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    # Nota: Si el archivo init_db.py no se puede abrir (image_cd9c05.png), 
    # verifica que la ruta sea correcta si usas 'Restaurante2' como directorio de trabajo.
    DATABASE_URL = f"sqlite:///{DATA_DIR}/db.sqlite"
    print("Usando SQLite localmente.")

# 2. Configurar el motor
# Para PostgreSQL se requiere el driver psycopg2 (instalado en Fase 1)
if DATABASE_URL.startswith("postgresql"):
    engine = create_engine(
        DATABASE_URL, 
        pool_pre_ping=True
    )
else:
    # Configuración para SQLite
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )

# 3. Sesión
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    from database.models import Base
    # Importante: Asegúrate de que Base está importada en database/models.py
    try:
        Base.metadata.create_all(bind=engine)
        print("Base de datos inicializada/actualizada.")
    except Exception as e:
        print(f"Error al inicializar la BD: {e}")