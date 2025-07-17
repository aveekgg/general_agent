from sqlalchemy import Column, String, Float, Boolean, Text, DateTime, JSON, Index, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, Any, Optional
import json

from app.core.config import BusinessType

Base = declarative_base()


class Product(Base):
    __tablename__ = "products"
    
    id = Column(String(255), primary_key=True)
    name = Column(String(500), nullable=False)
    description = Column(Text)
    price = Column(Float)
    category = Column(String(100))
    business_type = Column(String(50), nullable=False)
    product_metadata = Column(JSON)  # Store custom attributes like color, size, etc.
    availability = Column(Boolean, default=True)
    image_url = Column(String(1000))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes for better search performance
    __table_args__ = (
        Index('idx_business_type', 'business_type'),
        Index('idx_category', 'category'),
        Index('idx_price', 'price'),
        Index('idx_availability', 'availability'),
        Index('idx_name', 'name'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'category': self.category,
            'metadata': self.product_metadata or {},
            'availability': self.availability,
            'image_url': self.image_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], business_type: BusinessType):
        """Create Product from dictionary"""
        return cls(
            id=data['id'],
            name=data['name'],
            description=data.get('description', ''),
            price=data.get('price'),
            category=data.get('category'),
            business_type=business_type.value,
            product_metadata=data.get('metadata', {}),
            availability=data.get('availability', True),
            image_url=data.get('image_url')
        )


class ProductFacet(Base):
    __tablename__ = "product_facets"
    
    id = Column(String(255), primary_key=True)
    business_type = Column(String(50), nullable=False)
    facet_name = Column(String(100), nullable=False)  # e.g., "color", "brand", "size"
    facet_value = Column(String(255), nullable=False)  # e.g., "red", "Dell", "large"
    count = Column(Integer, default=0)  # Number of products with this facet
    
    __table_args__ = (
        Index('idx_business_type_facet', 'business_type', 'facet_name'),
        Index('idx_facet_name_value', 'facet_name', 'facet_value'),
    )


# Database utility functions
def get_database_url(business_type: BusinessType) -> str:
    """Get database URL for specific business type"""
    from app.core.config import settings
    
    # For now, use single database but could be extended to per-business DBs
    return settings.database_url


def create_tables(engine):
    """Create all database tables"""
    Base.metadata.create_all(engine)


def drop_tables(engine):
    """Drop all database tables"""
    Base.metadata.drop_all(engine) 