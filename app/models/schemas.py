from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from app.core.config import ConversationType, BusinessType


class MessageType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ActionType(str, Enum):
    SEARCH_PRODUCTS = "search_products"
    GET_COMPANY_INFO = "get_company_info"
    GET_PRODUCT_DETAILS = "get_product_details"
    COMPARE_PRODUCTS = "compare_products"
    TRACK_ORDER = "track_order"
    CLARIFY_PARAMS = "clarify_params"
    RECOMMEND_ITEMS = "recommend_items"
    GENERAL_RESPONSE = "general_response"


class ResponseFormat(str, Enum):
    TEXT = "text"
    CAROUSEL = "carousel"
    QUICK_REPLIES = "quick_replies"
    FORM = "form"
    PRODUCT_DETAIL = "product_detail"
    PRODUCT_COMPARISON = "product_comparison"
    MIXED = "mixed"


class ConversationMessage(BaseModel):
    id: str
    session_id: str
    message_type: MessageType
    content: str
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class UserIntent(BaseModel):
    """Represents the user's intent classification"""
    conversation_type: ConversationType
    confidence: float = Field(ge=0.0, le=1.0)
    entities: Dict[str, Any] = Field(default_factory=dict)
    required_params: List[str] = Field(default_factory=list)
    missing_params: List[str] = Field(default_factory=list)


class AgentAction(BaseModel):
    """Represents an action to be taken by an agent"""
    action_type: ActionType
    agent_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=1, ge=1, le=10)
    instructions: str = ""


class AgentResponse(BaseModel):
    """Response from an agent"""
    agent_name: str
    content: str
    response_format: ResponseFormat
    metadata: Optional[Dict[str, Any]] = None
    suggested_actions: List[AgentAction] = Field(default_factory=list)
    quick_replies: List[str] = Field(default_factory=list)
    requires_clarification: bool = False


class ConversationState(BaseModel):
    """Maintains the state of the conversation"""
    session_id: str
    user_id: Optional[str] = None
    business_type: BusinessType
    current_intent: Optional[UserIntent] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    conversation_history: List[ConversationMessage] = Field(default_factory=list)
    active_actions: List[AgentAction] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.now)


class ProductItem(BaseModel):
    """Generic product/service item"""
    id: str
    name: str
    description: str
    price: Optional[float] = None
    category: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    availability: bool = True
    image_url: Optional[str] = None


class SearchRequest(BaseModel):
    """Search request parameters"""
    query: str
    filters: Dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=10, ge=1, le=50)
    business_type: BusinessType


class SearchResponse(BaseModel):
    """Search results"""
    items: List[ProductItem]
    total_count: int
    facets: Dict[str, List[str]] = Field(default_factory=dict)
    suggestions: List[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    """Incoming chat request"""
    message: str
    session_id: str
    user_id: Optional[str] = None
    business_type: BusinessType = BusinessType.GENERIC
    context: Dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """Chat response to frontend"""
    message: str
    response_format: ResponseFormat
    quick_replies: List[str] = Field(default_factory=list)
    carousel_items: List[ProductItem] = Field(default_factory=list)
    form_fields: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    session_id: str


class CarouselItem(BaseModel):
    """Item in a carousel response"""
    title: str
    subtitle: str
    image_url: Optional[str] = None
    price: Optional[str] = None
    buttons: List[Dict[str, str]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QuickReply(BaseModel):
    """Quick reply button"""
    title: str
    payload: str
    metadata: Optional[Dict[str, Any]] = None


class FormField(BaseModel):
    """Dynamic form field"""
    name: str
    label: str
    field_type: str  # text, number, select, date, etc.
    required: bool = False
    options: List[str] = Field(default_factory=list)
    placeholder: Optional[str] = None
    validation: Optional[Dict[str, Any]] = None


class ProductDetail(BaseModel):
    """Detailed product information"""
    id: str
    name: str
    price: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    specifications: Dict[str, Any] = Field(default_factory=dict)
    features: List[str] = Field(default_factory=list)
    description: str = ""
    availability: str = "Unknown"
    rating: Optional[float] = None
    reviews_count: int = 0
    actions: List[Dict[str, str]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProductComparison(BaseModel):
    """Product comparison data"""
    products: List[Dict[str, Any]]
    summary: str = ""
    recommendation: str = ""
    comparison_matrix: Dict[str, List[str]] = Field(default_factory=dict)


class ProductDetailResponse(BaseModel):
    """Response containing product details"""
    message: str
    response_format: ResponseFormat = ResponseFormat.PRODUCT_DETAIL
    product_detail: ProductDetail
    quick_replies: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProductComparisonResponse(BaseModel):
    """Response containing product comparison"""
    message: str
    response_format: ResponseFormat = ResponseFormat.PRODUCT_COMPARISON
    comparison: ProductComparison
    quick_replies: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict) 