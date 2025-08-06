"""
Simple Database Models for Quick Production Deployment
====================================================
Simplified version of the complex models for immediate use
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class User(Base):
    """Simplified User model"""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="parent", nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    phone_number = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    children = relationship("Child", back_populates="parent")

class Child(Base):
    """Simplified Child model"""
    __tablename__ = "children"
    
    id = Column(String, primary_key=True)
    parent_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    avatar_url = Column(String(500), nullable=True)
    safety_score = Column(Float, default=100.0, nullable=False)
    is_online = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_active = Column(DateTime, nullable=True)
    
    # Relationships
    parent = relationship("User", back_populates="children")
    interactions = relationship("Interaction", back_populates="child")
    safety_alerts = relationship("SafetyAlert", back_populates="child")

class Interaction(Base):
    """Simplified Interaction model"""
    __tablename__ = "interactions"
    
    id = Column(String, primary_key=True)
    child_id = Column(String, ForeignKey("children.id"), nullable=False)
    message = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=False)
    safety_score = Column(Float, default=100.0, nullable=False)
    flagged = Column(Boolean, default=False, nullable=False)
    flag_reason = Column(String(200), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    child = relationship("Child", back_populates="interactions")

class SafetyAlert(Base):
    """Simplified Safety Alert model"""
    __tablename__ = "safety_alerts"
    
    id = Column(String, primary_key=True)
    child_id = Column(String, ForeignKey("children.id"), nullable=False)
    type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    message = Column(Text, nullable=False)
    resolved = Column(Boolean, default=False, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    
    # Relationships  
    child = relationship("Child", back_populates="safety_alerts")