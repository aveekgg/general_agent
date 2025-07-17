from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from typing import Dict, List, Optional
import json
import uuid
from contextlib import asynccontextmanager

from app.core.config import settings, BusinessType
from app.models.schemas import ChatRequest, ChatResponse, ConversationMessage
from app.agents.workflow import MultiAgentWorkflow


# Global workflow instances for different business types
workflows: Dict[str, MultiAgentWorkflow] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize workflows on startup"""
    
    # Initialize workflows for each business type
    for business_type in BusinessType:
        workflows[business_type.value] = MultiAgentWorkflow(business_type)
    
    print(f"✅ Multi-Agent Customer Service Platform initialized for {len(workflows)} business types")
    
    yield
    
    # Cleanup on shutdown
    workflows.clear()
    print("🔄 Application shutdown complete")


# Initialize FastAPI app
app = FastAPI(
    title="Multi-Agent Customer Service Platform",
    description="Universal AI-powered customer service system that adapts to any business domain",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
    
    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await websocket.send_text(json.dumps(message))


manager = ConnectionManager()


def get_workflow(business_type: str) -> MultiAgentWorkflow:
    """Get workflow instance for business type"""
    if business_type not in workflows:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported business type: {business_type}"
        )
    return workflows[business_type]


@app.get("/")
async def root():
    """Root endpoint with platform information"""
    return {
        "message": "Multi-Agent Customer Service Platform",
        "version": "1.0.0",
        "supported_business_types": [bt.value for bt in BusinessType],
        "features": [
            "Intent Classification",
            "Product Discovery & Details",
            "Process Guidance",
            "Multi-turn Conversations",
            "Business-specific Workflows"
        ]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "active_workflows": len(workflows),
        "business_types": list(workflows.keys())
    }


@app.post("/api/chat/message", response_model=ChatResponse)
async def process_chat_message(chat_request: ChatRequest):
    """Process a single chat message through the multi-agent system"""
    
    try:
        # Get appropriate workflow
        workflow = get_workflow(chat_request.business_type.value)
        
        # Process the message
        response = await workflow.process_message(chat_request)
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing message: {str(e)}"
        )


@app.get("/api/chat/history/{session_id}")
async def get_conversation_history(
    session_id: str,
    business_type: str = "generic"
):
    """Get conversation history for a session"""
    
    try:
        workflow = get_workflow(business_type)
        history = await workflow.get_conversation_history(session_id)
        
        return {
            "session_id": session_id,
            "message_count": len(history),
            "history": [msg.dict() for msg in history]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving history: {str(e)}"
        )


@app.delete("/api/chat/history/{session_id}")
async def clear_conversation_history(
    session_id: str,
    business_type: str = "generic"
):
    """Clear conversation history for a session"""
    
    try:
        workflow = get_workflow(business_type)
        success = await workflow.clear_conversation(session_id)
        
        return {
            "session_id": session_id,
            "cleared": success
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing history: {str(e)}"
        )


@app.websocket("/api/chat/ws/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time chat"""
    
    await manager.connect(websocket, session_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Extract business type and message
            business_type = message_data.get("business_type", "generic")
            user_message = message_data.get("message", "")
            context = message_data.get("context", {})
            
            if not user_message:
                await manager.send_message(session_id, {
                    "error": "Message is required"
                })
                continue
            
            # Create chat request
            chat_request = ChatRequest(
                message=user_message,
                session_id=session_id,
                business_type=BusinessType(business_type),
                context=context
            )
            
            try:
                # Get workflow and process message
                workflow = get_workflow(business_type)
                response = await workflow.process_message(chat_request)
                
                # Send response back to client
                await manager.send_message(session_id, response.dict())
                
            except Exception as e:
                await manager.send_message(session_id, {
                    "error": f"Processing error: {str(e)}",
                    "session_id": session_id
                })
    
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print(f"WebSocket error for session {session_id}: {e}")
        manager.disconnect(session_id)


@app.get("/api/business-types")
async def get_business_types():
    """Get available business types and their configurations"""
    
    business_configs = {}
    
    for business_type in BusinessType:
        from app.core.config import BusinessConfig
        config = BusinessConfig(business_type)
        
        business_configs[business_type.value] = {
            "name": business_type.value.replace("_", " ").title(),
            "conversation_types": [ct.value for ct in config.config["conversation_types"]],
            "product_fields": config.config.get("product_fields", []),
            "process_stages": config.config.get("process_stages", []),
            "quick_replies": config.config.get("quick_replies", {})
        }
    
    return business_configs


@app.get("/api/demo/widget")
async def get_demo_widget():
    """Get a demo chat widget for testing"""
    
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Multi-Agent Customer Service Demo</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 20px; background-color: #f5f7fa; }
        .demo-header { text-align: center; margin-bottom: 30px; }
        .demo-header h1 { color: #2c3e50; margin-bottom: 10px; }
        .demo-header p { color: #7f8c8d; font-size: 16px; }
        .chat-container { 
            max-width: 800px; 
            margin: 0 auto; 
            background: white;
            border-radius: 15px; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            padding: 25px; 
        }
        .business-selector { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px; 
        }
        .business-selector label { font-weight: bold; display: block; margin-bottom: 10px; }
        select { 
            padding: 12px 15px; 
            border-radius: 8px; 
            border: none; 
            font-size: 14px;
            width: 200px;
            margin-right: 15px;
        }
        .business-info {
            background: rgba(255,255,255,0.2);
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
            font-size: 14px;
        }
        .example-queries {
            margin-top: 10px;
        }
        .example-query {
            background: rgba(255,255,255,0.3);
            padding: 8px 12px;
            margin: 5px 5px 5px 0;
            border-radius: 20px;
            display: inline-block;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.3s ease;
        }
        .example-query:hover {
            background: rgba(255,255,255,0.5);
            transform: translateY(-1px);
        }
        .messages { 
            height: 450px; 
            overflow-y: auto; 
            border: 1px solid #e9ecef; 
            padding: 15px; 
            margin-bottom: 15px; 
            border-radius: 10px;
            background: #fafbfc;
        }
        .message { 
            margin: 15px 0; 
            padding: 12px 15px; 
            border-radius: 12px; 
            max-width: 80%;
        }
        .user-message { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; 
            margin-left: auto;
            text-align: right; 
        }
        .assistant-message { 
            background: white;
            border: 1px solid #e9ecef;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
        .input-container { 
            display: flex; 
            gap: 12px;
            align-items: center;
        }
        input[type="text"] { 
            flex: 1; 
            padding: 15px; 
            border: 2px solid #e9ecef; 
            border-radius: 10px; 
            font-size: 14px;
            transition: border-color 0.3s ease;
        }
        input[type="text"]:focus {
            outline: none;
            border-color: #667eea;
        }
        .send-btn { 
            padding: 15px 25px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; 
            border: none; 
            border-radius: 10px; 
            cursor: pointer; 
            font-weight: bold;
            transition: transform 0.2s ease;
        }
        .send-btn:hover {
            transform: translateY(-1px);
        }
        .quick-replies { 
            margin: 15px 0; 
            padding: 10px 0;
        }
        .quick-reply-btn { 
            background: #f8f9fa;
            color: #495057; 
            border: 1px solid #dee2e6; 
            padding: 8px 15px; 
            margin: 3px; 
            border-radius: 20px; 
            cursor: pointer; 
            font-size: 13px; 
            transition: all 0.3s ease;
        }
        .quick-reply-btn:hover {
            background: #e9ecef;
            transform: translateY(-1px);
        }
        .typing-indicator {
            display: none;
            color: #7f8c8d;
            font-style: italic;
            padding: 10px 15px;
        }
        .stats {
            display: flex;
            justify-content: space-between;
            margin-top: 15px;
            font-size: 12px;
            color: #7f8c8d;
        }
        .carousel {
            display: flex;
            gap: 15px;
            overflow-x: auto;
            padding: 15px 0;
            margin: 10px 0;
        }
        .carousel-item {
            min-width: 280px;
            max-width: 300px;
            background: white;
            border: 1px solid #e9ecef;
            border-radius: 12px;
            padding: 15px;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
            transition: transform 0.2s ease;
        }
        .carousel-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.15);
        }
        .product-image {
            width: 100%;
            height: 150px;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 12px;
            font-size: 24px;
        }
        .product-name {
            font-weight: bold;
            margin-bottom: 8px;
            color: #2c3e50;
            font-size: 14px;
            line-height: 1.3;
        }
        .product-price {
            font-size: 18px;
            font-weight: bold;
            color: #e74c3c;
            margin-bottom: 8px;
        }
        .product-description {
            font-size: 12px;
            color: #7f8c8d;
            margin-bottom: 10px;
            line-height: 1.4;
        }
        .product-specs {
            font-size: 11px;
            color: #95a5a6;
            margin-bottom: 12px;
        }
        .product-actions {
            display: flex;
            gap: 8px;
        }
        .product-btn {
            flex: 1;
            padding: 8px 12px;
            border: 1px solid #667eea;
            background: white;
            color: #667eea;
            border-radius: 6px;
            cursor: pointer;
            font-size: 11px;
            transition: all 0.2s ease;
        }
        .product-btn.primary {
            background: #667eea;
            color: white;
        }
        .product-btn:hover {
            background: #667eea;
            color: white;
        }
    </style>
</head>
<body>
    <div class="demo-header">
        <h1>🤖 Universal Multi-Agent Customer Service</h1>
        <p>Intelligent AI that adapts to any business domain in real-time</p>
    </div>
    
    <div class="chat-container">
        <div class="business-selector">
            <label>🏢 Select Business Type to See AI Adaptation:</label>
            <select id="businessType" onchange="switchBusinessType()">
                <option value="ecommerce">🛒 E-commerce Store</option>
                <option value="hotel">🏨 Hotel & Resort</option>
                <option value="real_estate">🏠 Real Estate Agency</option>
                <option value="rental">🚗 Rental Services</option>
                <option value="generic">💼 Generic Business</option>
            </select>
            
            <div class="business-info" id="businessInfo">
                <strong>E-commerce Capabilities:</strong> Product search, comparisons, cart management, order tracking, customer support
            </div>
            
            <div class="example-queries">
                <strong>Try these examples:</strong><br>
                <div id="exampleQueries">
                    <span class="example-query" onclick="sendMessage('Show me laptops under $1000')">Show me laptops under $1000</span>
                    <span class="example-query" onclick="sendMessage('Show me red laptops')">Show me red laptops</span>
                    <span class="example-query" onclick="sendMessage('Compare iPhone vs Samsung Galaxy')">Compare iPhone vs Samsung Galaxy</span>
                    <span class="example-query" onclick="sendMessage('How do I track my order?')">How do I track my order?</span>
                    <span class="example-query" onclick="sendMessage('Tell me about your return policy')">Tell me about your return policy</span>
                </div>
            </div>
        </div>
        
        <div id="messages" class="messages"></div>
        <div class="typing-indicator" id="typingIndicator">🤖 AI is thinking...</div>
        
        <div id="quickReplies" class="quick-replies"></div>
        
        <div class="input-container">
            <input type="text" id="messageInput" placeholder="Type your message or try the examples above..." />
            <button class="send-btn" onclick="sendMessage()">Send</button>
        </div>
        
        <div class="stats">
            <span>Session: <span id="sessionId"></span></span>
            <span>Messages: <span id="messageCount">0</span></span>
            <span>Business: <span id="currentBusiness">E-commerce</span></span>
        </div>
    </div>

<script>
    const sessionId = 'demo-' + Math.random().toString(36).substr(2, 9);
    const messagesDiv = document.getElementById('messages');
    const messageInput = document.getElementById('messageInput');
    const quickRepliesDiv = document.getElementById('quickReplies');
    const typingIndicator = document.getElementById('typingIndicator');
    let messageCount = 0;
    
    document.getElementById('sessionId').textContent = sessionId;
    
    const businessConfig = {
        ecommerce: {
            name: 'E-commerce',
            description: 'Product search, comparisons, cart management, order tracking, customer support',
            examples: [
                'Show me laptops under $1000',
                'Show me red laptops',
                'Compare iPhone vs Samsung Galaxy',
                'How do I track my order?',
                'Tell me about your return policy'
            ]
        },
        hotel: {
            name: 'Hotel & Resort',
            description: 'Room availability, booking assistance, amenity information, guest services',
            examples: [
                'Check room availability for next weekend',
                'Tell me about your spa services',
                'How do I cancel my reservation?',
                'What amenities do you offer?'
            ]
        },
        real_estate: {
            name: 'Real Estate',
            description: 'Property search, viewing scheduling, market information, process guidance',
            examples: [
                'Show me 3-bedroom houses under $500K',
                'Schedule a property viewing',
                'What are current market trends?',
                'How does the buying process work?'
            ]
        },
        rental: {
            name: 'Rental Services',
            description: 'Equipment availability, reservation management, pricing information, logistics',
            examples: [
                'Rent a car for the weekend',
                'What construction tools do you have?',
                'How much does delivery cost?',
                'Check availability of party equipment'
            ]
        },
        generic: {
            name: 'Generic Business',
            description: 'General customer service, information, and assistance',
            examples: [
                'Tell me about your company',
                'What services do you offer?',
                'How can I contact you?',
                'What are your business hours?'
            ]
        }
    };
    
    function switchBusinessType() {
        const businessType = document.getElementById('businessType').value;
        const config = businessConfig[businessType];
        
        document.getElementById('businessInfo').innerHTML = 
            `<strong>${config.name} Capabilities:</strong> ${config.description}`;
        
        const exampleQueriesDiv = document.getElementById('exampleQueries');
        exampleQueriesDiv.innerHTML = '<strong>Try these examples:</strong><br>' +
            config.examples.map(example => 
                `<span class="example-query" onclick="sendMessage('${example}')">${example}</span>`
            ).join('');
        
        document.getElementById('currentBusiness').textContent = config.name;
        
        // Clear conversation when switching business types
        messagesDiv.innerHTML = '';
        messageCount = 0;
        document.getElementById('messageCount').textContent = messageCount;
        
        // Add new greeting
        setTimeout(() => {
            addMessage(`Hello! I'm your AI assistant for ${config.name.toLowerCase()}. How can I help you today?`, 'assistant');
            showQuickReplies(['Tell me about your business', 'Browse products/services', 'Get help']);
        }, 500);
    }
    
    async function sendMessage(message = null) {
        const text = message || messageInput.value.trim();
        if (!text) return;
        
        // Add user message to chat
        addMessage(text, 'user');
        messageInput.value = '';
        
        // Show typing indicator
        typingIndicator.style.display = 'block';
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
        
        // Send to API
        try {
            const response = await fetch('/api/chat/message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: text,
                    session_id: sessionId,
                    business_type: document.getElementById('businessType').value,
                    context: {}
                })
            });
            
            const data = await response.json();
            
            // Hide typing indicator
            typingIndicator.style.display = 'none';
            
            // Simulate AI thinking delay for better UX
            setTimeout(() => {
                // Add assistant response with proper formatting
                addAssistantMessage(data);
                
                // Show quick replies
                showQuickReplies(data.quick_replies || []);
            }, 800);
            
        } catch (error) {
            typingIndicator.style.display = 'none';
            addMessage('Sorry, there was an error processing your message. Please try again.', 'assistant');
        }
    }
    
    function addMessage(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        messageDiv.textContent = text;
        messagesDiv.appendChild(messageDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
        
        messageCount++;
        document.getElementById('messageCount').textContent = messageCount;
    }
    
    function addAssistantMessage(response) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant-message';
        
        // Add text message
        if (response.message) {
            const textDiv = document.createElement('div');
            textDiv.textContent = response.message;
            messageDiv.appendChild(textDiv);
        }
        
        // Add carousel if present
        if (response.response_format === 'carousel' && response.carousel_items && response.carousel_items.length > 0) {
            const carouselDiv = document.createElement('div');
            carouselDiv.className = 'carousel';
            
            response.carousel_items.forEach(item => {
                const itemDiv = document.createElement('div');
                itemDiv.className = 'carousel-item';
                
                // Product image placeholder
                const imageDiv = document.createElement('div');
                imageDiv.className = 'product-image';
                imageDiv.textContent = '🖥️'; // Laptop emoji
                itemDiv.appendChild(imageDiv);
                
                // Product name
                const nameDiv = document.createElement('div');
                nameDiv.className = 'product-name';
                nameDiv.textContent = item.name;
                itemDiv.appendChild(nameDiv);
                
                // Product price
                const priceDiv = document.createElement('div');
                priceDiv.className = 'product-price';
                priceDiv.textContent = `$${item.price}`;
                itemDiv.appendChild(priceDiv);
                
                // Product description
                const descDiv = document.createElement('div');
                descDiv.className = 'product-description';
                descDiv.textContent = item.description.length > 100 ? 
                    item.description.substring(0, 100) + '...' : item.description;
                itemDiv.appendChild(descDiv);
                
                // Product specs
                if (item.metadata) {
                    const specsDiv = document.createElement('div');
                    specsDiv.className = 'product-specs';
                    const specs = [];
                    if (item.metadata.color) specs.push(`Color: ${item.metadata.color}`);
                    if (item.metadata.brand) specs.push(`Brand: ${item.metadata.brand}`);
                    if (item.metadata.processor) specs.push(`CPU: ${item.metadata.processor}`);
                    if (item.metadata.ram) specs.push(`RAM: ${item.metadata.ram}`);
                    specsDiv.textContent = specs.join(' • ');
                    itemDiv.appendChild(specsDiv);
                }
                
                // Action buttons
                const actionsDiv = document.createElement('div');
                actionsDiv.className = 'product-actions';
                
                const detailsBtn = document.createElement('button');
                detailsBtn.className = 'product-btn';
                detailsBtn.textContent = 'Details';
                detailsBtn.onclick = () => sendMessage(`Tell me more about ${item.name}`);
                actionsDiv.appendChild(detailsBtn);
                
                const addBtn = document.createElement('button');
                addBtn.className = 'product-btn primary';
                addBtn.textContent = 'Add to Cart';
                addBtn.onclick = () => sendMessage(`Add ${item.name} to cart`);
                actionsDiv.appendChild(addBtn);
                
                itemDiv.appendChild(actionsDiv);
                carouselDiv.appendChild(itemDiv);
            });
            
            messageDiv.appendChild(carouselDiv);
        }
        
        messagesDiv.appendChild(messageDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
        
        messageCount++;
        document.getElementById('messageCount').textContent = messageCount;
    }
    
    function showQuickReplies(replies) {
        quickRepliesDiv.innerHTML = '';
        replies.forEach(reply => {
            const btn = document.createElement('button');
            btn.className = 'quick-reply-btn';
            btn.textContent = reply;
            btn.onclick = () => sendMessage(reply);
            quickRepliesDiv.appendChild(btn);
        });
    }
    
    // Send message on Enter
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
    
    // Initialize
    switchBusinessType();
</script>
</body>
</html>
    """
    
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    ) 