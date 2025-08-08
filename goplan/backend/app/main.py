from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import asyncio
import json
import uuid
from datetime import datetime
import logging
import logfire
from goplan.backend.app.logging_config import setup_logging
# ⚠️ Pydantic v2 requires from typing_extensions import Annotated for `Annotated`
# but your pydantic_ai.messages may not have it. Added this for completeness.
from typing_extensions import Annotated

setup_logging()
# Import your travel agent components
from goplan.backend.app.agent_graph import (
    travel_agent_graph,
    run_travel_agent_simple,
    run_travel_agent_with_streaming
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Goplan Travel Agent API",
    description="AI-powered travel planning service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class TravelRequest(BaseModel):
    user_input: str
    preferred_airlines: Optional[List[str]] = Field(default=[])
    hotel_amenities: Optional[List[str]] = Field(default=[])
    budget_level: Optional[str] = Field(default="medium")

class TravelResponse(BaseModel):
    success: bool
    request_id: str
    final_plan: Optional[str] = None
    error_message: Optional[str] = None
    processing_time: Optional[float] = None
    # ⚠️ Added an errors field for better client feedback
    errors: Optional[List[str]] = Field(default=None)

class StreamingTravelRequest(BaseModel):
    user_input: str
    preferred_airlines: Optional[List[str]] = Field(default=[])
    hotel_amenities: Optional[List[str]] = Field(default=[])
    budget_level: Optional[str] = Field(default="medium")

class ResumeTripRequest(BaseModel):
    request_id: str
    user_input: str

# In-memory store
active_requests: Dict[str, Dict[str, Any]] = {}

# Health
@logfire.trace
@app.get("/")
async def root():
    logfire.info("Health check hit", extra={"route": "/", "status": "OK"})
    return {
        "message": "Goplan Travel Agent API",
        "status": "active",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_requests": len(active_requests),
        "services": {
            "travel_agent": "operational",
            "flight_search": "operational",
            "hotel_search": "operational",
            "activity_search": "operational"
        }
    }

# Standard trip planning (no streaming)
@app.post("/plan-trip", response_model=TravelResponse)
async def plan_trip(request: TravelRequest):
    request_id = str(uuid.uuid4())
    start_time = datetime.utcnow()

    final_plan_str = None
    errors = []
    
    try:
        logger.info(f"Processing travel request {request_id}: {request.user_input}")
        active_requests[request_id] = {
            "status": "processing",
            "start_time": start_time,
            "user_input": request.user_input
        }

        # ⚠️ The fix: Correctly unpack the tuple returned by run_travel_agent_simple
        final_plan_str, errors = await run_travel_agent_simple(request.user_input)
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        active_requests.pop(request_id, None)

        return TravelResponse(
            success=True,
            request_id=request_id,
            final_plan=final_plan_str, # Use the string variable
            error_message=errors[0] if errors else None,
            processing_time=processing_time,
            errors=errors
        )

    except Exception as e:
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        active_requests.pop(request_id, None)

        return TravelResponse(
            success=False,
            request_id=request_id,
            error_message=str(e),
            processing_time=processing_time,
            errors=[str(e)]
        )

# Streaming planner with interrupt support
@app.post("/plan-trip-streaming")
async def plan_trip_streaming(request: StreamingTravelRequest):
    request_id = str(uuid.uuid4())

    async def generate_streaming_response():
        try:
            logger.info(f"Starting streaming travel request {request_id}: {request.user_input}")
            yield f"data: {json.dumps({'type': 'start', 'request_id': request_id, 'message': 'Starting travel planning...'})}\n\n"

            active_requests[request_id] = {
                "status": "processing",
                "start_time": datetime.utcnow(),
                "user_input": request.user_input
            }

            final_result = await stream_travel_planning(request.user_input, request_id)

            if isinstance(final_result, dict) and final_result.get("interrupt"):
                yield f"data: {json.dumps({'type': 'interrupt', 'request_id': request_id, 'question': final_result['question']})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'complete', 'request_id': request_id, 'final_plan': final_result})}\n\n"

            active_requests.pop(request_id, None)

        except Exception as e:
            logger.error(f"Error in streaming travel request {request_id}: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'request_id': request_id, 'error': str(e)})}\n\n"
            active_requests.pop(request_id, None)

    return StreamingResponse(
        generate_streaming_response(),
        media_type="text/event-stream"
    )

# Streaming logic with interrupt support
async def stream_travel_planning(user_input: str, request_id: str) -> Any:
    thread_id = str(uuid.uuid
