# Multi-Agent Customer Service Platform

A universal, plug-and-play multi-agent AI system that adapts to any business domain for intelligent customer service conversations. Whether you're running a Shopify store, hotel booking platform, real estate agency, or rental service, this system instantly adapts to your business domain.

## 🚀 Features

- **Universal Business Support**: Works with e-commerce, hotels, real estate, rentals, and generic businesses
- **Intent Classification**: Automatically classifies user intents and extracts entities
- **Multi-Agent Architecture**: Specialized agents for different conversation types
- **Real-time Chat**: WebSocket support for live conversations
- **Product Discovery**: Intelligent product search and recommendations
- **Process Guidance**: Step-by-step assistance for business processes
- **Context Awareness**: Maintains conversation context across interactions
- **Dynamic UI**: Interactive demo widget with carousels and quick replies

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   Frontend UI   │────│   FastAPI Server │────│   LangGraph Engine  │
│                 │    │                  │    │                     │
│ • Chat Interface│    │ • WebSocket      │    │ • Orchestrator      │
│ • Carousels     │    │ • REST APIs      │    │ • Specialized Agents│
│ • Quick Replies │    │ • CORS Support   │    │ • GPT-4 Powered     │
│ • Dynamic Forms │    │ • Session Mgmt   │    │ • MemorySaver       │
│ • Demo Widget   │    │ • Error Handling │    │ • State Management  │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
```

## 📋 Requirements

- Python 3.9+
- OpenAI API Key
- pip (Python package manager)

## 🛠️ Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/multi-agent-customer-service.git
cd multi-agent-customer-service
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

Create a `.env` file in the root directory:

```bash
cp .env.example .env  # If .env.example exists
```

Add your OpenAI API key to `.env`:

```env
OPENAI_API_KEY=sk-your-openai-api-key-here
```

### 5. Seed Database (Optional)

For demo purposes, seed the database with sample products:

```bash
python seed_database.py
```

### 6. Run the Application

```bash
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 7. Access the Demo

Open your browser and navigate to:
- **Demo Widget**: http://localhost:8000/api/demo/widget
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 🎯 Supported Business Types

### E-commerce
- Product search and discovery
- Product comparisons
- Order tracking
- Shopping cart management
- Customer support

### Hotel & Resort
- Room availability checking
- Booking assistance
- Amenity information
- Guest services
- Reservation management

### Real Estate
- Property search and filtering
- Viewing scheduling
- Market information
- Process guidance
- Agent contact

### Rental Services
- Equipment availability
- Reservation management
- Pricing information
- Delivery coordination
- Return processes

### Generic Business
- General customer service
- Information requests
- Process guidance
- Contact assistance

## 🔌 API Endpoints

### Chat Endpoints
- `POST /api/chat/message` - Process a chat message
- `GET /api/chat/history/{session_id}` - Get conversation history
- `DELETE /api/chat/history/{session_id}` - Clear conversation history
- `WS /api/chat/ws/{session_id}` - WebSocket for real-time chat

### Configuration Endpoints
- `GET /api/business-types` - List supported business types
- `GET /health` - Health check
- `GET /` - Platform information

## 💬 Usage Examples

### Basic Chat Request

```python
import requests

response = requests.post("http://localhost:8000/api/chat/message", json={
    "message": "Show me laptops under $1000",
    "session_id": "user123",
    "business_type": "ecommerce",
    "context": {}
})

print(response.json())
```

### WebSocket Chat

```javascript
const ws = new WebSocket('ws://localhost:8000/api/chat/ws/user123');

ws.onopen = () => {
    ws.send(JSON.stringify({
        business_type: 'ecommerce',
        message: 'Show me red laptops',
        context: {}
    }));
};

ws.onmessage = (event) => {
    const response = JSON.parse(event.data);
    console.log(response);
};
```

## 🏛️ Project Structure

```
multi-agent-customer-service/
├── app/
│   ├── agents/                 # AI agents
│   │   ├── orchestrator.py    # Main orchestrator
│   │   ├── product_discovery_agent.py
│   │   ├── product_detail_agent.py
│   │   └── clarification_agent.py
│   ├── api/                   # FastAPI endpoints
│   │   └── main.py
│   ├── core/                  # Configuration
│   │   └── config.py
│   ├── models/                # Data models
│   │   ├── database.py
│   │   └── schemas.py
│   ├── repositories/          # Data access
│   │   ├── factory.py
│   │   └── sqlite_repository.py
│   └── data/                  # Sample data
│       └── seeds/
├── venv/                      # Virtual environment
├── requirements.txt           # Python dependencies
├── seed_database.py          # Database seeding script
├── ARCHITECTURE.md           # Detailed architecture
└── README.md                 # This file
```

## 🔧 Configuration

### Business Type Configuration

The system automatically adapts based on the business type:

```python
# E-commerce configuration
{
    "product_fields": ["name", "price", "description", "category", "in_stock"],
    "search_fields": ["category", "brand", "price_range", "rating"],
    "process_stages": ["cart", "checkout", "payment", "shipping", "delivery"]
}

# Hotel configuration
{
    "product_fields": ["room_type", "price_per_night", "amenities", "availability"],
    "search_fields": ["check_in", "check_out", "guests", "location", "amenities"],
    "process_stages": ["search", "booking", "payment", "confirmation", "check_in"]
}
```

### Adding Custom Business Types

1. Add new business type to `BusinessType` enum in `app/core/config.py`
2. Create business-specific configuration in `BusinessConfig._get_business_config()`
3. Add sample data for the new business type
4. Test with the demo widget

## 🧪 Testing

### Manual Testing
1. Start the server: `uvicorn app.api.main:app --reload`
2. Open the demo widget: http://localhost:8000/api/demo/widget
3. Try different business types and conversation flows

### API Testing
```bash
# Test health endpoint
curl http://localhost:8000/health

# Test chat endpoint
curl -X POST http://localhost:8000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me laptops",
    "session_id": "test123",
    "business_type": "ecommerce"
  }'
```

## 🚀 Deployment

### Local Development
```bash
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Deployment
```bash
# Using Gunicorn
pip install gunicorn
gunicorn app.api.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Using Docker (if Dockerfile exists)
docker build -t multi-agent-customer-service .
docker run -p 8000:8000 multi-agent-customer-service
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Add tests if applicable
5. Commit your changes: `git commit -am 'Add feature'`
6. Push to the branch: `git push origin feature-name`
7. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: Create an issue on GitHub
- **Documentation**: See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture
- **API Docs**: Visit http://localhost:8000/docs when running the server

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Powered by [OpenAI GPT-4](https://openai.com/)
- Uses [LangGraph](https://github.com/langchain-ai/langgraph) for workflow orchestration
- Demo UI built with vanilla JavaScript and CSS

---

**Status**: ✅ Production Ready

This system has been successfully implemented and deployed for various business domains. The plug-and-play architecture allows instant adaptation to any business type selling products or services. 