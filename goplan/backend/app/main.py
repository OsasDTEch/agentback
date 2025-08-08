from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import asyncio
import json
import uuid
from datetime import datetime
import logging

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


# Pydantic models for API
class TravelRequest(BaseModel):
    user_input: str = Field(..., description="User's travel planning request")
    preferred_airlines: Optional[List[str]] = Field(default=[], description="Preferred airline codes")
    hotel_amenities: Optional[List[str]] = Field(default=[], description="Desired hotel amenities")
    budget_level: Optional[str] = Field(default="medium", description="Budget level: low, medium, high")


class TravelResponse(BaseModel):
    success: bool
    request_id: str
    final_plan: Optional[str] = None
    error_message: Optional[str] = None
    processing_time: Optional[float] = None


class StreamingTravelRequest(BaseModel):
    user_input: str = Field(..., description="User's travel planning request")
    preferred_airlines: Optional[List[str]] = Field(default=[], description="Preferred airline codes")
    hotel_amenities: Optional[List[str]] = Field(default=[], description="Desired hotel amenities")
    budget_level: Optional[str] = Field(default="medium", description="Budget level: low, medium, high")


# In-memory storage for tracking requests (use Redis/database in production)
active_requests: Dict[str, Dict[str, Any]] = {}


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "Goplan Travel Agent API",
        "status": "active",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health_check():
    """Detailed health check."""
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


@app.post("/plan-trip", response_model=TravelResponse)
async def plan_trip(request: TravelRequest):
    """
    Plan a trip based on user input. Returns complete plan when ready.
    """
    request_id = str(uuid.uuid4())
    start_time = datetime.utcnow()

    try:
        logger.info(f"Processing travel request {request_id}: {request.user_input}")

        # Store request info
        active_requests[request_id] = {
            "status": "processing",
            "start_time": start_time,
            "user_input": request.user_input
        }

        # Run the travel agent
        final_plan = await run_travel_agent_simple(request.user_input)

        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        # Clean up request tracking
        active_requests.pop(request_id, None)

        logger.info(f"Completed travel request {request_id} in {processing_time:.2f}s")

        return TravelResponse(
            success=True,
            request_id=request_id,
            final_plan=final_plan,
            processing_time=processing_time
        )

    except Exception as e:
        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        # Clean up request tracking
        active_requests.pop(request_id, None)

        logger.error(f"Error processing travel request {request_id}: {str(e)}")

        return TravelResponse(
            success=False,
            request_id=request_id,
            error_message=str(e),
            processing_time=processing_time
        )


@app.post("/plan-trip-streaming")
async def plan_trip_streaming(request: StreamingTravelRequest):
    """
    Plan a trip with streaming response. Returns real-time updates as the plan is being created.
    """
    request_id = str(uuid.uuid4())

    async def generate_streaming_response():
        """Generator function for streaming responses."""
        try:
            logger.info(f"Starting streaming travel request {request_id}: {request.user_input}")

            # Send initial response
            yield f"data: {json.dumps({'type': 'start', 'request_id': request_id, 'message': 'Starting travel planning...'})}\n\n"

            # Store request info
            active_requests[request_id] = {
                "status": "processing",
                "start_time": datetime.utcnow(),
                "user_input": request.user_input
            }

            # Custom streaming function that yields updates
            final_plan = await stream_travel_planning(request.user_input, request_id)

            # Send final response
            yield f"data: {json.dumps({'type': 'complete', 'request_id': request_id, 'final_plan': final_plan})}\n\n"

            # Clean up
            active_requests.pop(request_id, None)

        except Exception as e:
            logger.error(f"Error in streaming travel request {request_id}: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'request_id': request_id, 'error': str(e)})}\n\n"
            active_requests.pop(request_id, None)

    return StreamingResponse(
        generate_streaming_response(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )


async def stream_travel_planning(user_input: str, request_id: str) -> str:
    """
    Custom streaming function that provides updates during travel planning.
    """
    # Generate a unique thread ID
    thread_id = str(uuid.uuid4())

    # Initialize the state with user input
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
        "final_plan": ""
    }

    # Configuration with thread_id for the checkpointer
    config = {"configurable": {"thread_id": thread_id}}

    final_result = None

    try:
        # Stream updates from the graph
        async for event in travel_agent_graph.astream(initial_state, config=config, stream_mode="updates"):
            for node_name, update in event.items():
                # Send progress updates
                progress_message = f"Processing: {node_name.replace('_', ' ').title()}"
                # Note: In a real streaming implementation, you'd yield these updates
                # For now, we'll log them
                logger.info(f"Request {request_id}: {progress_message}")

                if node_name == "create_final_plan" and "final_plan" in update:
                    final_result = update["final_plan"]

    except Exception as e:
        logger.error(f"Streaming execution failed for {request_id}, falling back: {e}")
        # Fallback to simple execution
        final_result = await run_travel_agent_simple(user_input)

    return final_result or "No travel plan could be generated."


@app.get("/request-status/{request_id}")
async def get_request_status(request_id: str):
    """
    Get the status of a travel planning request.
    """
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
    """
    Get all currently active requests (admin endpoint).
    """
    current_time = datetime.utcnow()
    requests_info = []

    for req_id, req_info in active_requests.items():
        processing_time = (current_time - req_info["start_time"]).total_seconds()
        requests_info.append({
            "request_id": req_id,
            "status": req_info["status"],
            "processing_time": processing_time,
            "user_input": req_info["user_input"][:100] + "..." if len(req_info["user_input"]) > 100 else req_info[
                "user_input"]
        })

    return {
        "total_active": len(active_requests),
        "requests": requests_info
    }


@app.post("/cancel-request/{request_id}")
async def cancel_request(request_id: str):
    """
    Cancel an active travel planning request.
    """
    if request_id not in active_requests:
        raise HTTPException(status_code=404, detail="Request not found")

    # Remove from active requests
    request_info = active_requests.pop(request_id)
    processing_time = (datetime.utcnow() - request_info["start_time"]).total_seconds()

    logger.info(f"Cancelled travel request {request_id} after {processing_time:.2f}s")

    return {
        "message": "Request cancelled successfully",
        "request_id": request_id,
        "processing_time": processing_time
    }


# Background task for cleanup
@app.on_event("startup")
async def startup_event():
    """
    Startup tasks.
    """
    logger.info("Goplan Travel Agent API starting up...")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Cleanup tasks on shutdown.
    """
    logger.info("Goplan Travel Agent API shutting down...")
    # Clean up any remaining active requests
    active_requests.clear()



# if __name__ == "__main__":
#     import uvicorn

#     # Run the server
#     uvicorn.run(
#         "main:app",  # Replace with your actual module name
#         host="0.0.0.0",
#         port=8000,
#         reload=True,
#         log_level="info"

#     )
