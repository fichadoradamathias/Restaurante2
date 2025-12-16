# services/auth.py
from sqlalchemy.orm import Session
from database.models import User, Office
from passlib.context import CryptContext

# Configuración de hashing (Estándar y compatible con bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- FUNCIONES CORE (HASHING) ---

def verify_password(plain_password, hashed_password):
    """Verifica si la contraseña coincide con el hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Genera un hash seguro de la contraseña."""
    return pwd_context.hash(password)

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

def create_user(db: Session, username, full_name, password, office_id: int = None, role="user"):
    """Crea un nuevo usuario asignando su oficina."""
    # 1. Verificar si ya existe
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return False, f"El usuario '{username}' ya existe."

    hashed_password = get_password_hash(password)
    
    # 2. Validar oficina (si se envió un ID)
    if office_id:
        office = db.query(Office).filter(Office.id == office_id).first()
        if not office:
            return False, "La oficina seleccionada no es válida."

    # 3. Crear usuario
    new_user = User(
        username=username,
        full_name=full_name,
        password_hash=hashed_password,
        role=role,
        office_id=office_id, # Guardamos la oficina
        is_active=True
    )
    
    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
        return True, "Usuario creado exitosamente."
    except Exception as e:
        db.rollback()
        return False, f"Error al crear usuario: {e}"

def update_user_details(db: Session, user_id: int, username: str, full_name: str, office_id: int, role: str, is_active: bool):
    """Actualiza datos del perfil, incluyendo la oficina."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False, "Usuario no encontrado."

    # Validación: Si el username cambió, verificar que no esté ocupado
    if user.username != username:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            return False, f"El usuario '{username}' ya existe. Elija otro."

    try:
        user.username = username
        user.full_name = full_name
        user.role = role
        user.is_active = is_active
        user.office_id = office_id # Actualizamos la oficina
        
        db.commit()
        return True, "Datos actualizados correctamente."
    except Exception as e:
        db.rollback()
        return False, f"Error al actualizar: {e}"

def reset_user_password(db: Session, user_id: int, new_password: str, actor_id: int = None):
    """
    Resetea la contraseña.
    NOTA: Acepta 'actor_id' para compatibilidad con la auditoría de la vista,
    aunque no lo usemos directamente aquí para evitar dependencias circulares.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False, "Usuario no encontrado."
    
    try:
        user.password_hash = get_password_hash(new_password)
        db.commit()
        return True, "Contraseña actualizada correctamente."
    except Exception as e:
        db.rollback()
        return False, f"Error al cambiar contraseña: {e}"
