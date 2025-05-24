import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Set
import uuid

import aio_pika
from aio_pika import Message, connect_robust
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RabbitMQ Chat Server", version="1.0.0")

# Pydantic models
class ChatMessage(BaseModel):
    user_id: str
    message: str
    room: str = "general"
    timestamp: str = None

class SendMessageRequest(BaseModel):
    user_id: str
    message: str
    room: str = "general"

# Global variables
rabbitmq_connection = None
rabbitmq_channel = None
active_websockets: Dict[str, WebSocket] = {}
user_rooms: Dict[str, str] = {}  # websocket_id -> room

# RabbitMQ configuration
RABBITMQ_URL = "amqp://guest:guest@localhost:5672/"
CHAT_EXCHANGE = "chat_exchange"

async def setup_rabbitmq():
    """Initialize RabbitMQ connection and setup exchanges/queues"""
    global rabbitmq_connection, rabbitmq_channel
    
    try:
        # Create robust connection (auto-reconnect)
        rabbitmq_connection = await connect_robust(RABBITMQ_URL)
        rabbitmq_channel = await rabbitmq_connection.channel()
        
        # Declare exchange for chat messages
        await rabbitmq_channel.declare_exchange(
            CHAT_EXCHANGE, 
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        
        logger.info("RabbitMQ connection established successfully")
        
    except Exception as e:
        logger.error(f"Failed to connect to RabbitMQ: {e}")
        raise

async def close_rabbitmq():
    """Close RabbitMQ connection"""
    global rabbitmq_connection
    if rabbitmq_connection and not rabbitmq_connection.is_closed:
        await rabbitmq_connection.close()
        logger.info("RabbitMQ connection closed")

@app.on_event("startup")
async def startup_event():
    """Initialize RabbitMQ on startup"""
    await setup_rabbitmq()

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    await close_rabbitmq()

async def publish_message(message: ChatMessage):
    """Publish message to RabbitMQ exchange"""
    try:
        if not message.timestamp:
            message.timestamp = datetime.now().isoformat()
            
        message_body = message.model_dump_json()
        routing_key = f"chat.{message.room}"
        
        await rabbitmq_channel.default_exchange.publish(
            Message(
                message_body.encode(),
                headers={"room": message.room, "user_id": message.user_id}
            ),
            # routing_key=f"chat_queue_{message.room}"
            routing_key=routing_key
        )
        
        logger.info(f"Published message to room {message.room} from user {message.user_id}")
        
    except Exception as e:
        logger.error(f"Error publishing message: {e}")
        raise

async def setup_message_consumer(room: str, websocket_id: str):
    """Set up message consumer for a specific room"""
    try:
        # Declare queue for the room
        queue_name = f"chat_queue_{room}"
        queue = await rabbitmq_channel.declare_queue(
            queue_name, 
            durable=True,
            auto_delete=False
        )
        
        # Bind queue to exchange
        await queue.bind(CHAT_EXCHANGE, routing_key=f"chat.{room}")
        
        async def message_handler(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    print(f"Received message in rabbitmq: ${message.body.decode()}")
                    logger.info(f"Received message in rabbitmq: ${message.body.decode()}")
                    # Parse message
                    message_data = json.loads(message.body.decode())
                    
                    # Send to WebSocket if connection is still active
                    if websocket_id in active_websockets:
                        websocket = active_websockets[websocket_id]
                        await websocket.send_text(json.dumps(message_data))
                        logger.info(f"Sent message to WebSocket {websocket_id}")
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        
        # Start consuming messages
        await queue.consume(message_handler)
        logger.info(f"Started consuming messages for room {room}")
        
    except Exception as e:
        logger.error(f"Error setting up consumer for room {room}: {e}")
        raise

@app.get("/")
async def root():
    return {"message": "RabbitMQ Chat Server is running"}

@app.post("/send_message")
async def send_message(request: SendMessageRequest):
    """HTTP endpoint to send a chat message"""
    try:
        chat_message = ChatMessage(
            user_id=request.user_id,
            message=request.message,
            room=request.room,
            timestamp=datetime.now().isoformat()
        )
        
        await publish_message(chat_message)
        
        return {
            "status": "success",
            "message": "Message sent successfully",
            "timestamp": chat_message.timestamp
        }
        
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")

@app.websocket("/chat/{user_id}")
async def websocket_chat_endpoint(websocket: WebSocket, user_id: str, room: str = "general"):
    """WebSocket endpoint for real-time chat"""
    websocket_id = str(uuid.uuid4())
    
    await websocket.accept()
    active_websockets[websocket_id] = websocket
    user_rooms[websocket_id] = room
    
    logger.info(f"WebSocket connected: {websocket_id} for user {user_id} in room {room}")
    
    try:
        # Setup message consumer for this room
        await setup_message_consumer(room, websocket_id)
        
        # Send welcome message
        welcome_message = {
            "user_id": "system",
            "message": f"Welcome to room '{room}', {user_id}!",
            "room": room,
            "timestamp": datetime.now().isoformat(),
            "type": "system"
        }
        await websocket.send_text(json.dumps(welcome_message))
        
        # Listen for incoming messages from WebSocket
        while True:
            try:
                # Receive message from WebSocket
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Create chat message
                chat_message = ChatMessage(
                    user_id=user_id,
                    message=message_data.get("message", ""),
                    room=message_data.get("room", room),
                    timestamp=datetime.now().isoformat()
                )
                
                # Publish to RabbitMQ
                await publish_message(chat_message)
                
                # Send acknowledgment
                ack_message = {
                    "type": "ack",
                    "status": "sent",
                    "timestamp": chat_message.timestamp
                }
                await websocket.send_text(json.dumps(ack_message))
                
            except json.JSONDecodeError:
                error_msg = {"type": "error", "message": "Invalid JSON format"}
                await websocket.send_text(json.dumps(error_msg))
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                error_msg = {"type": "error", "message": "Failed to process message"}
                await websocket.send_text(json.dumps(error_msg))
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {websocket_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {websocket_id}: {e}")
    finally:
        # Cleanup
        if websocket_id in active_websockets:
            del active_websockets[websocket_id]
        if websocket_id in user_rooms:
            del user_rooms[websocket_id]
        
        logger.info(f"Cleaned up WebSocket connection: {websocket_id}")

@app.get("/rooms")
async def list_rooms():
    """List active chat rooms"""
    rooms = set(user_rooms.values())
    return {
        "active_rooms": list(rooms),
        "total_connections": len(active_websockets)
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    rabbitmq_status = "connected" if rabbitmq_connection and not rabbitmq_connection.is_closed else "disconnected"
    
    return {
        "status": "healthy",
        "rabbitmq": rabbitmq_status,
        "active_connections": len(active_websockets),
        "timestamp": datetime.now().isoformat()
    }

# For running the server directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)