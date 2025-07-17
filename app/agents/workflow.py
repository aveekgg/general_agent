from typing import Dict, List, Optional, Any, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import uuid
import json
from datetime import datetime

from app.core.config import BusinessType, ConversationType
from app.models.schemas import (
    ConversationState, ConversationMessage, MessageType, UserIntent, 
    AgentAction, AgentResponse, ChatRequest, ChatResponse, ResponseFormat, ActionType
)
from app.agents.orchestrator import OrchestratorAgent
from app.agents.product_detail_agent import ProductDetailAgent
from app.agents.product_discovery_agent import ProductDiscoveryAgent


class WorkflowState(TypedDict):
    """State maintained throughout the workflow execution"""
    conversation_state: ConversationState
    user_message: str
    user_intent: Optional[UserIntent]
    planned_actions: List[AgentAction]
    agent_responses: List[AgentResponse]
    final_response: Optional[ChatResponse]
    error: Optional[str]


class MultiAgentWorkflow:
    """
    Main LangGraph workflow that orchestrates the multi-agent customer service system.
    Handles the complete conversation flow from intent classification to response generation.
    """
    
    def __init__(self, business_type: BusinessType):
        self.business_type = business_type
        
        # Initialize agents
        self.orchestrator = OrchestratorAgent(business_type)
        self.agents = {
            "product_detail_agent": ProductDetailAgent(business_type),
            "product_discovery_agent": ProductDiscoveryAgent(business_type),
            # Other agents will be added here as we implement them
        }
        
        # Register agents with orchestrator
        for agent_name, agent_instance in self.agents.items():
            self.orchestrator.register_agent(agent_name, agent_instance)
        
        # Agent mapping for different conversation types
        self.agent_mapping = {
            ConversationType.PRODUCT_DISCOVERY: "product_discovery_agent",
            ConversationType.PRODUCT_DETAIL: "product_detail_agent", 
            ConversationType.COMPANY_INFO: "product_discovery_agent",  # fallback
            ConversationType.PROCESS_QUESTIONS: "product_discovery_agent",  # fallback
            ConversationType.GENERAL_CONVERSATION: "product_discovery_agent",  # fallback
        }
        
        # Initialize the workflow graph
        self.workflow = self._create_workflow()
        self.memory = MemorySaver()
        
        # Compile the workflow
        self.app = self.workflow.compile(checkpointer=self.memory)
    
    def _create_workflow(self) -> StateGraph:
        """Create the LangGraph workflow"""
        
        workflow = StateGraph(WorkflowState)
        
        # Add nodes
        workflow.add_node("classify_intent", self._classify_intent_node)
        workflow.add_node("plan_actions", self._plan_actions_node)
        workflow.add_node("execute_actions", self._execute_actions_node)
        workflow.add_node("generate_response", self._generate_response_node)
        workflow.add_node("handle_error", self._handle_error_node)
        
        # Define the workflow flow
        workflow.set_entry_point("classify_intent")
        
        # From classify_intent
        workflow.add_edge("classify_intent", "plan_actions")
        
        # From plan_actions
        workflow.add_edge("plan_actions", "execute_actions")
        
        # From execute_actions - conditional routing
        workflow.add_conditional_edges(
            "execute_actions",
            self._should_continue_or_respond,
            {
                "generate_response": "generate_response",
                "handle_error": "handle_error"
            }
        )
        
        # Terminal nodes
        workflow.add_edge("generate_response", END)
        workflow.add_edge("handle_error", END)
        
        return workflow
    
    async def process_message(self, chat_request: ChatRequest) -> ChatResponse:
        """Process a chat message through the multi-agent workflow"""
        
        # Initialize conversation state
        conversation_state = ConversationState(
            session_id=chat_request.session_id,
            user_id=chat_request.user_id,
            business_type=chat_request.business_type,
            context=chat_request.context
        )
        
        # Add user message to conversation history
        user_message = ConversationMessage(
            id=str(uuid.uuid4()),
            session_id=chat_request.session_id,
            message_type=MessageType.USER,
            content=chat_request.message,
            timestamp=datetime.now()
        )
        
        # Ensure conversation_history is a list and append message
        if not hasattr(conversation_state, 'conversation_history') or conversation_state.conversation_history is None:
            conversation_state.conversation_history = []
        conversation_state.conversation_history.append(user_message)
        
        # Initialize workflow state
        initial_state = WorkflowState(
            conversation_state=conversation_state,
            user_message=chat_request.message,
            user_intent=None,
            planned_actions=[],
            agent_responses=[],
            final_response=None,
            error=None
        )
        
        # Execute the workflow
        config = {"configurable": {"thread_id": chat_request.session_id}}
        
        try:
            result = await self.app.ainvoke(initial_state, config)
            
            if result.get("error"):
                return self._create_error_response(chat_request.session_id, result["error"])
            
            return result["final_response"]
            
        except Exception as e:
            return self._create_error_response(chat_request.session_id, str(e))
    
    async def _classify_intent_node(self, state: WorkflowState) -> WorkflowState:
        """Node: Classify user intent using the orchestrator"""
        
        try:
            print(f"🔍 [CLASSIFY_INTENT] Processing message: '{state['user_message']}'")
            
            user_intent, planned_actions = await self.orchestrator.process_message(
                state["user_message"], 
                state["conversation_state"]
            )
            
            print(f"🎯 [CLASSIFY_INTENT] Classified as: {user_intent.conversation_type.value} (confidence: {user_intent.confidence})")
            print(f"📝 [CLASSIFY_INTENT] Entities extracted: {user_intent.entities}")
            print(f"⚡ [CLASSIFY_INTENT] Planned actions: {len(planned_actions)} actions")
            for i, action in enumerate(planned_actions):
                print(f"   Action {i+1}: {action.action_type.value} -> {action.agent_name} (priority: {action.priority})")
            
            # Update conversation state with intent
            state["conversation_state"].current_intent = user_intent
            
            return {
                **state,
                "user_intent": user_intent,
                "planned_actions": planned_actions
            }
            
        except Exception as e:
            print(f"❌ [CLASSIFY_INTENT] Error: {str(e)}")
            return {
                **state,
                "error": f"Intent classification failed: {str(e)}"
            }
    
    async def _plan_actions_node(self, state: WorkflowState) -> WorkflowState:
        """Node: Plan and prioritize actions with robust validation"""
        
        print(f"📋 [PLAN_ACTIONS] Validating planned actions...")
        
        # The orchestrator already planned actions, so we validate and fix them
        planned_actions = state.get("planned_actions", [])
        user_intent = state.get("user_intent")
        
        if not planned_actions:
            print(f"⚠️ [PLAN_ACTIONS] No actions planned, creating fallback action")
            # Create fallback action using agent mapping
            fallback_agent = self._get_fallback_agent(user_intent)
            fallback_action = AgentAction(
                action_type=ActionType.GENERAL_RESPONSE,
                agent_name=fallback_agent,
                parameters={},
                priority=1,
                instructions="Provide a helpful general response"
            )
            planned_actions = [fallback_action]
        else:
            # Validate and fix agent assignments, remove duplicates
            validated_actions = []
            seen_actions = set()
            
            for action in planned_actions:
                # Create a unique identifier for this action (safe for lists/dicts)
                params_str = json.dumps(action.parameters, sort_keys=True) if action.parameters else ""
                action_key = (action.action_type.value, action.agent_name, params_str)
                
                # Skip duplicates
                if action_key in seen_actions:
                    print(f"⚠️ [PLAN_ACTIONS] Skipping duplicate action: {action.action_type.value}")
                    continue
                
                seen_actions.add(action_key)
                
                if action.agent_name not in self.agents:
                    print(f"⚠️ [PLAN_ACTIONS] Agent '{action.agent_name}' not found, using fallback")
                    # Use agent mapping to find correct agent
                    correct_agent = self._get_agent_for_action(action, user_intent)
                    action.agent_name = correct_agent
                    print(f"   → Redirected to '{correct_agent}'")
                
                validated_actions.append(action)
            
            planned_actions = validated_actions
            print(f"✅ [PLAN_ACTIONS] {len(planned_actions)} actions validated (removed duplicates)")
        
        return {
            **state,
            "planned_actions": planned_actions
        }
    
    def _get_fallback_agent(self, user_intent: Optional[UserIntent]) -> str:
        """Get fallback agent based on user intent"""
        if user_intent and user_intent.conversation_type in self.agent_mapping:
            return self.agent_mapping[user_intent.conversation_type]
        return "product_discovery_agent"  # ultimate fallback
    
    def _get_agent_for_action(self, action: AgentAction, user_intent: Optional[UserIntent]) -> str:
        """Get the correct agent for an action"""
        # First try direct mapping based on action type
        action_agent_mapping = {
            ActionType.SEARCH_PRODUCTS: "product_discovery_agent",
            ActionType.RECOMMEND_ITEMS: "product_discovery_agent", 
            ActionType.GET_PRODUCT_DETAILS: "product_detail_agent",
            ActionType.COMPARE_PRODUCTS: "product_detail_agent",
            ActionType.GENERAL_RESPONSE: "product_discovery_agent",
        }
        
        if action.action_type in action_agent_mapping:
            return action_agent_mapping[action.action_type]
        
        # Fallback to intent-based mapping
        return self._get_fallback_agent(user_intent)
    
    async def _execute_actions_node(self, state: WorkflowState) -> WorkflowState:
        """Node: Execute planned actions using specialized agents"""
        
        try:
            print(f"🤖 [EXECUTE_ACTIONS] Executing {len(state['planned_actions'])} actions...")
            print(f"🔧 [EXECUTE_ACTIONS] Available agents: {list(self.agents.keys())}")
            
            for action in state["planned_actions"]:
                print(f"   Executing: {action.action_type.value} -> {action.agent_name}")
                if action.agent_name in self.agents:
                    print(f"   ✅ Agent '{action.agent_name}' found")
                else:
                    print(f"   ❌ Agent '{action.agent_name}' NOT FOUND")
            
            responses = await self.orchestrator.coordinate_agents(
                state["planned_actions"],
                state["conversation_state"]
            )
            
            print(f"📤 [EXECUTE_ACTIONS] Got {len(responses)} responses")
            for i, response in enumerate(responses):
                print(f"   Response {i+1}: {response.agent_name} -> {response.response_format.value}")
                print(f"   Content preview: {response.content[:100]}...")
            
            return {
                **state,
                "agent_responses": responses
            }
            
        except Exception as e:
            print(f"❌ [EXECUTE_ACTIONS] Error: {str(e)}")
            import traceback
            print(f"🔍 [EXECUTE_ACTIONS] Traceback: {traceback.format_exc()}")
            return {
                **state,
                "error": f"Action execution failed: {str(e)}"
            }
    
    async def _generate_response_node(self, state: WorkflowState) -> WorkflowState:
        """Node: Generate final response to user"""
        
        try:
            print(f"💬 [GENERATE_RESPONSE] Processing agent responses...")
            
            agent_responses = state.get("agent_responses", [])
            conversation_state = state["conversation_state"]
            
            print(f"💬 [GENERATE_RESPONSE] Received {len(agent_responses)} agent responses")
            
            if not agent_responses:
                print(f"⚠️ [GENERATE_RESPONSE] No agent responses, using fallback")
                # Fallback response
                final_response = ChatResponse(
                    message="I'm here to help! How can I assist you today?",
                    response_format=ResponseFormat.TEXT,
                    quick_replies=self._get_default_quick_replies(),
                    metadata={},
                    session_id=conversation_state.session_id
                )
            else:
                print(f"✨ [GENERATE_RESPONSE] Processing responses into final response")
                # Process agent responses into final chat response
                final_response = self._process_agent_responses(agent_responses, conversation_state)
                print(f"📨 [GENERATE_RESPONSE] Final response format: {final_response.response_format.value}")
                print(f"📨 [GENERATE_RESPONSE] Final message: {final_response.message[:100]}...")
            
            # Add assistant message to conversation history
            assistant_message = ConversationMessage(
                id=str(uuid.uuid4()),
                session_id=conversation_state.session_id,
                message_type=MessageType.ASSISTANT,
                content=final_response.message,
                metadata=final_response.metadata or {},
                timestamp=datetime.now()
            )
            
            # Ensure conversation_history is a list and append message
            if not hasattr(conversation_state, 'conversation_history') or conversation_state.conversation_history is None:
                conversation_state.conversation_history = []
            conversation_state.conversation_history.append(assistant_message)
            
            return {
                **state,
                "final_response": final_response
            }
            
        except Exception as e:
            return {
                **state,
                "error": f"Response generation failed: {str(e)}"
            }
    
    async def _handle_error_node(self, state: WorkflowState) -> WorkflowState:
        """Node: Handle errors gracefully"""
        
        error_message = state.get("error", "An unexpected error occurred")
        session_id = state["conversation_state"].session_id
        
        final_response = ChatResponse(
            message="I apologize, but I encountered an issue processing your request. Please try again or contact our support team.",
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=["Try again", "Contact support", "Browse help"],
            metadata={"error": error_message},
            session_id=session_id
        )
        
        return {
            **state,
            "final_response": final_response
        }
    
    def _should_continue_or_respond(self, state: WorkflowState) -> str:
        """Conditional routing: determine next step after action execution"""
        
        if state.get("error"):
            return "handle_error"
        
        return "generate_response"
    
    def _select_best_response(self, agent_responses: List[AgentResponse]) -> AgentResponse:
        """Select the best response from multiple agent responses"""
        
        if not agent_responses:
            return None
        
        if len(agent_responses) == 1:
            return agent_responses[0]
        
        # Response priority order (higher = better)
        format_priority = {
            ResponseFormat.CAROUSEL: 10,           # Product results - highest priority
            ResponseFormat.PRODUCT_DETAIL: 9,     # Detailed product info
            ResponseFormat.PRODUCT_COMPARISON: 8, # Product comparisons
            ResponseFormat.FORM: 7,               # Interactive forms
            ResponseFormat.MIXED: 6,              # Mixed content
            ResponseFormat.TEXT: 5,               # Plain text
            ResponseFormat.QUICK_REPLIES: 4,      # Quick replies - lower priority
        }
        
        # Sort responses by format priority, then by content quality
        def response_score(response: AgentResponse) -> int:
            score = format_priority.get(response.response_format, 1)
            
            # Boost score for responses with actual content
            if response.response_format == ResponseFormat.CAROUSEL:
                metadata = response.metadata or {}
                carousel_items = metadata.get("carousel_items", [])
                if carousel_items:
                    score += len(carousel_items)  # More items = better
            
            # Penalize generic fallback messages
            generic_phrases = [
                "I'd be happy to help",
                "I specialize in helping", 
                "I couldn't find any results",
                "Let me help you search"
            ]
            
            if any(phrase in response.content for phrase in generic_phrases):
                score -= 5
            
            return score
        
        # Select the best response
        best_response = max(agent_responses, key=response_score)
        
        print(f"🎯 [RESPONSE_SELECTION] Selected response: {best_response.response_format.value} (score: {response_score(best_response)})")
        print(f"   Content preview: {best_response.content[:100]}...")
        
        return best_response
    
    def _process_agent_responses(
        self, 
        agent_responses: List[AgentResponse], 
        conversation_state: ConversationState
    ) -> ChatResponse:
        """Process multiple agent responses into a single chat response"""
        
        if not agent_responses:
            return self._create_fallback_response(conversation_state.session_id)
        
        # Intelligent response selection: prefer actual results over fallbacks
        primary_response = self._select_best_response(agent_responses)
        
        # Handle different response formats
        if primary_response.response_format == ResponseFormat.PRODUCT_DETAIL:
            return ChatResponse(
                message=primary_response.content,
                response_format=ResponseFormat.PRODUCT_DETAIL,
                quick_replies=primary_response.quick_replies,
                metadata=primary_response.metadata or {},
                session_id=conversation_state.session_id
            )
        
        elif primary_response.response_format == ResponseFormat.PRODUCT_COMPARISON:
            return ChatResponse(
                message=primary_response.content,
                response_format=ResponseFormat.PRODUCT_COMPARISON,
                quick_replies=primary_response.quick_replies,
                metadata=primary_response.metadata or {},
                session_id=conversation_state.session_id
            )
        
        elif primary_response.response_format == ResponseFormat.CAROUSEL:
            # Extract carousel items from metadata
            metadata = primary_response.metadata or {}
            carousel_items = metadata.get("carousel_items", [])
            return ChatResponse(
                message=primary_response.content,
                response_format=ResponseFormat.CAROUSEL,
                carousel_items=carousel_items,
                quick_replies=primary_response.quick_replies,
                metadata=metadata,
                session_id=conversation_state.session_id
            )
        
        elif primary_response.response_format == ResponseFormat.FORM:
            # Extract form fields from metadata
            metadata = primary_response.metadata or {}
            form_fields = metadata.get("form_fields", [])
            return ChatResponse(
                message=primary_response.content,
                response_format=ResponseFormat.FORM,
                form_fields=form_fields,
                quick_replies=primary_response.quick_replies,
                metadata=metadata,
                session_id=conversation_state.session_id
            )
        
        else:
            # Default text or quick replies response
            return ChatResponse(
                message=primary_response.content,
                response_format=primary_response.response_format,
                quick_replies=primary_response.quick_replies,
                metadata=primary_response.metadata or {},
                session_id=conversation_state.session_id
            )
    
    def _get_default_quick_replies(self) -> List[str]:
        """Get default quick replies based on business type"""
        
        if self.business_type == BusinessType.ECOMMERCE:
            return ["Browse products", "Track order", "Contact support", "Help"]
        elif self.business_type == BusinessType.HOTEL:
            return ["Check availability", "View rooms", "Make reservation", "Contact hotel"]
        elif self.business_type == BusinessType.REAL_ESTATE:
            return ["View properties", "Schedule viewing", "Get information", "Contact agent"]
        elif self.business_type == BusinessType.RENTAL:
            return ["Check availability", "Browse items", "Make reservation", "Contact us"]
        else:
            return ["Get help", "Browse options", "Contact support", "Learn more"]
    
    def _create_fallback_response(self, session_id: str) -> ChatResponse:
        """Create a fallback response when no agent responses are available"""
        
        return ChatResponse(
            message="I'm here to help! What would you like to know?",
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=self._get_default_quick_replies(),
            metadata={},
            session_id=session_id
        )
    
    def _create_error_response(self, session_id: str, error: str) -> ChatResponse:
        """Create an error response"""
        
        return ChatResponse(
            message="I apologize, but I encountered an issue. Please try again or contact support.",
            response_format=ResponseFormat.QUICK_REPLIES,
            quick_replies=["Try again", "Contact support", "Help"],
            metadata={"error": error},
            session_id=session_id
        )
    
    async def get_conversation_history(self, session_id: str) -> List[ConversationMessage]:
        """Retrieve conversation history for a session"""
        
        config = {"configurable": {"thread_id": session_id}}
        
        try:
            # Get the current state from memory
            state = await self.app.aget_state(config)
            
            if state and state.values.get("conversation_state"):
                return state.values["conversation_state"].conversation_history
            
            return []
            
        except Exception:
            return []
    
    async def clear_conversation(self, session_id: str) -> bool:
        """Clear conversation history for a session"""
        
        config = {"configurable": {"thread_id": session_id}}
        
        try:
            # This would clear the conversation state in the memory
            # Implementation depends on the specific checkpointer being used
            return True
            
        except Exception:
            return False 