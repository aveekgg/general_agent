from typing import Dict, List, Optional, Any, Tuple
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import json
import asyncio

from app.core.config import BusinessConfig, ConversationType, BusinessType, settings
from app.models.schemas import (
    ConversationState, UserIntent, AgentAction, AgentResponse,
    ActionType, ResponseFormat, ConversationMessage, MessageType
)


class OrchestratorAgent:
    """
    The Orchestrator Agent is the brain of the multi-agent system.
    It classifies user intents, determines optimal actions, and coordinates specialized agents.
    """
    
    def __init__(self, business_type: BusinessType):
        self.business_type = business_type
        self.business_config = BusinessConfig(business_type)
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.1,
            api_key=settings.openai_api_key
        )
        
        # Initialize specialized agents registry
        self.specialized_agents = {}
        
        # Define required parameters per action type
        self.action_required_params = {
            ActionType.SEARCH_PRODUCTS: [],  # No required params - can search with any criteria
            ActionType.GET_PRODUCT_DETAILS: [],  # No required params - can search by name
            ActionType.COMPARE_PRODUCTS: [],  # No required params - can extract from context
            ActionType.RECOMMEND_ITEMS: [],  # No required params - can use conversation context
            ActionType.CLARIFY_PARAMS: ["missing_params"],  # Only clarify_params requires missing_params
            ActionType.GENERAL_RESPONSE: [],  # No required params
        }
        
    async def process_message(
        self, 
        message: str, 
        conversation_state: ConversationState
    ) -> Tuple[UserIntent, List[AgentAction]]:
        """
        Main orchestration logic: 
        1. Classify user intent
        2. Determine optimal actions
        3. Return actions with instructions
        """
        
        # Step 1: Classify user intent
        user_intent = await self._classify_intent(message, conversation_state)
        
        # Step 2: Determine required actions based on intent
        actions = await self._determine_actions(user_intent, conversation_state)
        
        # Step 3: Validate parameters and add clarification actions if needed
        actions = await self._validate_and_enhance_actions(actions, user_intent, conversation_state)
        
        return user_intent, actions
    
    async def _classify_intent(self, message: str, state: ConversationState) -> UserIntent:
        """Classify the user's intent and extract entities"""
        
        # Get business-specific context
        business_context = self.business_config.config
        conversation_history = self._format_conversation_history(state.conversation_history[-5:])  # Last 5 messages
        
        classification_prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_classification_system_prompt()),
            ("human", self._get_classification_human_prompt())
        ])
        
        prompt_input = {
            "message": message,
            "business_type": self.business_type.value,
            "business_context": json.dumps(business_context, indent=2),
            "conversation_history": conversation_history,
            "current_context": json.dumps(state.context, indent=2)
        }
        
        response = await self.llm.ainvoke(classification_prompt.format(**prompt_input))
        
        # Parse the structured response
        try:
            print(f"🔍 [CLASSIFY_INTENT] Raw LLM response: {response.content}")
            
            # Strip markdown code blocks if present
            content = response.content.strip()
            if content.startswith('```json'):
                content = content[7:]  # Remove ```json
            if content.startswith('```'):
                content = content[3:]   # Remove ```
            if content.endswith('```'):
                content = content[:-3]  # Remove trailing ```
            content = content.strip()
            
            print(f"🔍 [CLASSIFY_INTENT] Cleaned content: {content}")
            intent_data = json.loads(content)
            print(f"🔍 [CLASSIFY_INTENT] Parsed JSON: {intent_data}")
            
            # Handle case sensitivity by converting to lowercase
            conversation_type_value = intent_data["conversation_type"].lower()
            
            return UserIntent(
                conversation_type=ConversationType(conversation_type_value),
                confidence=intent_data["confidence"],
                entities=intent_data.get("entities", {}),
                required_params=intent_data.get("required_params", []),
                missing_params=intent_data.get("missing_params", [])
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Fallback classification
            print(f"❌ [CLASSIFY_INTENT] JSON parsing failed: {e}")
            print(f"❌ [CLASSIFY_INTENT] Raw response was: {response.content}")
            return UserIntent(
                conversation_type=ConversationType.GENERAL_CONVERSATION,
                confidence=0.5,
                entities={},
                required_params=[],
                missing_params=[]
            )
    
    async def _determine_actions(
        self, 
        user_intent: UserIntent, 
        state: ConversationState
    ) -> List[AgentAction]:
        """Determine the optimal actions based on user intent"""
        
        conversation_flow = self.business_config.get_conversation_flow(user_intent.conversation_type)
        
        action_planning_prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_action_planning_system_prompt()),
            ("human", self._get_action_planning_human_prompt())
        ])
        
        prompt_input = {
            "user_intent": user_intent.dict(),
            "conversation_flow": json.dumps(conversation_flow, indent=2),
            "business_config": json.dumps(self.business_config.config, indent=2),
            "current_context": json.dumps(state.context, indent=2),
            "available_actions": [action.value for action in ActionType]
        }
        
        response = await self.llm.ainvoke(action_planning_prompt.format(**prompt_input))
        
        try:
            # Strip markdown code blocks if present
            content = response.content.strip()
            if content.startswith('```json'):
                content = content[7:]  # Remove ```json
            if content.startswith('```'):
                content = content[3:]   # Remove ```
            if content.endswith('```'):
                content = content[:-3]  # Remove trailing ```
            content = content.strip()
            
            print(f"📝 [ACTION_PLANNING] Raw LLM response: {response.content}")
            print(f"📝 [ACTION_PLANNING] Cleaned content: {content}")
            actions_data = json.loads(content)
            print(f"📝 [ACTION_PLANNING] Parsed actions: {actions_data}")
            actions = []
            
            for action_item in actions_data["actions"]:
                action = AgentAction(
                    action_type=ActionType(action_item["action_type"]),
                    agent_name=action_item["agent_name"],
                    parameters=action_item.get("parameters", {}),
                    priority=action_item.get("priority", 1),
                    instructions=action_item.get("instructions", "")
                )
                actions.append(action)
            
            # Sort by priority (higher priority first)
            actions.sort(key=lambda x: x.priority, reverse=True)
            return actions
            
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback action using existing agent
            return [AgentAction(
                action_type=ActionType.GENERAL_RESPONSE,
                agent_name="product_discovery_agent",
                parameters={},
                priority=1,
                instructions="Provide a helpful general response"
            )]
    
    async def _validate_and_enhance_actions(
        self, 
        actions: List[AgentAction], 
        user_intent: UserIntent, 
        conversation_state: ConversationState
    ) -> List[AgentAction]:
        """Validate actions and add clarification actions if needed"""
        
        validated_actions = []
        
        for action in actions:
            # Check if action has required parameters
            required_params = self.action_required_params.get(action.action_type, [])
            missing_params = []
            
            for param in required_params:
                if param not in action.parameters or not action.parameters[param]:
                    missing_params.append(param)
            
            # If missing required parameters, add clarification action
            if missing_params:
                clarification_action = AgentAction(
                    action_type=ActionType.CLARIFY_PARAMS,
                    agent_name="product_discovery_agent",  # Default to product_discovery_agent
                    parameters={
                        "missing_params": missing_params,
                        "context": action.parameters
                    },
                    priority=action.priority + 1,  # Higher priority than original action
                    instructions=f"Clarify missing parameters: {', '.join(missing_params)}"
                )
                validated_actions.append(clarification_action)
            
            # Add the original action
            validated_actions.append(action)
        
        return validated_actions
    
    def _format_conversation_history(self, messages: List[ConversationMessage]) -> str:
        """Format conversation history for prompt"""
        formatted = []
        for msg in messages:
            role = "User" if msg.message_type == MessageType.USER else "Assistant"
            formatted.append(f"{role}: {msg.content}")
        return "\n".join(formatted)
    
    def _get_classification_system_prompt(self) -> str:
        return """You are an intelligent conversation classifier for a customer service system.
Your job is to analyze user messages and classify them into one of five conversation types:

1. company_info: Questions about the business, services, locations, hours, policies
2. product_discovery: Looking for products/services, recommendations, browsing (general search)
3. product_detail: Questions about specific products, detailed information, specifications, comparisons
4. process_questions: Questions about purchasing, ordering, delivery, returns, account issues
5. general_conversation: Greetings, small talk, or unclear intent

Key distinctions:
- product_discovery: "Show me laptops", "What do you recommend?", "I need something for gaming"
- product_detail: "Tell me about the MacBook Pro", "Compare iPhone vs Samsung", "What are the specs?"

IMPORTANT: You must respond with exact lowercase values for conversation_type.

You must respond with a valid JSON object containing:
- conversation_type: one of the five types above (lowercase)
- confidence: float between 0.0 and 1.0
- entities: extracted entities (product names, model numbers, brands, specifications, etc.)
- required_params: a simple list of strings (e.g., ["preferences", "budget"])
- missing_params: a simple list of strings (e.g., ["preferences"])

IMPORTANT: Only mark parameters as required/missing if they are absolutely critical for the query.
Most queries can be handled without additional parameters.

CRITICAL: For product_detail queries, product_id is NEVER required. The system can search by product name, brand, model, etc.
- DO NOT mark product_id as required or missing for any product_detail query
- Product names, brands, models extracted from the message are sufficient
- Only mark parameters as missing if NO product information is available at all

Consider the business type, conversation history, and current context when classifying."""

    def _get_classification_human_prompt(self) -> str:
        return """Business Type: {business_type}
Business Context: {business_context}

Conversation History:
{conversation_history}

Current Context: {current_context}

User Message: "{message}"

Classify this message and return a JSON response:"""

    def _get_action_planning_system_prompt(self) -> str:
        return """You are an action planning agent for a customer service system.
Based on the classified user intent, determine the optimal sequence of actions to take.

Available Actions:
- search_products: Search for products/services (general search)
- get_company_info: Retrieve company information
- get_product_details: Get detailed information about specific products
- compare_products: Compare multiple products side-by-side
- track_order: Track order status
- clarify_params: Ask for missing parameters
- recommend_items: Generate recommendations
- general_response: Provide general conversational response

Agent Assignments (use these exact agent names):
- product_discovery_agent: search_products, recommend_items, general_response, clarify_params
- product_detail_agent: get_product_details, compare_products

IMPORTANT: Only use these agent names: product_discovery_agent, product_detail_agent
If unsure, default to product_discovery_agent with search_products action.

GUIDELINES:
- For product searches with clear criteria (e.g., "laptops under $1000"), use search_products directly
- Don't require additional preferences for simple category + budget searches
- Only use clarify_params if critical information is missing (not preferences)

GUIDELINES:
- For product searches with clear criteria (e.g., "laptops under $1000"), use search_products directly
- For product detail queries with clear product names (e.g., "Tell me about MacBook Pro"), use get_product_details directly
- Don't require additional preferences for simple category + budget searches
- Only use clarify_params if critical information is missing (not preferences)

For each action, specify:
- action_type: the action to take
- agent_name: which specialized agent should handle it (from list above)
- parameters: specific parameters for the action
- priority: 1-10 (10 being highest priority)
- instructions: specific instructions for the agent

Return a JSON object with an "actions" array."""

    def _get_action_planning_human_prompt(self) -> str:
        return """User Intent: {user_intent}
Conversation Flow: {conversation_flow}
Business Configuration: {business_config}
Current Context: {current_context}
Available Actions: {available_actions}

Plan the optimal actions to address this user intent:"""

    def register_agent(self, agent_name: str, agent_instance):
        """Register a specialized agent"""
        self.specialized_agents[agent_name] = agent_instance
    
    async def coordinate_agents(
        self,
        actions: List[AgentAction],
        conversation_state: ConversationState
    ) -> List[AgentResponse]:
        """Coordinate execution of actions across specialized agents"""
        
        responses = []
        
        # Execute actions in priority order
        for action in actions:
            if action.agent_name in self.specialized_agents:
                agent = self.specialized_agents[action.agent_name]
                try:
                    response = await agent.execute_action(action, conversation_state)
                    responses.append(response)
                except Exception as e:
                    # Handle agent execution errors gracefully
                    error_response = AgentResponse(
                        agent_name=action.agent_name,
                        content=f"I apologize, but I encountered an issue processing your request. Please try rephrasing or contact support.",
                        response_format=ResponseFormat.TEXT,
                        metadata={"error": str(e)}
                    )
                    responses.append(error_response)
            else:
                # Agent not found - provide fallback response
                fallback_response = AgentResponse(
                    agent_name="orchestrator",
                    content="I understand your request, but I'm not able to process it right now. Please try again or contact support.",
                    response_format=ResponseFormat.TEXT
                )
                responses.append(fallback_response)
        
        return responses 