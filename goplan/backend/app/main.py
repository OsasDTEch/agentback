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
    thread_id = str(uuid.uuid4())

    initial_state = {
        'thread_id': thread_id,
        "user_input": user_input,
        "messages": [],
        "travel_details": {},
        "preferred_airlines": [],
        "hotel_amenities": [],
        "budget_level": "medium",
        "flight_results": "",
        "hotel_results": "",
        "activity_results": "",
        "final_plan": "",
        "errors": []
    }

    config = {"configurable": {"thread_id": thread_id}}
    
    final_plan = "No travel plan could be generated."
    
    try:
        async for event in travel_agent_graph.astream(initial_state, config=config, stream_mode="updates"):
            for node_name, update in event.items():
                logger.info(f"Request {request_id}: {node_name} update")

                if update.get("interrupt"):
                    active_requests[request_id]["status"] = "waiting_for_user"
                    # Note: We can't pickle the state directly for storage, so this is a simplified example
                    active_requests[request_id]["interrupted_state"] = update["current_state"]
                    active_requests[request_id]["interrupt_question"] = update.get("question", "Need more details")
                    return {
                        "interrupt": True,
                        "question": update.get("question")
                    }

                if node_name == "create_final_plan" and "final_plan" in update:
                    final_plan = update["final_plan"]
                    # If final plan is generated, break the stream and return
                    return final_plan

    except Exception as e:
        logger.error(f"Streaming failed for {request_id}, fallback triggered: {e}")
        # ⚠️ The fix: Correctly unpack the tuple from the fallback function
        final_plan_str, errors = await run_travel_agent_simple(user_input)
        return final_plan_str
    
    return final_plan


# Resume logic after interrupt
@app.post("/resume-trip")
async def resume_trip(request: ResumeTripRequest):
    request_id = request.request_id

    if request_id not in active_requests:
        raise HTTPException(status_code=404, detail="Request not found")

    state = active_requests[request_id].get("interrupted_state")
    if not state:
        raise HTTPException(status_code=400, detail="No interrupted state available")

    state["user_input"] = request.user_input
    config = {"configurable": {"thread_id": state["thread_id"]}}

    final_plan_str = None
    
    try:
        async for event in travel_agent_graph.astream(state, config=config, stream_mode="updates"):
            for node_name, update in event.items():
                logger.info(f"Resuming Request {request_id}: {node_name} update")

                if update.get("interrupt"):
                    active_requests[request_id]["status"] = "waiting_for_user"
                    active_requests[request_id]["interrupted_state"] = update["current_state"]
                    active_requests[request_id]["interrupt_question"] = update.get("question", "Need more details")
                    return {
                        "status": "waiting_for_user",
                        "question": update.get("question"),
                        "request_id": request_id
                    }

                if node_name == "create_final_plan" and "final_plan" in update:
                    final_plan_str = update["final_plan"]
                    active_requests.pop(request_id, None)
                    return {
                        "status": "complete",
                        "request_id": request_id,
                        "final_plan": final_plan_str
                    }

    except Exception as e:
        logger.error(f"Error resuming travel request {request_id}: {str(e)}")
        # ⚠️ The fix: Correctly unpack the tuple from the fallback function
        final_plan_str, errors = await run_travel_agent_simple(request.user_input)
        return {
            "status": "error",
            "message": str(e),
            "final_plan": final_plan_str,
            "request_id": request_id
        }

    return {
        "status": "incomplete",
        "request_id": request_id
    }

# Status endpoints
@app.get("/request-status/{request_id}")
async def get_request_status(request_id: str):
    if request_id not in active_requests:
        raise HTTPException(status_code=404, detail="Request not found")

    request_info = active_requests[request_id]
    processing_time = (datetime.utcnow() - request_info["start_time"]).total_seconds()

    return {
        "request_id": request_id,
        "status": request_info["status"],
        "user_input": request_info["user_input"],
        "processing_time": processing_time,
        "start_time": request_info["start_time"].isoformat()
    }

@app.get("/active-requests")
async def get_active_requests():
    current_time = datetime.utcnow()
    requests_info = []

    for req_id, req_info in active_requests.items():
        processing_time = (current_time - req_info["start_time"]).total_seconds()
        requests_info.append({
            "request_id": req_id,
            "status": req_info["status"],
            "processing_time": processing_time,
            "user_input": req_info["user_input"][:100] + "..." if len(req_info["user_input"]) > 100 else req_info["user_input"]
        })

    return {
        "total_active": len(active_requests),
        "requests": requests_info
    }

@app.post("/cancel-request/{request_id}")
async def cancel_request(request_id: str):
    if request_id not in active_requests:
        raise HTTPException(status_code=404, detail="Request not found")

    request_info = active_requests.pop(request_id)
    processing_time = (datetime.utcnow() - request_info["start_time"]).total_seconds()

    return {
        "message": "Request cancelled successfully",
        "request_id": request_id,
        "processing_time": processing_time
    }

@app.on_event("startup")
async def startup_event():
    logger.info("Goplan Travel Agent API starting up...")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Goplan Travel Agent API shutting down...")
    active_requests.clear()
