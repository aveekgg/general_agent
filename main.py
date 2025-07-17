#!/usr/bin/env python3
"""
Multi-Agent Customer Service Platform
Main application entry point
"""

import os
import sys
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

# Import and run the FastAPI application
if __name__ == "__main__":
    import uvicorn
    from app.api.main import app
    from app.core.config import settings
    
    from app.core.config import BusinessType
    
    print("🚀 Starting Multi-Agent Customer Service Platform")
    print(f"📋 Business Types Supported: {', '.join([bt.value for bt in BusinessType])}")
    print(f"🌐 Server: http://{settings.api_host}:{settings.api_port}")
    print(f"📖 API Docs: http://{settings.api_host}:{settings.api_port}/docs")
    print(f"🎮 Interactive Demo: http://{settings.api_host}:{settings.api_port}/api/demo/widget (try switching business types!)")
    
    uvicorn.run(
        "app.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning"
    ) 