from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import BusinessConfig, BusinessType, settings
from app.models.schemas import (
    AgentAction, AgentResponse, ConversationState, ResponseFormat,
    ConversationMessage, MessageType
)


class BaseAgent(ABC):
    """
    Abstract base class for all specialized agents in the multi-agent system.
    Provides common functionality and enforces consistent interface.
    """
    
    def __init__(self, business_type: BusinessType, agent_name: str):
        self.business_type = business_type
        self.agent_name = agent_name
        self.business_config = BusinessConfig(business_type)
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.2,
            api_key=settings.openai_api_key
        )
        
        # Common tools and resources
        self.tools = {}
        self.knowledge_base = {}
        
    @abstractmethod
    async def execute_action(
        self, 
        action: AgentAction, 
        conversation_state: ConversationState
    ) -> AgentResponse:
        """
        Execute the assigned action and return appropriate response.
        Must be implemented by each specialized agent.
        """
        pass
    
    def get_supported_actions(self) -> List[str]:
        """Return list of actions this agent can handle"""
        return []
    
    def format_conversation_history(
        self, 
        messages: List[ConversationMessage], 
        limit: int = 5
    ) -> str:
        """Format recent conversation history for context"""
        recent_messages = messages[-limit:] if len(messages) > limit else messages
        formatted = []
        
        for msg in recent_messages:
            role = "User" if msg.message_type == MessageType.USER else "Assistant"
            formatted.append(f"{role}: {msg.content}")
        
        return "\n".join(formatted)
    
    def extract_entities(self, conversation_state: ConversationState, entity_type: str) -> List[Any]:
        """Extract specific entities from conversation state"""
        entities = []
        
        # From current intent
        if conversation_state.current_intent and conversation_state.current_intent.entities:
            intent_entities = conversation_state.current_intent.entities.get(entity_type, [])
            if isinstance(intent_entities, list):
                entities.extend(intent_entities)
            elif intent_entities:  # Single entity
                entities.append(intent_entities)
        
        # From conversation context
        context_entities = conversation_state.context.get(entity_type, [])
        if isinstance(context_entities, list):
            entities.extend(context_entities)
        elif context_entities:
            entities.append(context_entities)
        
        return list(set(str(e) for e in entities))  # Remove duplicates and ensure strings
    
    def create_clarification_response(
        self, 
        message: str, 
        quick_replies: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> AgentResponse:
        """Create a standardized clarification response"""
        return AgentResponse(
            agent_name=self.agent_name,
            content=message,
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=quick_replies or [],
            metadata=metadata or {},
            requires_clarification=True
        )
    
    def create_error_response(
        self, 
        error_message: str = None,
        fallback_actions: List[str] = None
    ) -> AgentResponse:
        """Create a standardized error response"""
        default_message = f"I apologize, but I encountered an issue processing your request. Let me help you in another way."
        default_actions = ["Try again", "Contact support", "Browse options"]
        
        return AgentResponse(
            agent_name=self.agent_name,
            content=error_message or default_message,
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=fallback_actions or default_actions,
            metadata={"error": True},
            requires_clarification=False
        )
    
    def get_business_context(self) -> Dict[str, Any]:
        """Get relevant business context for this agent"""
        return {
            "business_type": self.business_type.value,
            "config": self.business_config.config,
            "agent_name": self.agent_name
        }
    
    async def generate_response_content(
        self,
        system_prompt: str,
        human_prompt: str,
        prompt_variables: Dict[str, Any],
        fallback_response: str = None
    ) -> Dict[str, Any]:
        """Generate response content using LLM with error handling"""
        
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", human_prompt)
            ])
            
            response = await self.llm.ainvoke(prompt.format(**prompt_variables))
            
            # Try to parse as JSON first
            try:
                import json
                return json.loads(response.content)
            except json.JSONDecodeError:
                # If not JSON, return as plain text
                return {
                    "message": response.content,
                    "quick_replies": []
                }
                
        except Exception as e:
            # Fallback response
            return {
                "message": fallback_response or "I'm here to help! Please let me know what you need.",
                "quick_replies": ["Help", "Try again", "Contact support"],
                "error": str(e)
            }
    
    def validate_required_parameters(
        self, 
        action: AgentAction, 
        required_params: List[str]
    ) -> tuple[bool, List[str]]:
        """Validate that required parameters are present in action"""
        missing_params = []
        
        for param in required_params:
            if param not in action.parameters or not action.parameters[param]:
                missing_params.append(param)
        
        return len(missing_params) == 0, missing_params
    
    def get_quick_replies_for_context(
        self, 
        context_type: str,
        conversation_state: ConversationState
    ) -> List[str]:
        """Get context-appropriate quick replies"""
        
        business_quick_replies = self.business_config.config.get("quick_replies", {})
        context_replies = business_quick_replies.get(context_type, [])
        
        # Add business-specific quick replies
        if self.business_type == BusinessType.ECOMMERCE:
            base_replies = ["Browse products", "Check cart", "Track order", "Contact support"]
        elif self.business_type == BusinessType.HOTEL:
            base_replies = ["Check availability", "View rooms", "Book now", "Contact hotel"]
        elif self.business_type == BusinessType.REAL_ESTATE:
            base_replies = ["View properties", "Schedule viewing", "Get pre-approved", "Contact agent"]
        elif self.business_type == BusinessType.RENTAL:
            base_replies = ["Check availability", "View items", "Make reservation", "Contact us"]
        else:
            base_replies = ["Learn more", "Get help", "Browse options", "Contact us"]
        
        # Combine context-specific and base replies, remove duplicates
        all_replies = list(set(context_replies + base_replies))
        return all_replies[:4]  # Limit to 4 quick replies for better UX
    
    def log_action_execution(
        self, 
        action: AgentAction, 
        response: AgentResponse, 
        execution_time: float = None
    ):
        """Log action execution for analytics and debugging"""
        log_data = {
            "agent": self.agent_name,
            "action": action.action_type.value,
            "success": not response.metadata.get("error", False),
            "response_format": response.response_format.value,
            "requires_clarification": response.requires_clarification,
            "execution_time": execution_time
        }
        
        # In a real implementation, this would log to a proper logging system
        # For now, we can use this for debugging
        if settings.debug:
            print(f"Agent Action Log: {log_data}")
    
    def update_conversation_context(
        self, 
        conversation_state: ConversationState, 
        updates: Dict[str, Any]
    ):
        """Update conversation context with new information"""
        for key, value in updates.items():
            conversation_state.context[key] = value 