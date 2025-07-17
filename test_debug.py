#!/usr/bin/env python3
"""
Debug script to test the multi-agent workflow step by step
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.agents.orchestrator import OrchestratorAgent
from app.agents.product_discovery_agent import ProductDiscoveryAgent
from app.agents.product_detail_agent import ProductDetailAgent
from app.models.schemas import ConversationMessage, ConversationState, MessageType
from app.core.config import BusinessType
from datetime import datetime

async def test_workflow():
    """Test the complete workflow"""
    
    print("🧪 Testing Multi-Agent Workflow Debug")
    print("=" * 50)
    
    # Test query for custom attribute filtering
    test_query = "Show me red laptops"
    business_type = BusinessType.ECOMMERCE
    
    print(f"📝 Testing query: '{test_query}'")
    print(f"🏢 Business type: {business_type.value}")
    print()
    
    # Initialize orchestrator
    orchestrator = OrchestratorAgent(business_type)
    
    # Register specialized agents
    product_discovery_agent = ProductDiscoveryAgent(business_type)
    product_detail_agent = ProductDetailAgent(business_type)
    
    orchestrator.register_agent("product_discovery_agent", product_discovery_agent)
    orchestrator.register_agent("product_detail_agent", product_detail_agent)
    
    # Create conversation state
    conversation_state = ConversationState(
        session_id="test_session",
        business_type=business_type,
        conversation_history=[
            ConversationMessage(
                id="user_1",
                session_id="test_session",
                message_type=MessageType.USER,
                content=test_query,
                timestamp=datetime.now()
            )
        ]
    )
    
    try:
        # Process the message
        user_intent, planned_actions = await orchestrator.process_message(
            test_query, conversation_state
        )
        
        print(f"🎯 [CLASSIFY_INTENT] Classified as: {user_intent.conversation_type.value} (confidence: {user_intent.confidence})")
        print(f"📝 [CLASSIFY_INTENT] Entities extracted: {user_intent.entities}")
        print(f"⚡ [CLASSIFY_INTENT] Planned actions: {len(planned_actions)} actions")
        
        for i, action in enumerate(planned_actions, 1):
            print(f"   Action {i}: {action.action_type.value} -> {action.agent_name} (priority: {action.priority})")
        
        # Validate and execute actions
        print(f"\n📋 [PLAN_ACTIONS] Validating planned actions...")
        
        # Remove duplicates
        unique_actions = []
        seen_combinations = set()
        for action in planned_actions:
            combination = (action.action_type, action.agent_name, str(sorted(action.parameters.items())))
            if combination not in seen_combinations:
                seen_combinations.add(combination)
                unique_actions.append(action)
            else:
                print(f"⚠️ [PLAN_ACTIONS] Duplicate action removed: {action.action_type.value} -> {action.agent_name}")
        
        # Check agent availability and redirect if needed
        validated_actions = []
        available_agents = ["product_detail_agent", "product_discovery_agent"]
        
        for action in unique_actions:
            if action.agent_name not in available_agents:
                print(f"⚠️ [PLAN_ACTIONS] Agent '{action.agent_name}' not found, using fallback")
                # Redirect to product_discovery_agent as fallback
                action.agent_name = "product_discovery_agent"
                print(f"   → Redirected to '{action.agent_name}'")
            validated_actions.append(action)
        
        print(f"✅ [PLAN_ACTIONS] {len(validated_actions)} actions validated (removed duplicates)")
        
        # Execute actions
        print(f"\n🤖 [EXECUTE_ACTIONS] Executing {len(validated_actions)} actions...")
        print(f"🔧 [EXECUTE_ACTIONS] Available agents: {available_agents}")
        
        agent_responses = []
        for action in validated_actions:
            print(f"   Executing: {action.action_type.value} -> {action.agent_name}")
            if action.agent_name in orchestrator.specialized_agents:
                print(f"   ✅ Agent '{action.agent_name}' found")
                try:
                    response = await orchestrator.specialized_agents[action.agent_name].execute_action(
                        action, conversation_state
                    )
                    agent_responses.append(response)
                except Exception as e:
                    print(f"   ❌ Error executing action: {e}")
                    continue
            else:
                print(f"   ❌ Agent '{action.agent_name}' not found")
        
        print(f"📤 [EXECUTE_ACTIONS] Got {len(agent_responses)} responses")
        
        # Show response previews and find the best one
        print(f"\n💬 [GENERATE_RESPONSE] Processing agent responses...")
        print(f"💬 [GENERATE_RESPONSE] Received {len(agent_responses)} agent responses")
        
        best_response = None
        best_score = 0
        
        for i, response in enumerate(agent_responses, 1):
            preview = response.content[:80] + "..." if len(response.content) > 80 else response.content
            print(f"   Response {i}: {response.agent_name} -> {response.response_format.value}")
            print(f"   Content preview: {preview}")
            
            # Score this response
            score = 0
            if response.response_format.value == "carousel":
                score += 10
                if response.metadata and response.metadata.get("carousel_items"):
                    score += len(response.metadata["carousel_items"])
            elif response.response_format.value == "quick_replies":
                score += 4
            elif response.response_format.value == "text":
                score += 2
            
            if score > best_score:
                best_score = score
                best_response = response
        
        if best_response:
            print(f"\n🎯 [RESPONSE_SELECTION] Selected response: {best_response.response_format.value} (score: {best_score})")
            preview = best_response.content[:80] + "..." if len(best_response.content) > 80 else best_response.content
            print(f"   Content preview: {preview}")
            
            print(f"\n✅ SUCCESS - Got response:")
            print(f"📨 Message: {best_response.content}")
            print(f"🎨 Format: {best_response.response_format.value}")
            print(f"⚡ Quick replies: {best_response.quick_replies}")
            
            # Show carousel items if available
            if best_response.metadata and best_response.metadata.get("carousel_items"):
                carousel_items = best_response.metadata["carousel_items"]
                print(f"🎠 Carousel items: {len(carousel_items)}")
                print(f"\n🎠 CAROUSEL ITEMS:")
                for i, item in enumerate(carousel_items, 1):
                    color = item.get('metadata', {}).get('color', 'N/A')
                    brand = item.get('metadata', {}).get('brand', 'N/A')
                    print(f"   {i}. {item['name']} - ${item['price']} (Color: {color}, Brand: {brand})")
            
            print(f"\n📋 Metadata: {best_response.metadata}")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_workflow()) 