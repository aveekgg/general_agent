from typing import Dict, List, Optional, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import json
import asyncio

from app.core.config import BusinessConfig, BusinessType, settings
from app.models.schemas import (
    AgentAction, AgentResponse, ConversationState, ActionType, ResponseFormat,
    ProductDetail, ProductComparison, ProductDetailResponse, ProductComparisonResponse,
    ProductItem
)
from app.repositories.factory import get_product_repository


class ProductDetailAgent:
    """
    Specialized agent for handling product-specific inquiries.
    Provides detailed product information, specifications, and comparisons.
    """
    
    def __init__(self, business_type: BusinessType):
        self.business_type = business_type
        self.business_config = BusinessConfig(business_type)
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.1,
            api_key=settings.openai_api_key
        )
        
        # Initialize repository for real product data
        self.repository = get_product_repository(business_type)
        
        # Initialize product knowledge base and tools
        self.product_tools = {}
        
    async def execute_action(
        self, 
        action: AgentAction, 
        conversation_state: ConversationState
    ) -> AgentResponse:
        """Execute the assigned action and return detailed response"""
        
        if action.action_type == ActionType.GET_PRODUCT_DETAILS:
            return await self._get_product_details(action, conversation_state)
        elif action.action_type == ActionType.COMPARE_PRODUCTS:
            return await self._compare_products(action, conversation_state)
        else:
            return self._fallback_response(action)
    
    async def _get_product_details(
        self, 
        action: AgentAction, 
        state: ConversationState
    ) -> AgentResponse:
        """Get detailed information about a specific product"""
        
        # Extract product information from action parameters
        product_info = action.parameters.get("product_info", {})
        product_name = product_info.get("name") or action.parameters.get("product_name")
        product_id = product_info.get("id") or action.parameters.get("product_id")
        
        # If no direct product info, try to construct from entities
        if not product_name and not product_id and state.current_intent:
            entities = state.current_intent.entities
            if entities.get("brand") and entities.get("model"):
                product_name = f"{entities.get('brand')} {entities.get('model')}"
                if entities.get("color"):
                    product_name += f" {entities.get('color')}"
        
        # If still no product name, extract from conversation context
        if not product_name and not product_id:
            product_entities = self._extract_product_entities(state)
            if not product_entities:
                return self._request_product_clarification()
            product_name = product_entities[0]
        
        # Get product details from knowledge base/external APIs
        product_details = await self._fetch_product_details(product_name, product_id, state)
        
        if not product_details:
            return self._product_not_found_response(product_name or product_id)
        
        # Generate comprehensive product detail response
        response_content = await self._generate_product_detail_content(product_details, state)
        
        # Create structured response
        return AgentResponse(
            agent_name="product_detail_agent",
            content=response_content["message"],
            response_format=ResponseFormat.PRODUCT_DETAIL,
            metadata={
                "product_detail": product_details.dict(),
                "business_type": self.business_type.value
            },
            quick_replies=response_content.get("quick_replies", []),
            requires_clarification=False
        )
    
    async def _compare_products(
        self, 
        action: AgentAction, 
        state: ConversationState
    ) -> AgentResponse:
        """Compare multiple products side-by-side"""
        
        # Extract products to compare
        products_to_compare = action.parameters.get("products", [])
        
        if len(products_to_compare) < 2:
            # Extract from conversation context or ask for clarification
            extracted_products = self._extract_comparison_products(state)
            if len(extracted_products) < 2:
                return self._request_comparison_clarification()
            products_to_compare = extracted_products
        
        # Fetch details for all products
        product_details_list = []
        for product in products_to_compare:
            details = await self._fetch_product_details(
                product.get("name"), 
                product.get("id"), 
                state
            )
            if details:
                product_details_list.append(details)
        
        if len(product_details_list) < 2:
            return self._insufficient_products_for_comparison()
        
        # Generate comparison analysis
        comparison_data = await self._generate_product_comparison(product_details_list, state)
        
        # Create structured comparison response
        return AgentResponse(
            agent_name="product_detail_agent",
            content=comparison_data["message"],
            response_format=ResponseFormat.PRODUCT_COMPARISON,
            metadata={
                "comparison": comparison_data["comparison"].dict(),
                "business_type": self.business_type.value
            },
            quick_replies=comparison_data.get("quick_replies", []),
            requires_clarification=False
        )
    
    async def _fetch_product_details(
        self, 
        product_name: Optional[str], 
        product_id: Optional[str], 
        state: ConversationState
    ) -> Optional[ProductDetail]:
        """Fetch comprehensive product details from database"""
        
        try:
            product_item = None
            
            # Try to get by ID first
            if product_id:
                product_item = await self.repository.get_product_by_id(product_id, self.business_type)
            
            # If not found by ID, try to search by name
            if not product_item and product_name:
                from app.models.schemas import SearchRequest
                search_request = SearchRequest(
                    query=product_name,
                    filters={},
                    limit=1,
                    business_type=self.business_type
                )
                search_response = await self.repository.search_products(search_request)
                if search_response.items:
                    product_item = search_response.items[0]
            
            if not product_item:
                return None
            
            # Convert ProductItem to ProductDetail
            return self._convert_item_to_detail(product_item)
            
        except Exception as e:
            print(f"Error fetching product details: {str(e)}")
            # Fallback to basic product details
            return self._create_fallback_product_details(product_name, product_id)
    
    def _convert_item_to_detail(self, product_item: ProductItem) -> ProductDetail:
        """Convert ProductItem to ProductDetail with enhanced information"""
        metadata = product_item.metadata or {}
        
        # Extract specifications from metadata
        specifications = {}
        features = []
        
        # Common specifications
        spec_fields = ["processor", "ram", "storage", "screen_size", "weight", "os", "graphics"]
        for field in spec_fields:
            if field in metadata:
                specifications[field.replace("_", " ").title()] = metadata[field]
        
        # Extract features
        if "touchscreen" in metadata and metadata["touchscreen"]:
            features.append("Touchscreen Display")
        if "convertible" in metadata and metadata["convertible"]:
            features.append("2-in-1 Convertible Design")
        if "graphics" in metadata:
            features.append(f"Dedicated Graphics: {metadata['graphics']}")
        
        # Generate actions based on business type
        actions = [
            {"title": "Add to Cart", "action": "add_to_cart"},
            {"title": "Compare", "action": "compare_product"},
            {"title": "View Reviews", "action": "view_reviews"}
        ]
        
        return ProductDetail(
            id=product_item.id,
            name=product_item.name,
            price=f"${product_item.price:.2f}" if product_item.price else None,
            images=[product_item.image_url] if product_item.image_url else [],
            specifications=specifications,
            features=features,
            description=product_item.description,
            availability="In Stock" if product_item.availability else "Out of Stock",
            rating=metadata.get("rating"),
            reviews_count=metadata.get("reviews_count", 0),
            actions=actions,
            metadata=metadata
        )
    
    async def _generate_product_detail_content(
        self, 
        product_details: ProductDetail, 
        state: ConversationState
    ) -> Dict[str, Any]:
        """Generate comprehensive product detail content"""
        
        content_prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_content_generation_system_prompt()),
            ("human", self._get_content_generation_human_prompt())
        ])
        
        prompt_input = {
            "product_details": product_details.dict(),
            "business_type": self.business_type.value,
            "conversation_history": self._format_conversation_history(state.conversation_history[-3:])
        }
        
        try:
            response = await self.llm.ainvoke(content_prompt.format(**prompt_input))
            return json.loads(response.content)
        except (json.JSONDecodeError, KeyError):
            return {
                "message": f"Here are the detailed specifications for {product_details.name}:",
                "quick_replies": ["Compare with similar", "Check availability", "Add to cart"]
            }
    
    async def _generate_product_comparison(
        self, 
        products: List[ProductDetail], 
        state: ConversationState
    ) -> Dict[str, Any]:
        """Generate intelligent product comparison"""
        
        comparison_prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_comparison_system_prompt()),
            ("human", self._get_comparison_human_prompt())
        ])
        
        prompt_input = {
            "products": [p.dict() for p in products],
            "business_type": self.business_type.value,
            "product_fields": json.dumps(self.business_config.config.get("product_fields", [])),
            "conversation_context": json.dumps(state.context)
        }
        
        try:
            response = await self.llm.ainvoke(comparison_prompt.format(**prompt_input))
            comparison_data = json.loads(response.content)
            
            comparison = ProductComparison(
                products=comparison_data.get("products", []),
                summary=comparison_data.get("summary", ""),
                recommendation=comparison_data.get("recommendation", ""),
                comparison_matrix=comparison_data.get("comparison_matrix", {})
            )
            
            return {
                "message": comparison_data.get("message", "Here's a detailed comparison:"),
                "comparison": comparison,
                "quick_replies": comparison_data.get("quick_replies", [])
            }
            
        except (json.JSONDecodeError, KeyError):
            return self._create_fallback_comparison(products)
    
    def _extract_product_entities(self, state: ConversationState) -> List[str]:
        """Extract product names/entities from conversation context"""
        entities = []
        
        # Check current intent entities
        if state.current_intent and state.current_intent.entities:
            product_entities = state.current_intent.entities.get("products", [])
            if isinstance(product_entities, list):
                entities.extend(product_entities)
            elif isinstance(product_entities, str):
                entities.append(product_entities)
        
        # Check conversation context
        context_products = state.context.get("mentioned_products", [])
        entities.extend(context_products)
        
        return list(set(entities))  # Remove duplicates
    
    def _extract_comparison_products(self, state: ConversationState) -> List[Dict[str, str]]:
        """Extract products for comparison from conversation"""
        products = []
        
        # Extract from current intent
        if state.current_intent and state.current_intent.entities:
            comparison_products = state.current_intent.entities.get("comparison_products", [])
            for product in comparison_products:
                if isinstance(product, str):
                    products.append({"name": product})
                elif isinstance(product, dict):
                    products.append(product)
        
        return products
    
    def _create_fallback_product_details(
        self, 
        product_name: Optional[str], 
        product_id: Optional[str]
    ) -> ProductDetail:
        """Create basic product details when detailed fetch fails"""
        return ProductDetail(
            id=product_id or "unknown",
            name=product_name or "Product",
            description="Product information is currently being updated. Please contact us for the latest details.",
            availability="Please check with our team",
            actions=[
                {"title": "Contact Support", "action": "contact_support"},
                {"title": "Browse Similar", "action": "browse_similar"}
            ]
        )
    
    def _create_fallback_comparison(self, products: List[ProductDetail]) -> Dict[str, Any]:
        """Create basic comparison when detailed analysis fails"""
        return {
            "message": f"Here's a comparison between {' and '.join([p.name for p in products])}:",
            "comparison": ProductComparison(
                products=[p.dict() for p in products],
                summary="Both products have their unique advantages. Contact us for personalized recommendations.",
                recommendation="Consider your specific needs and budget when making a decision."
            ),
            "quick_replies": ["Get recommendation", "Contact expert", "Browse more options"]
        }
    
    def _request_product_clarification(self) -> AgentResponse:
        """Request clarification when product is not specified"""
        return AgentResponse(
            agent_name="product_detail_agent",
            content="I'd be happy to provide detailed product information! Which specific product would you like to know more about?",
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=["Browse products", "Popular items", "Contact support"],
            requires_clarification=True
        )
    
    def _request_comparison_clarification(self) -> AgentResponse:
        """Request clarification for product comparison"""
        return AgentResponse(
            agent_name="product_detail_agent",
            content="I can help you compare products! Please tell me which products you'd like to compare, or I can suggest some popular comparisons.",
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=["Popular comparisons", "Browse categories", "Get recommendations"],
            requires_clarification=True
        )
    
    def _product_not_found_response(self, product_identifier: str) -> AgentResponse:
        """Response when product is not found"""
        return AgentResponse(
            agent_name="product_detail_agent",
            content=f"I couldn't find detailed information for '{product_identifier}'. Let me help you find what you're looking for!",
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=["Browse similar products", "Search again", "Contact support"],
            requires_clarification=False
        )
    
    def _insufficient_products_for_comparison(self) -> AgentResponse:
        """Response when not enough products for comparison"""
        return AgentResponse(
            agent_name="product_detail_agent",
            content="I need at least two products to create a meaningful comparison. Would you like me to suggest some popular product comparisons?",
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=["Popular comparisons", "Browse products", "Get recommendations"],
            requires_clarification=True
        )
    
    def _fallback_response(self, action: AgentAction) -> AgentResponse:
        """Fallback response for unhandled actions"""
        return AgentResponse(
            agent_name="product_detail_agent",
            content="I specialize in providing detailed product information and comparisons. How can I help you learn more about our products?",
            response_format=ResponseFormat.TEXT,
            quick_replies=["Product details", "Compare products", "Browse catalog"]
        )
    
    def _format_conversation_history(self, messages) -> str:
        """Format conversation history for prompts"""
        formatted = []
        for msg in messages:
            role = "User" if msg.message_type.value == "user" else "Assistant"
            formatted.append(f"{role}: {msg.content}")
        return "\n".join(formatted)
    
    def _get_product_detail_system_prompt(self) -> str:
        return """You are a product information specialist. Your job is to create comprehensive, accurate product details based on the given information and business context.

Generate detailed product information including:
- Complete specifications relevant to the business type
- Key features and benefits
- Pricing information (if available)
- Availability status
- Customer ratings and reviews (realistic estimates)
- Relevant product images/media
- Actionable next steps for customers

Adapt the level of detail and technical specifications to match the business type (e-commerce, hotel, real estate, etc.).

Return a JSON object with all product details."""
    
    def _get_product_detail_human_prompt(self) -> str:
        return """Product Name: {product_name}
Product ID: {product_id}
Business Type: {business_type}
Required Product Fields: {product_fields}
Business Context: {business_context}
Conversation Context: {conversation_context}

Generate comprehensive product details as a JSON object:"""
    
    def _get_content_generation_system_prompt(self) -> str:
        return """You are a customer service content generator. Create engaging, informative messages that present product details in a conversational and helpful manner.

Focus on:
- Clear, customer-friendly language
- Highlighting key benefits and features
- Addressing potential customer questions
- Providing helpful next steps
- Maintaining business tone and style

Return a JSON object with:
- message: the main response content
- quick_replies: relevant follow-up options"""
    
    def _get_content_generation_human_prompt(self) -> str:
        return """Product Details: {product_details}
Business Type: {business_type}
Recent Conversation: {conversation_history}

Generate customer-friendly product detail content as JSON:"""
    
    def _get_comparison_system_prompt(self) -> str:
        return """You are a product comparison specialist. Create comprehensive, unbiased product comparisons that help customers make informed decisions.

For each comparison:
- Analyze key specifications and features
- Identify pros and cons for each product
- Provide objective summary and recommendation
- Consider different customer needs and use cases
- Present information in a clear, structured format

Return a JSON object with detailed comparison data."""
    
    def _get_comparison_human_prompt(self) -> str:
        return """Products to Compare: {products}
Business Type: {business_type}
Product Fields: {product_fields}
Customer Context: {conversation_context}

Generate comprehensive product comparison as JSON:""" 