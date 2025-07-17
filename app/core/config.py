from typing import Dict, List, Optional, Any
from pydantic_settings import BaseSettings
from pydantic import Field
from enum import Enum


class BusinessType(str, Enum):
    ECOMMERCE = "ecommerce"
    HOTEL = "hotel"
    REAL_ESTATE = "real_estate"
    RENTAL = "rental"
    GENERIC = "generic"


class ConversationType(str, Enum):
    COMPANY_INFO = "company_info"
    PRODUCT_DISCOVERY = "product_discovery"
    PRODUCT_DETAIL = "product_detail"
    PROCESS_QUESTIONS = "process_questions"
    GENERAL_CONVERSATION = "general_conversation"


class Settings(BaseSettings):
    # API Configuration
    openai_api_key: str
    openai_model: str = "gpt-4-turbo-preview"
    
    # Database
    database_url: str = "sqlite:///./customer_service.db"
    redis_url: str = "redis://localhost:6379"
    
    # Vector Store
    chroma_persist_directory: str = "./data/chroma"
    
    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True
    
    # Business Configuration
    business_type: BusinessType = BusinessType.GENERIC
    business_name: str = "Generic Business"
    business_domain: str = "example.com"
    
    class Config:
        env_file = ".env"


class BusinessConfig:
    """Generic business configuration that adapts to different domains"""
    
    def __init__(self, business_type: BusinessType):
        self.business_type = business_type
        self.config = self._get_business_config()
    
    def _get_business_config(self) -> Dict[str, Any]:
        """Get business-specific configuration"""
        
        base_config = {
            "conversation_types": [
                ConversationType.COMPANY_INFO,
                ConversationType.PRODUCT_DISCOVERY,
                ConversationType.PRODUCT_DETAIL,
                ConversationType.PROCESS_QUESTIONS,
                ConversationType.GENERAL_CONVERSATION
            ],
            "required_params": {
                ConversationType.PRODUCT_DISCOVERY: ["preferences", "budget_range"],
                ConversationType.PRODUCT_DETAIL: ["product_id", "product_name"],
                ConversationType.PROCESS_QUESTIONS: ["stage", "order_id"]
            },
            "quick_replies": {
                ConversationType.COMPANY_INFO: [
                    "Tell me about your company",
                    "What services do you offer?",
                    "Where are you located?"
                ],
                ConversationType.PRODUCT_DISCOVERY: [
                    "Show me recommendations",
                    "What's popular?",
                    "Filter by price"
                ],
                ConversationType.PRODUCT_DETAIL: [
                    "Show me specifications",
                    "Compare with similar products",
                    "Check availability",
                    "Read reviews"
                ]
            }
        }
        
        # Business-specific configurations
        business_configs = {
            BusinessType.ECOMMERCE: {
                **base_config,
                "product_fields": ["name", "price", "description", "category", "in_stock"],
                "search_fields": ["category", "brand", "price_range", "rating"],
                "process_stages": ["cart", "checkout", "payment", "shipping", "delivery"],
                "external_apis": ["shopify", "stripe", "shipstation"]
            },
            
            BusinessType.HOTEL: {
                **base_config,
                "product_fields": ["room_type", "price_per_night", "amenities", "availability"],
                "search_fields": ["check_in", "check_out", "guests", "location", "amenities"],
                "process_stages": ["search", "booking", "payment", "confirmation", "check_in"],
                "external_apis": ["booking_engine", "pms", "payment_gateway"]
            },
            
            BusinessType.REAL_ESTATE: {
                **base_config,
                "product_fields": ["property_type", "price", "bedrooms", "location", "features"],
                "search_fields": ["location", "price_range", "property_type", "bedrooms"],
                "process_stages": ["inquiry", "viewing", "application", "approval", "signing"],
                "external_apis": ["mls", "crm", "document_signing"]
            },
            
            BusinessType.RENTAL: {
                **base_config,
                "product_fields": ["item_name", "daily_rate", "availability", "condition"],
                "search_fields": ["category", "date_range", "location", "price_range"],
                "process_stages": ["reservation", "pickup", "usage", "return", "billing"],
                "external_apis": ["inventory_system", "payment_processor"]
            }
        }
        
        return business_configs.get(self.business_type, base_config)
    
    def get_conversation_flow(self, conversation_type: ConversationType) -> Dict[str, Any]:
        """Get conversation flow configuration for a specific type"""
        flows = {
            ConversationType.COMPANY_INFO: {
                "intent": "Provide information about the business",
                "actions": ["search_company_info", "get_business_details"],
                "response_format": "informational"
            },
            ConversationType.PRODUCT_DISCOVERY: {
                "intent": "Help user discover products/services",
                "actions": ["search_products", "filter_results", "recommend_items"],
                "response_format": "carousel_with_details"
            },
            ConversationType.PRODUCT_DETAIL: {
                "intent": "Provide detailed information about specific products",
                "actions": ["get_product_details", "compare_products", "get_reviews"],
                "response_format": "detailed_product_view"
            },
            ConversationType.PROCESS_QUESTIONS: {
                "intent": "Guide user through business processes",
                "actions": ["get_process_info", "track_status", "provide_next_steps"],
                "response_format": "step_by_step"
            },
            ConversationType.GENERAL_CONVERSATION: {
                "intent": "Engage in helpful conversation",
                "actions": ["general_response", "redirect_if_needed"],
                "response_format": "conversational"
            }
        }
        
        return flows.get(conversation_type, flows[ConversationType.GENERAL_CONVERSATION])


# Global settings instance
settings = Settings() 