from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import create_engine, and_, or_, func, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
import json
import re
from datetime import datetime

from app.repositories.base_repository import BaseProductRepository
from app.models.database import Product, create_tables
from app.models.schemas import ProductItem, SearchRequest, SearchResponse
from app.core.config import BusinessType, settings


class SQLiteProductRepository(BaseProductRepository):
    """SQLite implementation of product repository"""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or settings.database_url
        self.engine = create_engine(
            self.database_url,
            connect_args={"check_same_thread": False} if "sqlite" in self.database_url else {}
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Create tables if they don't exist
        create_tables(self.engine)
    
    def get_db(self) -> Session:
        """Get database session"""
        return self.SessionLocal()
    
    async def search_products(self, search_request: SearchRequest) -> SearchResponse:
        """Search for products with filters and full-text search"""
        db = self.get_db()
        try:
            # Base query
            query = db.query(Product).filter(
                Product.business_type == search_request.business_type.value
            )
            
            # Text search
            if search_request.query.strip():
                search_term = f"%{search_request.query.lower()}%"
                query = query.filter(
                    or_(
                        func.lower(Product.name).like(search_term),
                        func.lower(Product.description).like(search_term),
                        func.lower(Product.category).like(search_term)
                    )
                )
            
            # Apply filters
            query = self._apply_filters(query, search_request.filters)
            
            # Get total count before pagination
            total_count = query.count()
            
            # Apply pagination
            products = query.limit(search_request.limit).all()
            
            # Convert to ProductItem objects
            items = [self._product_to_item(product) for product in products]
            
            # Get facets
            facets = await self._get_facets_for_results(db, search_request.business_type, search_request.filters)
            
            return SearchResponse(
                items=items,
                total_count=total_count,
                facets=facets,
                suggestions=self._get_suggestions(search_request.query, items)
            )
            
        finally:
            db.close()
    
    async def get_product_by_id(self, product_id: str, business_type: BusinessType) -> Optional[ProductItem]:
        """Get a specific product by ID"""
        db = self.get_db()
        try:
            product = db.query(Product).filter(
                and_(
                    Product.id == product_id,
                    Product.business_type == business_type.value
                )
            ).first()
            
            return self._product_to_item(product) if product else None
            
        finally:
            db.close()
    
    async def get_products_by_ids(self, product_ids: List[str], business_type: BusinessType) -> List[ProductItem]:
        """Get multiple products by IDs"""
        db = self.get_db()
        try:
            products = db.query(Product).filter(
                and_(
                    Product.id.in_(product_ids),
                    Product.business_type == business_type.value
                )
            ).all()
            
            return [self._product_to_item(product) for product in products]
            
        finally:
            db.close()
    
    async def get_facets(self, business_type: BusinessType, category: str = None) -> Dict[str, List[str]]:
        """Get available facets for filtering"""
        db = self.get_db()
        try:
            return await self._get_facets_for_results(db, business_type, {"category": category} if category else {})
        finally:
            db.close()
    
    async def get_categories(self, business_type: BusinessType) -> List[str]:
        """Get available categories"""
        db = self.get_db()
        try:
            categories = db.query(Product.category).filter(
                Product.business_type == business_type.value
            ).distinct().all()
            
            return [cat[0] for cat in categories if cat[0]]
            
        finally:
            db.close()
    
    async def get_price_range(self, business_type: BusinessType, category: str = None) -> Tuple[float, float]:
        """Get min and max prices"""
        db = self.get_db()
        try:
            query = db.query(func.min(Product.price), func.max(Product.price)).filter(
                Product.business_type == business_type.value
            )
            
            if category:
                query = query.filter(Product.category == category)
            
            result = query.first()
            return (result[0] or 0.0, result[1] or 0.0)
            
        finally:
            db.close()
    
    async def create_product(self, product: ProductItem, business_type: BusinessType) -> ProductItem:
        """Create a new product"""
        db = self.get_db()
        try:
            db_product = Product.from_dict(product.dict(), business_type)
            db.add(db_product)
            db.commit()
            db.refresh(db_product)
            
            return self._product_to_item(db_product)
            
        finally:
            db.close()
    
    async def update_product(self, product_id: str, product: ProductItem, business_type: BusinessType) -> Optional[ProductItem]:
        """Update an existing product"""
        db = self.get_db()
        try:
            db_product = db.query(Product).filter(
                and_(
                    Product.id == product_id,
                    Product.business_type == business_type.value
                )
            ).first()
            
            if not db_product:
                return None
            
            # Update fields
            for field, value in product.dict(exclude_unset=True).items():
                if field != 'id':  # Don't update ID
                    setattr(db_product, field, value)
            
            db.commit()
            db.refresh(db_product)
            
            return self._product_to_item(db_product)
            
        finally:
            db.close()
    
    async def delete_product(self, product_id: str, business_type: BusinessType) -> bool:
        """Delete a product"""
        db = self.get_db()
        try:
            db_product = db.query(Product).filter(
                and_(
                    Product.id == product_id,
                    Product.business_type == business_type.value
                )
            ).first()
            
            if not db_product:
                return False
            
            db.delete(db_product)
            db.commit()
            return True
            
        finally:
            db.close()
    
    def _apply_filters(self, query, filters: Dict[str, Any]):
        """Apply filters to query"""
        for key, value in filters.items():
            if key == "category" and value:
                query = query.filter(Product.category == value)
            elif key == "price_range" and value:
                if isinstance(value, dict):
                    min_price = value.get("min")
                    max_price = value.get("max")
                    if min_price is not None:
                        query = query.filter(Product.price >= min_price)
                    if max_price is not None:
                        query = query.filter(Product.price <= max_price)
                elif isinstance(value, list) and len(value) == 2:
                    query = query.filter(Product.price.between(value[0], value[1]))
            elif key == "availability" and value is not None:
                query = query.filter(Product.availability == value)
            elif key == "color" and value:
                # Handle color filter specifically
                query = query.filter(
                    func.json_extract(Product.product_metadata, '$.color') == value
                )
            elif key == "brand" and value:
                # Handle brand filter
                query = query.filter(
                    func.json_extract(Product.product_metadata, '$.brand') == value
                )
            else:
                # Handle other metadata filters (custom attributes)
                if value:
                    query = query.filter(
                        func.json_extract(Product.product_metadata, f'$.{key}') == value
                    )
        
        return query
    
    async def _get_facets_for_results(self, db: Session, business_type: BusinessType, current_filters: Dict[str, Any]) -> Dict[str, List[str]]:
        """Get facets based on current search results"""
        facets = {}
        
        # Get base query
        base_query = db.query(Product).filter(Product.business_type == business_type.value)
        
        # Categories
        if "category" not in current_filters:
            categories = base_query.with_entities(Product.category).distinct().all()
            facets["category"] = [cat[0] for cat in categories if cat[0]]
        
        # Price ranges
        min_price, max_price = await self.get_price_range(business_type)
        if min_price < max_price:
            facets["price_range"] = [
                f"${int(min_price)}-${int(min_price + (max_price - min_price) * 0.33)}",
                f"${int(min_price + (max_price - min_price) * 0.33)}-${int(min_price + (max_price - min_price) * 0.67)}",
                f"${int(min_price + (max_price - min_price) * 0.67)}-${int(max_price)}"
            ]
        
        # Metadata facets (custom attributes)
        products = base_query.all()
        metadata_facets = {}
        
        for product in products:
            if product.product_metadata:
                for key, value in product.product_metadata.items():
                    if key not in metadata_facets:
                        metadata_facets[key] = set()
                    if value:
                        metadata_facets[key].add(str(value))
        
        # Convert sets to sorted lists
        for key, values in metadata_facets.items():
            facets[key] = sorted(list(values))
        
        return facets
    
    def _product_to_item(self, product: Product) -> ProductItem:
        """Convert Product model to ProductItem schema"""
        return ProductItem(
            id=product.id,
            name=product.name,
            description=product.description or "",
            price=product.price,
            category=product.category,
            metadata=product.product_metadata or {},
            availability=product.availability,
            image_url=product.image_url
        )
    
    def _get_suggestions(self, query: str, items: List[ProductItem]) -> List[str]:
        """Generate search suggestions based on results"""
        if not items:
            return ["Browse all products", "Check categories", "Adjust filters"]
        
        suggestions = []
        categories = list(set(item.category for item in items if item.category))
        
        if categories:
            suggestions.extend([f"More {cat}" for cat in categories[:3]])
        
        if len(items) > 5:
            suggestions.append("Narrow search")
        else:
            suggestions.append("Broaden search")
        
        return suggestions[:4] 