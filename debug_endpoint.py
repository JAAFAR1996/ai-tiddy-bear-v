"""
Quick debug endpoint to check app.state
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

def add_debug_endpoint(app: FastAPI):
    """Add debug endpoint to check app.state"""
    
    @app.get("/debug/app-state")
    async def debug_app_state(request: Request):
        """Debug endpoint to check app.state values"""
        try:
            state_info = {
                "config": getattr(request.app.state, "config", None) is not None,
                "config_ready": getattr(request.app.state, "config_ready", None),
                "ready": getattr(request.app.state, "ready", None),
                "available_attrs": [attr for attr in dir(request.app.state) if not attr.startswith('_')]
            }
            
            if hasattr(request.app.state, 'config') and request.app.state.config:
                try:
                    state_info["config_env"] = getattr(request.app.state.config, 'ENVIRONMENT', 'unknown')
                except:
                    state_info["config_env"] = "error_reading_env"
            
            return JSONResponse(content=state_info)
            
        except Exception as e:
            return JSONResponse(
                content={"error": str(e), "type": type(e).__name__}, 
                status_code=500
            )