from typing import Dict, List, Optional, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import json
import asyncio

from app.core.config import BusinessConfig, BusinessType, settings, ConversationType
from app.models.schemas import (
    AgentAction, AgentResponse, ConversationState, ActionType, ResponseFormat,
    FormField, UserIntent
)


class ClarificationAgent:
    """
    Specialized agent for handling parameter clarification and missing information gathering.
    Generates contextual questions and forms to collect missing parameters.
    """
    
    def __init__(self, business_type: BusinessType):
        self.business_type = business_type
        self.business_config = BusinessConfig(business_type)
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.1,
            api_key=settings.openai_api_key
        )
        
        # Parameter clarification mappings for different conversation types
        self.clarification_mappings = {
            ConversationType.PRODUCT_DISCOVERY: {
                "category": "What type of product are you looking for?",
                "budget": "What's your budget range?",
                "preferences": "Any specific features or preferences?",
                "use_case": "What will you be using this for?"
            },
            ConversationType.PRODUCT_DETAIL: {
                "product_id": "Which specific product would you like to know about?",
                "product_name": "What's the exact product name?",
                "model": "Which model or variant?",
                "specifications": "What specific details do you need?"
            },
            ConversationType.PROCESS_QUESTIONS: {
                "order_id": "What's your order number?",
                "email": "What's your email address?",
                "phone": "What's your phone number?",
                "status": "What process are you asking about?"
            },
            ConversationType.COMPANY_INFO: {
                "location": "Which location are you asking about?",
                "service": "Which service do you need info about?",
                "department": "Which department can help you?"
            }
        }
        
    async def execute_action(
        self, 
        action: AgentAction, 
        conversation_state: ConversationState
    ) -> AgentResponse:
        """Execute the assigned action and return clarification response"""
        
        if action.action_type == ActionType.CLARIFY_PARAMS:
            return await self._clarify_params(action, conversation_state)
        else:
            return self._fallback_response(action)
    
    async def _clarify_params(
        self, 
        action: AgentAction, 
        state: ConversationState
    ) -> AgentResponse:
        """Generate contextual clarification questions for missing parameters"""
        
        missing_params = action.parameters.get("missing_params", [])
        conversation_type = state.current_intent.conversation_type if state.current_intent else ConversationType.GENERAL_CONVERSATION
        
        # Get context from conversation history
        context = self._extract_context_from_conversation(state)
        
        # For product queries, try to be smart about what we really need
        if conversation_type == ConversationType.PRODUCT_DETAIL:
            return await self._handle_product_detail_clarification(action, state, missing_params, context)
        elif conversation_type == ConversationType.PRODUCT_DISCOVERY:
            return await self._handle_product_discovery_clarification(action, state, missing_params, context)
        else:
            return await self._handle_general_clarification(action, state, missing_params, context)
    
    async def _handle_product_detail_clarification(
        self, 
        action: AgentAction, 
        state: ConversationState, 
        missing_params: List[str],
        context: Dict[str, Any]
    ) -> AgentResponse:
        """Handle clarification for product detail queries"""
        
        # If we have brand/model info but missing product_id, try to help with search
        if "product_id" in missing_params and state.current_intent:
            entities = state.current_intent.entities
            
            # We have enough info to search - suggest searching instead of requiring ID
            if entities.get("brand") and entities.get("model"):
                brand = entities.get("brand")
                model = entities.get("model")
                color = entities.get("color", "")
                
                search_query = f"{brand} {model} {color}".strip()
                
                return AgentResponse(
                    agent_name="clarification_agent",
                    content=f"I found you're looking for the {search_query}. Let me search for that product and show you the details!",
                    response_format=ResponseFormat.QUICK_REPLIES,
                    quick_replies=[
                        "Show me the details",
                        "Compare with similar products", 
                        "Check availability",
                        "See specifications"
                    ],
                    requires_clarification=False,
                    suggested_actions=[
                        AgentAction(
                            action_type=ActionType.GET_PRODUCT_DETAILS,
                            agent_name="product_detail_agent",
                            parameters={
                                "product_name": search_query,
                                "search_mode": True
                            },
                            priority=10,
                            instructions="Search for product by name and return details"
                        )
                    ]
                )
            
            # Fallback to asking for clarification
            return AgentResponse(
                agent_name="clarification_agent",
                content="I'd be happy to help you learn more about a specific product! Could you tell me the product name or provide more details about what you're looking for?",
                response_format=ResponseFormat.QUICK_REPLIES,
                quick_replies=[
                    "Browse product categories",
                    "Search by product name",
                    "Get recommendations",
                    "Popular products"
                ],
                requires_clarification=True
            )
        
        # Handle other missing parameters
        return await self._generate_clarification_response(missing_params, state.current_intent.conversation_type, context)
    
    async def _handle_product_discovery_clarification(
        self, 
        action: AgentAction, 
        state: ConversationState, 
        missing_params: List[str],
        context: Dict[str, Any]
    ) -> AgentResponse:
        """Handle clarification for product discovery queries"""
        
        # For product discovery, we're more lenient about missing preferences
        if "preferences" in missing_params and context.get("category"):
            # We have a category, that's usually enough to start
            return AgentResponse(
                agent_name="clarification_agent",
                content=f"Great! I can help you find {context.get('category')}. Let me show you some options!",
                response_format=ResponseFormat.QUICK_REPLIES,
                quick_replies=[
                    "See all options",
                    "Filter by price",
                    "Popular choices",
                    "Best rated"
                ],
                requires_clarification=False,
                suggested_actions=[
                    AgentAction(
                        action_type=ActionType.SEARCH_PRODUCTS,
                        agent_name="product_discovery_agent",
                        parameters={
                            "category": context.get("category"),
                            "query": context.get("original_query", "")
                        },
                        priority=10,
                        instructions="Search for products in the specified category"
                    )
                ]
            )
        
        return await self._generate_clarification_response(missing_params, ConversationType.PRODUCT_DISCOVERY, context)
    
    async def _handle_general_clarification(
        self, 
        action: AgentAction, 
        state: ConversationState, 
        missing_params: List[str],
        context: Dict[str, Any]
    ) -> AgentResponse:
        """Handle general clarification requests"""
        
        conversation_type = state.current_intent.conversation_type if state.current_intent else ConversationType.GENERAL_CONVERSATION
        return await self._generate_clarification_response(missing_params, conversation_type, context)
    
    async def _generate_clarification_response(
        self, 
        missing_params: List[str], 
        conversation_type: ConversationType,
        context: Dict[str, Any]
    ) -> AgentResponse:
        """Generate intelligent clarification response using LLM"""
        
        # Get clarification mappings for this conversation type
        param_questions = self.clarification_mappings.get(conversation_type, {})
        
        # Create clarification prompt
        clarification_prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_clarification_system_prompt()),
            ("human", self._get_clarification_human_prompt())
        ])
        
        prompt_input = {
            "missing_params": missing_params,
            "conversation_type": conversation_type.value,
            "context": json.dumps(context, indent=2),
            "business_type": self.business_type.value,
            "param_questions": json.dumps(param_questions, indent=2)
        }
        
        response = await self.llm.ainvoke(clarification_prompt.format(**prompt_input))
        
        try:
            # Parse the structured response
            content = response.content.strip()
            if content.startswith('```json'):
                content = content[7:]
            if content.startswith('```'):
                content = content[3:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            clarification_data = json.loads(content)
            
            # Create form fields if needed
            form_fields = []
            if clarification_data.get("use_form", False):
                for param in missing_params:
                    field_info = clarification_data.get("form_fields", {}).get(param, {})
                    form_fields.append(FormField(
                        name=param,
                        label=field_info.get("label", param.title()),
                        field_type=field_info.get("type", "text"),
                        required=field_info.get("required", True),
                        options=field_info.get("options", []),
                        placeholder=field_info.get("placeholder", "")
                    ))
            
            response_format = ResponseFormat.FORM if form_fields else ResponseFormat.QUICK_REPLIES
            
            return AgentResponse(
                agent_name="clarification_agent",
                content=clarification_data.get("message", "I need a bit more information to help you better."),
                response_format=response_format,
                quick_replies=clarification_data.get("quick_replies", []),
                requires_clarification=True,
                metadata={
                    "missing_params": missing_params,
                    "form_fields": [field.dict() for field in form_fields] if form_fields else []
                }
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback clarification
            return self._simple_clarification_response(missing_params, conversation_type)
    
    def _simple_clarification_response(
        self, 
        missing_params: List[str], 
        conversation_type: ConversationType
    ) -> AgentResponse:
        """Simple fallback clarification response"""
        
        param_questions = self.clarification_mappings.get(conversation_type, {})
        
        if missing_params and missing_params[0] in param_questions:
            question = param_questions[missing_params[0]]
            return AgentResponse(
                agent_name="clarification_agent",
                content=question,
                response_format=ResponseFormat.QUICK_REPLIES,
                quick_replies=["Help me decide", "Skip this", "Show me options", "I'm not sure"],
                requires_clarification=True
            )
        
        return AgentResponse(
            agent_name="clarification_agent",
            content="I need a bit more information to help you better. What specific details are you looking for?",
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=["Help me decide", "Show me options", "I'm not sure", "Start over"],
            requires_clarification=True
        )
    
    def _extract_context_from_conversation(self, state: ConversationState) -> Dict[str, Any]:
        """Extract relevant context from conversation history"""
        
        context = {}
        
        # Get the latest user message
        if state.conversation_history:
            last_message = state.conversation_history[-1]
            context["original_query"] = last_message.content
        
        # Extract from user intent
        if state.current_intent:
            entities = state.current_intent.entities
            for key, value in entities.items():
                context[key] = value
        
        # Extract from conversation state context
        context.update(state.context)
        
        return context
    
    def _fallback_response(self, action: AgentAction) -> AgentResponse:
        """Fallback response for unhandled actions"""
        
        return AgentResponse(
            agent_name="clarification_agent",
            content="I help collect missing information to provide better assistance. What details can I help you clarify?",
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=["Start over", "Help me decide", "Show me options", "I'm not sure"],
            requires_clarification=True
        )
    
    def _get_clarification_system_prompt(self) -> str:
        return """You are a clarification agent that helps gather missing information from users.
Your job is to ask smart, contextual questions to collect missing parameters while maintaining a natural conversation flow.

Key principles:
1. Ask only for truly essential information
2. Use context from the conversation to make smart suggestions
3. Provide quick replies that help users move forward
4. Don't over-complicate simple requests
5. Be helpful and encouraging

You must respond with a JSON object containing:
- message: the clarification question/message
- quick_replies: array of 3-4 helpful quick reply options
- use_form: boolean (true if complex form needed, false for simple questions)
- form_fields: object with field definitions if use_form is true

Focus on getting users to their goal quickly rather than collecting every possible detail."""

    def _get_clarification_human_prompt(self) -> str:
        return """Missing Parameters: {missing_params}
Conversation Type: {conversation_type}
Business Type: {business_type}
Context: {context}
Parameter Questions: {param_questions}

Generate a helpful clarification response that gets the user closer to their goal:""" 