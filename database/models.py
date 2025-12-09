# database/models.py
import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, UniqueConstraint, Date
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

# --- NUEVO: MODELO DE OFICINA ---
class Office(Base):
    __tablename__ = "offices"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    
    # Relación inversa
    users = relationship("User", back_populates="office")

# --- USUARIOS (Modificado) ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user") 
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # NUEVO: Vinculación con Oficina
    office_id = Column(Integer, ForeignKey("offices.id"), nullable=True) # Nullable true para no romper usuarios viejos al inicio
    office = relationship("Office", back_populates="users")

    orders = relationship("Order", back_populates="user")

# --- SEMANAS ---
class Week(Base):
    __tablename__ = "weeks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, unique=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_open = Column(Boolean, default=True)
    is_finalized = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    menu_items = relationship("MenuItem", back_populates="week", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="week")
    export_logs = relationship("ExportLog", back_populates="week")

# --- ITEMS DEL MENÚ ---
class MenuItem(Base):
    __tablename__ = "menu_items"
    id = Column(Integer, primary_key=True, index=True)
    week_id = Column(Integer, ForeignKey("weeks.id"), nullable=False)
    day = Column(String, nullable=False)
    type = Column(String, nullable=False)
    option_number = Column(Integer, default=1)
    description = Column(String, nullable=False)
    
    week = relationship("Week", back_populates="menu_items")

# --- PEDIDOS ---
class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    week_id = Column(Integer, ForeignKey("weeks.id"), nullable=False)
    status = Column(String, default="success") 
    details = Column(JSON, nullable=False) 
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'week_id', name='unique_order_per_week'),
    )

    week = relationship("Week", back_populates="orders")
    user = relationship("User", back_populates="orders")

# --- LOGS DE AUDITORÍA ---
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(String, nullable=True)
    target_username = Column(String, nullable=True)
    action = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    details = Column(Text, nullable=True)

# --- LOGS DE EXPORTACIÓN ---
class ExportLog(Base):
    __tablename__ = "export_logs"
    id = Column(Integer, primary_key=True, index=True)
    week_id = Column(Integer, ForeignKey("weeks.id"))
    exported_at = Column(DateTime, default=datetime.datetime.utcnow)
    filename = Column(String, nullable=False)
    created_by = Column(String, nullable=True)

    week = relationship("Week", back_populates="export_logs")