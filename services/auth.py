import bcrypt
from sqlalchemy.orm import Session
from database.models import User
from services.audit_service import create_log_entry # ⬅️ 1. NUEVA IMPORTACIÓN

# --- FUNCIONES CORE (HASHING) ---

def get_password_hash(password: str) -> str:
    """Genera un hash seguro de la contraseña usando bcrypt puro."""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña coincide con el hash."""
    try:
        pwd_bytes = plain_password.encode('utf-8')
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False

# --- AUTENTICACIÓN (LOGIN) ---

def authenticate_user(db: Session, username: str, password: str):
    """Busca al usuario y valida su contraseña."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None 
    return user

# --- GESTIÓN DE USUARIOS (CRUD) ---

def create_user(db: Session, username, full_name, password, role="user"):
    """Crea un nuevo usuario en la base de datos."""
    # 1. Verificar si ya existe
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return False, "El nombre de usuario ya existe."
    
    # 2. Hashear password
    hashed_pwd = get_password_hash(password)
    
    # 3. Crear usuario
    new_user = User(
        username=username,
        full_name=full_name,
        password_hash=hashed_pwd,
        role=role,
        is_active=True
    )
    
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return True, f"Usuario {username} creado exitosamente."
    except Exception as e:
        db.rollback()
        return False, f"Error al crear usuario: {str(e)}"

def update_user_details(db: Session, user_id: int, username: str, full_name: str, role: str, is_active: bool):
    """Actualiza datos del perfil, INCLUYENDO el nombre de usuario (Login)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False, "Usuario no encontrado."
    
    # Validación: Si el nombre de usuario cambió, verificar que no esté ocupado
    if user.username != username:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            return False, f"El usuario '{username}' ya existe. Elija otro."

    try:
        user.username = username
        user.full_name = full_name
        user.role = role
        user.is_active = is_active
        db.commit()
        return True, "Datos actualizados correctamente."
    except Exception as e:
        db.rollback()
        return False, f"Error al actualizar: {e}"

def reset_user_password(db: Session, user_id: int, new_password: str):
    """Resetea la contraseña de un usuario específico."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False, "Usuario no encontrado."
    
    try:
        user.password_hash = get_password_hash(new_password)
        db.commit()
        
        # ⬅️ 2. INTEGRACIÓN DEL LOG DE AUDITORÍA
        try:
            # Aquí registramos que la contraseña de este usuario fue reseteada
            create_log_entry(
                db, 
                user_id=user_id, 
                action="PASSWORD_RESET_ADMIN", 
                details=f"Contraseña reseteada por un administrador. Usuario afectado: {user.username}"
            )
        except Exception as log_e:
            # Si el log falla, no queremos que falle el reset de contraseña
            print(f"Error al registrar log de auditoría: {log_e}")
            
        return True, f"Contraseña de {user.username} reseteada exitosamente."
        
    except Exception as e:
        db.rollback()
        return False, f"Error al resetear contraseña: {e}"