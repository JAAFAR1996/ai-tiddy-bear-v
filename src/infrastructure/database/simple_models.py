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


# جميع الجداول تم نقلها إلى models.py وتستخدم Base الموحد.
