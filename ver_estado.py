# ver_estado.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
url = os.getenv("NEON_DATABASE_URL").replace("postgres://", "postgresql://", 1)
engine = create_engine(url)

with engine.connect() as conn:
    res = conn.execute(text("SELECT username, password_hash FROM users WHERE username = 'luisfranco'")).fetchone()
    if res:
        hash_val = res[1]
        print(f"👤 Usuario: {res[0]}")
        if hash_val.startswith("$2b$"):
            print("✅ EL HASH ESTÁ PERFECTO. El problema es solo de conexión/caché de Streamlit.")
        else:
            print("❌ EL HASH ESTÁ ROTO (es texto plano). Hay que arreglarlo con el script de rescate.")
    else:
        print("❓ El usuario no existe en Neon.")