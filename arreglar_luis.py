import streamlit as st
from sqlalchemy import create_engine, text
from passlib.context import CryptContext

# 1. Sacamos la URL exacta de Neon desde tus secretos
neon_url = st.secrets.connections.database_url
if neon_url.startswith("postgres://"):
    neon_url = neon_url.replace("postgres://", "postgresql://", 1)
if "sslmode" not in neon_url:
    separator = "&" if "?" in neon_url else "?"
    neon_url += f"{separator}sslmode=require"

# 2. Preparamos el motor y el encriptador
engine = create_engine(neon_url)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 3. Esta es la contraseña que usará Luis (la encriptamos aquí)
nueva_pass = "luis7654"
hash_seguro = pwd_context.hash(nueva_pass)

# 4. Inyectamos la contraseña encriptada directamente a Neon
print("🔌 Conectando a Neon para arreglar a Luis...")
try:
    with engine.begin() as conn:
        res = conn.execute(
            text("UPDATE users SET password_hash = :hash WHERE username = 'luisfranco'"),
            {"hash": hash_seguro}
        )
        if res.rowcount > 0:
            print("✅ ¡ÉXITO TOTAL! La contraseña de 'luisfranco' fue encriptada e inyectada en Neon.")
            print("👉 Ve a Streamlit ahora mismo e intenta entrar con: luis7654")
        else:
            print("⚠️ No se encontró al usuario 'luisfranco' en la base de datos.")
except Exception as e:
    print(f"❌ Error conectando a Neon: {e}")