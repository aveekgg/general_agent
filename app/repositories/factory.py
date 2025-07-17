from typing import Type
from app.repositories.base_repository import BaseProductRepository
from app.repositories.sqlite_repository import SQLiteProductRepository
from app.core.config import BusinessType, settings


def create_product_repository(business_type: BusinessType = None) -> BaseProductRepository:
    """Factory function to create appropriate repository based on configuration"""
    
    database_url = settings.database_url
    
    if database_url.startswith("sqlite"):
        return SQLiteProductRepository(database_url)
    elif database_url.startswith("postgresql"):
        # Future: Add PostgreSQL/Supabase repository
        raise NotImplementedError("PostgreSQL repository not yet implemented")
    else:
        # Future: Add external API repository
        raise NotImplementedError("External API repository not yet implemented")


# Global repository instance
_repository_instance = None


def get_product_repository(business_type: BusinessType = None) -> BaseProductRepository:
    """Get singleton repository instance"""
    global _repository_instance
    
    if _repository_instance is None:
        _repository_instance = create_product_repository(business_type)
    
    return _repository_instance 