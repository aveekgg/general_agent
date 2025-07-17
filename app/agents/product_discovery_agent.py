from typing import Dict, List, Optional, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import json
import asyncio

from app.core.config import BusinessConfig, BusinessType, settings
from app.models.schemas import (
    AgentAction, AgentResponse, ConversationState, ActionType, ResponseFormat,
    ProductItem, SearchRequest, SearchResponse
)
from app.repositories.factory import get_product_repository


class ProductDiscoveryAgent:
    """
    Specialized agent for handling product discovery and search.
    Provides product search, recommendations, and browsing capabilities.
    """
    
    def __init__(self, business_type: BusinessType):
        self.business_type = business_type
        self.business_config = BusinessConfig(business_type)
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.3,  # Slightly higher for creative recommendations
            api_key=settings.openai_api_key
        )
        
        # Initialize repository for real product data
        self.repository = get_product_repository(business_type)
        
        # Initialize product search tools
        self.search_tools = {}
        
    async def execute_action(
        self, 
        action: AgentAction, 
        conversation_state: ConversationState
    ) -> AgentResponse:
        """Execute the assigned action and return search results"""
        
        if action.action_type == ActionType.SEARCH_PRODUCTS:
            return await self._search_products(action, conversation_state)
        elif action.action_type == ActionType.RECOMMEND_ITEMS:
            return await self._recommend_items(action, conversation_state)
        elif action.action_type == ActionType.GENERAL_RESPONSE:
            return await self._general_response(action, conversation_state)
        elif action.action_type == ActionType.CLARIFY_PARAMS:
            return await self._clarify_params(action, conversation_state)
        else:
            return self._fallback_response(action)
    
    async def _search_products(
        self, 
        action: AgentAction, 
        state: ConversationState
    ) -> AgentResponse:
        """Search for products based on user criteria"""
        
        # Extract search parameters from action and conversation
        search_params = self._extract_search_parameters(action, state)
        
        # Only request clarification if we have no query AND no useful filters
        if not search_params.get("query") and not any(search_params.get(key) for key in ["category", "price_range", "budget", "brand"]):
            return self._request_search_clarification()
        
        # Perform product search (simulated with LLM for now)
        search_results = await self._perform_product_search(search_params, state)
        
        if not search_results:
            return self._no_results_response(search_params["query"])
        
        # Generate carousel response with products
        return self._create_carousel_response(search_results, search_params, state)
    
    async def _recommend_items(
        self, 
        action: AgentAction, 
        state: ConversationState
    ) -> AgentResponse:
        """Generate personalized product recommendations"""
        
        # Extract user preferences from conversation
        preferences = self._extract_user_preferences(action, state)
        
        # Generate recommendations
        recommendations = await self._generate_recommendations(preferences, state)
        
        if not recommendations:
            return self._generic_recommendations_response()
        
        return self._create_carousel_response(recommendations, preferences, state)
    
    async def _general_response(
        self, 
        action: AgentAction, 
        state: ConversationState
    ) -> AgentResponse:
        """Handle general conversation and provide helpful responses"""
        
        # Get the last user message for context
        last_message = ""
        if state.conversation_history:
            last_message = state.conversation_history[-1].content
        
        # Analyze the user's message and provide appropriate response
        if any(keyword in last_message.lower() for keyword in ["hello", "hi", "hey", "help"]):
            return self._greeting_response()
        elif any(keyword in last_message.lower() for keyword in ["thank", "thanks"]):
            return self._thanks_response()
        elif any(keyword in last_message.lower() for keyword in ["laptop", "computer", "phone", "electronics"]):
            return self._redirect_to_search_response(last_message)
        elif any(keyword in last_message.lower() for keyword in ["price", "cost", "budget", "under", "within"]):
            return self._redirect_to_search_response(last_message)
        else:
            return self._helpful_general_response()
    
    async def _clarify_params(
        self, 
        action: AgentAction, 
        state: ConversationState
    ) -> AgentResponse:
        """Handle parameter clarification requests"""
        
        missing_params = action.parameters.get("missing_params", [])
        
        # For simple searches, don't over-complicate with preferences
        if "preferences" in missing_params and state.current_intent:
            entities = state.current_intent.entities
            
            # If we have category and budget, that's enough for a good search
            if entities.get("category") and (entities.get("budget_range") or entities.get("price_range")):
                # Skip clarification and go straight to search
                return AgentResponse(
                    agent_name="product_discovery_agent",
                    content=f"Let me search for {entities.get('category')} within your budget range!",
                    response_format=ResponseFormat.QUICK_REPLIES,
                    quick_replies=["See results", "Filter more", "Browse categories", "Get recommendations"],
                    suggested_actions=[
                        AgentAction(
                            action_type=ActionType.SEARCH_PRODUCTS,
                            agent_name="product_discovery_agent",
                            parameters={
                                "query": state.conversation_history[-1].content if state.conversation_history else "",
                                "category": entities.get("category"),
                                "budget_range": entities.get("budget_range") or entities.get("price_range")
                            },
                            priority=1,
                            instructions="Search for products with available criteria"
                        )
                    ]
                )
        
        # Default clarification response
        message = "I'd like to help you find the perfect products! Could you tell me a bit more about what you're looking for?"
        quick_replies = ["Browse categories", "Popular items", "Get recommendations", "Help me search"]
        
        return AgentResponse(
            agent_name="product_discovery_agent",
            content=message,
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=quick_replies,
            requires_clarification=True
        )
    
    def _greeting_response(self) -> AgentResponse:
        """Friendly greeting response"""
        
        if self.business_type == BusinessType.ECOMMERCE:
            message = "Hello! I'm here to help you discover amazing products. What are you looking for today?"
            quick_replies = ["Browse electronics", "Show me deals", "Popular items", "Help me search"]
        elif self.business_type == BusinessType.HOTEL:
            message = "Welcome! I can help you find the perfect room for your stay. How can I assist you?"
            quick_replies = ["Check availability", "View rooms", "Special offers", "Hotel amenities"]
        elif self.business_type == BusinessType.REAL_ESTATE:
            message = "Hello! I'm here to help you find your dream property. What type of property are you interested in?"
            quick_replies = ["Houses for sale", "Apartments", "View listings", "Schedule viewing"]
        elif self.business_type == BusinessType.RENTAL:
            message = "Hi there! I can help you find rental items for your needs. What are you looking to rent?"
            quick_replies = ["Vehicles", "Tools & equipment", "Event items", "Browse categories"]
        else:
            message = "Hello! I'm here to help you find what you're looking for. How can I assist you today?"
            quick_replies = ["Browse products", "Search items", "Popular choices", "Get help"]
        
        return AgentResponse(
            agent_name="product_discovery_agent",
            content=message,
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=quick_replies,
            requires_clarification=False
        )
    
    def _thanks_response(self) -> AgentResponse:
        """Response to thank you messages"""
        
        message = "You're welcome! Is there anything else I can help you find today?"
        quick_replies = ["Browse more", "Search again", "Get recommendations", "Contact support"]
        
        return AgentResponse(
            agent_name="product_discovery_agent",
            content=message,
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=quick_replies,
            requires_clarification=False
        )
    
    def _redirect_to_search_response(self, user_message: str) -> AgentResponse:
        """Redirect shopping-related queries to search"""
        
        message = f"I'd love to help you find what you're looking for! Let me search for products based on your request."
        quick_replies = ["Search now", "Filter results", "Browse categories", "Get recommendations"]
        
        return AgentResponse(
            agent_name="product_discovery_agent",
            content=message,
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=quick_replies,
            requires_clarification=False,
            suggested_actions=[
                AgentAction(
                    action_type=ActionType.SEARCH_PRODUCTS,
                    agent_name="product_discovery_agent",
                    parameters={"query": user_message},
                    priority=1,
                    instructions="Search for products based on user query"
                )
            ]
        )
    
    def _helpful_general_response(self) -> AgentResponse:
        """General helpful response"""
        
        if self.business_type == BusinessType.ECOMMERCE:
            message = "I'm here to help you discover and find great products! You can search for specific items, browse categories, or get personalized recommendations."
            quick_replies = ["Search products", "Browse categories", "Popular items", "Get recommendations"]
        elif self.business_type == BusinessType.HOTEL:
            message = "I can help you find the perfect accommodation! You can check room availability, view amenities, or get recommendations based on your preferences."
            quick_replies = ["Check availability", "View rooms", "Hotel amenities", "Special offers"]
        elif self.business_type == BusinessType.REAL_ESTATE:
            message = "I'm here to help you find your ideal property! You can search listings, filter by preferences, or schedule viewings."
            quick_replies = ["Search properties", "Filter by price", "View listings", "Schedule viewing"]
        elif self.business_type == BusinessType.RENTAL:
            message = "I can help you find rental items for any need! Search by category, check availability, or browse our inventory."
            quick_replies = ["Browse categories", "Check availability", "Search items", "Popular rentals"]
        else:
            message = "I'm here to help you find exactly what you need! Feel free to search, browse, or ask for recommendations."
            quick_replies = ["Search", "Browse", "Recommendations", "Help"]
        
        return AgentResponse(
            agent_name="product_discovery_agent",
            content=message,
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=quick_replies,
            requires_clarification=False
        )
    
    def _extract_search_parameters(
        self, 
        action: AgentAction, 
        state: ConversationState
    ) -> Dict[str, Any]:
        """Extract search parameters from action and conversation context"""
        
        # Start with action parameters
        params = action.parameters.copy()
        
        # Extract from user intent entities
        if state.current_intent and state.current_intent.entities:
            entities = state.current_intent.entities
            
            # Extract product category
            if "category" in entities:
                params["category"] = entities["category"]
            
            # Extract price range
            if "price_range" in entities:
                params["price_range"] = entities["price_range"]
            elif "budget" in entities:
                params["price_range"] = entities["budget"]
            
            # Extract brand preferences
            if "brand" in entities:
                params["brand"] = entities["brand"]
            
            # Extract specifications
            if "specifications" in entities:
                params.update(entities["specifications"])
        
        # Extract query from the original user message
        if not params.get("query"):
            user_message = state.conversation_history[-1].content if state.conversation_history else ""
            # For category-based searches, use empty query to rely on filters
            if params.get("category") and any(keyword in user_message.lower() for keyword in ["show me", "find", "search", "under", "within", "budget"]):
                params["query"] = ""  # Let filters do the work
            else:
                params["query"] = user_message
        
        return params
    
    def _extract_user_preferences(
        self, 
        action: AgentAction, 
        state: ConversationState
    ) -> Dict[str, Any]:
        """Extract user preferences for recommendations"""
        
        preferences = action.parameters.copy()
        
        # Look at conversation history for preferences
        if state.context.get("user_preferences"):
            preferences.update(state.context["user_preferences"])
        
        # Default preferences based on business type
        if self.business_type == BusinessType.ECOMMERCE:
            preferences.setdefault("categories", ["electronics", "clothing", "home"])
        elif self.business_type == BusinessType.HOTEL:
            preferences.setdefault("room_types", ["standard", "deluxe", "suite"])
        elif self.business_type == BusinessType.REAL_ESTATE:
            preferences.setdefault("property_types", ["house", "apartment", "condo"])
        elif self.business_type == BusinessType.RENTAL:
            preferences.setdefault("item_types", ["vehicles", "equipment", "tools"])
        
        return preferences
    
    async def _perform_product_search(
        self, 
        search_params: Dict[str, Any], 
        state: ConversationState
    ) -> List[ProductItem]:
        """Perform product search using real database"""
        
        try:
            # Extract filters and show debug info
            filters = self._extract_filters_from_params(search_params)
            print(f"🔍 [DATABASE_SEARCH] Search params: {search_params}")
            print(f"🔍 [DATABASE_SEARCH] Extracted filters: {filters}")
            
            # Create SearchRequest from parameters
            search_request = SearchRequest(
                query=search_params.get("query", ""),
                filters=filters,
                limit=search_params.get("limit", 8),
                business_type=self.business_type
            )
            
            print(f"🔍 [DATABASE_SEARCH] SearchRequest: query='{search_request.query}', filters={search_request.filters}, business_type={search_request.business_type}")
            
            # Perform real database search
            search_response = await self.repository.search_products(search_request)
            
            print(f"🔍 [DATABASE_SEARCH] Found {len(search_response.items)} products")
            if search_response.items:
                print(f"🔍 [DATABASE_SEARCH] First product: {search_response.items[0].name} - ${search_response.items[0].price}")
            
            return search_response.items
            
        except Exception as e:
            print(f"❌ [DATABASE_SEARCH] Database search failed: {str(e)}")
            import traceback
            traceback.print_exc()
            # Fallback to sample products only if database fails
            return self._generate_sample_products(search_params)
    
    def _extract_filters_from_params(self, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract filters from search parameters"""
        filters = {}
        
        # Extract common filters
        if "category" in search_params:
            filters["category"] = search_params["category"]
        
        if "price_range" in search_params:
            price_range = search_params["price_range"]
            if isinstance(price_range, str):
                # Parse price range strings like "under $1000" or "$500-$1000"
                import re
                if "under" in price_range.lower():
                    max_price = float(re.findall(r'\d+', price_range)[0])
                    filters["price_range"] = {"min": 0, "max": max_price}
                elif "over" in price_range.lower() or "above" in price_range.lower():
                    min_price = float(re.findall(r'\d+', price_range)[0])
                    filters["price_range"] = {"min": min_price, "max": float('inf')}
                elif "-" in price_range:
                    prices = re.findall(r'\d+', price_range)
                    if len(prices) == 2:
                        filters["price_range"] = {"min": float(prices[0]), "max": float(prices[1])}
                else:
                    # Try to extract a single price as max
                    numbers = re.findall(r'\d+', price_range)
                    if numbers:
                        max_price = float(numbers[0])
                        filters["price_range"] = {"min": 0, "max": max_price}
            else:
                filters["price_range"] = price_range
        
        # Handle budget as price range
        if "budget" in search_params:
            budget = search_params["budget"]
            if isinstance(budget, (int, float)):
                filters["price_range"] = {"min": 0, "max": budget}
            elif isinstance(budget, str):
                # Parse budget strings like "under 1000" or "500-1000"
                import re
                if "under" in budget.lower():
                    max_price = float(re.findall(r'\d+', budget)[0])
                    filters["price_range"] = {"min": 0, "max": max_price}
                elif "-" in budget:
                    prices = re.findall(r'\d+', budget)
                    if len(prices) == 2:
                        filters["price_range"] = {"min": float(prices[0]), "max": float(prices[1])}
        
        # Extract custom attributes (color, brand, etc.)
        for key, value in search_params.items():
            if key in ["color", "brand", "processor", "ram", "storage", "os"]:
                filters[key] = value
        
        return filters
    
    async def _generate_recommendations(
        self, 
        preferences: Dict[str, Any], 
        state: ConversationState
    ) -> List[ProductItem]:
        """Generate personalized recommendations"""
        
        recommendation_prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_recommendation_system_prompt()),
            ("human", self._get_recommendation_human_prompt())
        ])
        
        prompt_input = {
            "user_preferences": json.dumps(preferences, indent=2),
            "business_type": self.business_type.value,
            "business_config": json.dumps(self.business_config.config, indent=2),
            "conversation_history": self._format_conversation_history(state.conversation_history[-3:])
        }
        
        try:
            response = await self.llm.ainvoke(recommendation_prompt.format(**prompt_input))
            rec_data = json.loads(response.content)
            
            products = []
            for item_data in rec_data.get("recommendations", []):
                product = ProductItem(
                    id=item_data.get("id", f"rec_{len(products)}"),
                    name=item_data.get("name", "Recommended Product"),
                    description=item_data.get("description", ""),
                    price=item_data.get("price"),
                    category=item_data.get("category"),
                    metadata=item_data.get("metadata", {}),
                    availability=item_data.get("availability", True),
                    image_url=item_data.get("image_url")
                )
                products.append(product)
            
            return products[:6]  # Limit to 6 recommendations
            
        except (json.JSONDecodeError, KeyError):
            return self._generate_sample_products(preferences)
    
    def _generate_sample_products(self, params: Dict[str, Any]) -> List[ProductItem]:
        """Generate sample products as fallback"""
        
        query = params.get("query", "").lower()
        sample_products = []
        
        if self.business_type == BusinessType.ECOMMERCE:
            if "laptop" in query:
                sample_products = [
                    ProductItem(id="lap1", name="Dell XPS 13", description="Ultrabook with Intel i7", price=899.99, category="laptops"),
                    ProductItem(id="lap2", name="MacBook Air M2", description="Apple's latest laptop", price=999.99, category="laptops"),
                    ProductItem(id="lap3", name="Lenovo ThinkPad X1", description="Business laptop", price=849.99, category="laptops"),
                    ProductItem(id="lap4", name="HP Pavilion 15", description="Budget-friendly laptop", price=649.99, category="laptops")
                ]
            else:
                sample_products = [
                    ProductItem(id="prod1", name="Popular Item 1", description="Highly rated product", price=199.99, category="electronics"),
                    ProductItem(id="prod2", name="Popular Item 2", description="Customer favorite", price=149.99, category="electronics"),
                    ProductItem(id="prod3", name="Popular Item 3", description="Best seller", price=299.99, category="electronics")
                ]
        elif self.business_type == BusinessType.HOTEL:
            sample_products = [
                ProductItem(id="room1", name="Standard Room", description="Comfortable accommodation", price=129.99, category="rooms"),
                ProductItem(id="room2", name="Deluxe Suite", description="Spacious with city view", price=249.99, category="rooms"),
                ProductItem(id="room3", name="Ocean View Room", description="Beautiful ocean views", price=199.99, category="rooms")
            ]
        elif self.business_type == BusinessType.REAL_ESTATE:
            sample_products = [
                ProductItem(id="prop1", name="3BR Modern House", description="Contemporary home with garden", price=450000, category="houses"),
                ProductItem(id="prop2", name="2BR Downtown Apartment", description="City center location", price=320000, category="apartments"),
                ProductItem(id="prop3", name="4BR Family Home", description="Perfect for growing families", price=580000, category="houses")
            ]
        elif self.business_type == BusinessType.RENTAL:
            sample_products = [
                ProductItem(id="rent1", name="Compact SUV", description="Perfect for city driving", price=45.99, category="vehicles"),
                ProductItem(id="rent2", name="Power Drill Set", description="Professional tools", price=25.99, category="tools"),
                ProductItem(id="rent3", name="Party Tent", description="Large outdoor tent", price=75.99, category="events")
            ]
        
        return sample_products
    
    def _create_carousel_response(
        self, 
        products: List[ProductItem], 
        search_params: Dict[str, Any], 
        state: ConversationState
    ) -> AgentResponse:
        """Create a carousel response with product results"""
        
        # Generate contextual message
        query = search_params.get("query", "your search")
        message = f"I found {len(products)} great options for {query}:"
        
        # Create quick replies
        quick_replies = ["See more details", "Compare products", "Refine search", "Contact support"]
        
        # Add business-specific quick replies
        if self.business_type == BusinessType.ECOMMERCE:
            quick_replies = ["Add to cart", "Compare", "See reviews", "Filter results"]
        elif self.business_type == BusinessType.HOTEL:
            quick_replies = ["Book now", "Check availability", "View amenities", "Compare rooms"]
        elif self.business_type == BusinessType.REAL_ESTATE:
            quick_replies = ["Schedule viewing", "Get more info", "Check mortgage", "Contact agent"]
        elif self.business_type == BusinessType.RENTAL:
            quick_replies = ["Reserve now", "Check availability", "View terms", "Get quote"]
        
        return AgentResponse(
            agent_name="product_discovery_agent",
            content=message,
            response_format=ResponseFormat.CAROUSEL,
            metadata={
                "carousel_items": [product.dict() for product in products],
                "search_params": search_params,
                "business_type": self.business_type.value
            },
            quick_replies=quick_replies,
            requires_clarification=False
        )
    
    def _request_search_clarification(self) -> AgentResponse:
        """Request clarification when search parameters are unclear"""
        
        if self.business_type == BusinessType.ECOMMERCE:
            message = "I'd love to help you find products! What are you looking for?"
            quick_replies = ["Electronics", "Clothing", "Home & Garden", "Sports"]
        elif self.business_type == BusinessType.HOTEL:
            message = "I can help you find the perfect room! What are your preferences?"
            quick_replies = ["Standard rooms", "Suites", "Ocean view", "Business center"]
        elif self.business_type == BusinessType.REAL_ESTATE:
            message = "Let me help you find properties! What type are you interested in?"
            quick_replies = ["Houses", "Apartments", "Condos", "Commercial"]
        elif self.business_type == BusinessType.RENTAL:
            message = "I can help you find rental items! What do you need?"
            quick_replies = ["Vehicles", "Tools", "Equipment", "Event items"]
        else:
            message = "What can I help you find today?"
            quick_replies = ["Browse categories", "Popular items", "New arrivals", "Deals"]
        
        return AgentResponse(
            agent_name="product_discovery_agent",
            content=message,
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=quick_replies,
            requires_clarification=True
        )
    
    def _no_results_response(self, query: str) -> AgentResponse:
        """Response when no products are found"""
        
        return AgentResponse(
            agent_name="product_discovery_agent",
            content=f"I couldn't find any results for '{query}'. Let me help you search differently or suggest alternatives.",
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=["Browse categories", "Popular items", "Search tips", "Contact support"],
            requires_clarification=False
        )
    
    def _generic_recommendations_response(self) -> AgentResponse:
        """Fallback recommendations response"""
        
        return AgentResponse(
            agent_name="product_discovery_agent",
            content="Here are some popular items you might be interested in:",
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=["See all products", "Browse categories", "Get personalized", "Contact support"],
            requires_clarification=False
        )
    
    def _fallback_response(self, action: AgentAction) -> AgentResponse:
        """Fallback response for unhandled actions"""
        
        # Check if this is a product-related query that should be redirected to search
        action_params = action.parameters
        if action_params and ("query" in action_params or "product" in str(action_params).lower()):
            return AgentResponse(
                agent_name="product_discovery_agent",
                content="I'd be happy to help you find products! Let me search for what you're looking for.",
                response_format=ResponseFormat.QUICK_REPLIES,
                quick_replies=["Search products", "Browse categories", "Get recommendations", "Popular items"],
                requires_clarification=False,
                suggested_actions=[
                    AgentAction(
                        action_type=ActionType.SEARCH_PRODUCTS,
                        agent_name="product_discovery_agent",
                        parameters=action_params,
                        priority=1,
                        instructions="Search for products based on user query"
                    )
                ]
            )
        
        return AgentResponse(
            agent_name="product_discovery_agent",
            content="I specialize in helping you discover and search for products. How can I help you find what you're looking for?",
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=["Search products", "Browse categories", "Get recommendations", "Popular items"],
            requires_clarification=False
        )
    
    def _format_conversation_history(self, messages) -> str:
        """Format conversation history for prompts"""
        formatted = []
        for msg in messages:
            role = "User" if msg.message_type.value == "user" else "Assistant"
            formatted.append(f"{role}: {msg.content}")
        return "\n".join(formatted)
    
    def _get_product_search_system_prompt(self) -> str:
        return """You are a product search specialist. Your job is to generate realistic, relevant product search results based on user queries and search parameters.

Create diverse, attractive product listings that match the search criteria. Include:
- Relevant product names and descriptions
- Realistic pricing for the business type
- Appropriate categories and specifications
- High-quality, varied selection
- Mix of popular and niche options

Adapt results to the business type:
- E-commerce: Electronics, clothing, home goods, etc.
- Hotel: Room types, amenities, rates
- Real Estate: Properties with locations, features, prices
- Rental: Equipment, vehicles, tools with daily/hourly rates

Return a JSON object with a "products" array containing detailed product information."""

    def _get_product_search_human_prompt(self) -> str:
        return """Search Query: "{search_query}"
Search Parameters: {search_params}
Business Type: {business_type}
Business Config: {business_config}
Conversation Context: {conversation_context}

Generate relevant product search results as JSON:"""

    def _get_recommendation_system_prompt(self) -> str:
        return """You are a personalized recommendation engine. Generate intelligent product recommendations based on user preferences, conversation history, and business context.

Create recommendations that are:
- Personalized to user interests and needs
- Diverse in price range and features
- High-quality and well-reviewed
- Aligned with current trends
- Appropriate for the business type

Consider user's budget, preferences, and previous interactions when making recommendations.

Return a JSON object with a "recommendations" array of suggested products."""

    def _get_recommendation_human_prompt(self) -> str:
        return """User Preferences: {user_preferences}
Business Type: {business_type}
Business Config: {business_config}
Recent Conversation: {conversation_history}

Generate personalized recommendations as JSON:""" 