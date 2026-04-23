import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from passlib.context import CryptContext

# 1. Leer la URL de Neon de tu archivo .env local
load_dotenv()
neon_url = os.getenv("NEON_DATABASE_URL")

# Correcciones para Neon
if neon_url.startswith("postgres://"):
    neon_url = neon_url.replace("postgres://", "postgresql://", 1)
if "sslmode" not in neon_url:
    separator = "&" if "?" in neon_url else "?"
    neon_url += f"{separator}sslmode=require"

# 2. Conectar y encriptar
engine = create_engine(neon_url)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 3. La contraseña de Luis
nueva_pass = "luis7654"
hash_seguro = pwd_context.hash(nueva_pass)

# 4. Inyectar en Neon
print("🔌 Conectando a Neon...")
try:
    with engine.begin() as conn:
        res = conn.execute(
            text("UPDATE users SET password_hash = :hash WHERE username = 'luisfranco'"),
            {"hash": hash_seguro}
        )
        if res.rowcount > 0:
            print("✅ ¡ÉXITO TOTAL! La contraseña de 'luisfranco' fue inyectada en Neon.")
            print("👉 Ve a la app en vivo en tu navegador e intenta entrar con: luis7654")
        else:
            print("⚠️ No se encontró al usuario 'luisfranco'.")
except Exception as e:
    print(f"❌ Error conectando a Neon: {e}")