from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from app.models.schemas import ProductItem, SearchRequest, SearchResponse
from app.core.config import BusinessType


class BaseProductRepository(ABC):
    """Abstract base class for product repositories"""
    
    @abstractmethod
    async def search_products(self, search_request: SearchRequest) -> SearchResponse:
        """Search for products based on criteria"""
        pass
    
    @abstractmethod
    async def get_product_by_id(self, product_id: str, business_type: BusinessType) -> Optional[ProductItem]:
        """Get a specific product by ID"""
        pass
    
    @abstractmethod
    async def get_products_by_ids(self, product_ids: List[str], business_type: BusinessType) -> List[ProductItem]:
        """Get multiple products by IDs"""
        pass
    
    @abstractmethod
    async def get_facets(self, business_type: BusinessType, category: str = None) -> Dict[str, List[str]]:
        """Get available facets for filtering"""
        pass
    
    @abstractmethod
    async def get_categories(self, business_type: BusinessType) -> List[str]:
        """Get available categories"""
        pass
    
    @abstractmethod
    async def get_price_range(self, business_type: BusinessType, category: str = None) -> Tuple[float, float]:
        """Get min and max prices"""
        pass
    
    @abstractmethod
    async def create_product(self, product: ProductItem, business_type: BusinessType) -> ProductItem:
        """Create a new product"""
        pass
    
    @abstractmethod
    async def update_product(self, product_id: str, product: ProductItem, business_type: BusinessType) -> Optional[ProductItem]:
        """Update an existing product"""
        pass
    
    @abstractmethod
    async def delete_product(self, product_id: str, business_type: BusinessType) -> bool:
        """Delete a product"""
        pass 