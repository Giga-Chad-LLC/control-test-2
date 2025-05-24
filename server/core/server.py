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
user_rooms: Dict[str, str] = {}  # user_id -> room

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
        
        exchange = await rabbitmq_channel.get_exchange(CHAT_EXCHANGE)
        await exchange.publish(
            Message(
                message_body.encode(),
                headers={"room": message.room, "user_id": message.user_id}
            ),
            routing_key=f"chat.{message.room}"
        )
        
        logger.info(f"Published message to room {message.room} from user {message.user_id}")
        
    except Exception as e:
        logger.error(f"Error publishing message: {e}")
        raise

async def setup_message_consumer(room: str, user_id: str):
    """Set up message consumer for a specific room"""
    try:
        # Declare queue for the room
        queue = await rabbitmq_channel.declare_queue(
            name="", 
            durable=False,
            exclusive=True,
            auto_delete=True
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
                    if user_id in active_websockets:
                        websocket = active_websockets[user_id]
                        await websocket.send_text(json.dumps(message_data))
                        logger.info(f"Sent message to WebSocket for user id {user_id}")
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        
        # Start consuming messages
        await queue.consume(message_handler)
        logger.info(f"Started consuming messages for room {room}")
        
    except Exception as e:
        logger.error(f"Error setting up consumer for room {room}: {e}")
        raise

@app.get("/auth")
async def auth():
    """Generate a unique ID for the client"""
    unique_id = str(uuid.uuid4())
    active_websockets[unique_id] = None  # Placeholder for WebSocket connection
    user_rooms[unique_id] = None  # No room entered
    return {"id": unique_id}

@app.post("/send_message")
async def send_message(request: SendMessageRequest):
    """HTTP endpoint to send a chat message"""
    try:
        if request.user_id not in active_websockets:
            raise HTTPException(status_code=403, detail="Invalid user ID. Provide authenticated user id.")

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
    
    except HTTPException as http_exc:
        logger.error(f"HTTP error: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")

@app.websocket("/chat/{user_id}")
async def websocket_chat_endpoint(websocket: WebSocket, user_id: str, room: str = "general"):
    """WebSocket endpoint for real-time chat"""
    try:
        await websocket.accept()

        if user_id not in active_websockets:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Invalid user ID. Please authenticate first."
            }))
            await websocket.close()
            logger.error(f"WebSocket connection attempt with unknown user ID: {user_id}")
            return

        room = websocket.query_params.get("room", "general")
        
        active_websockets[user_id] = websocket
        user_rooms[user_id] = room
        
        logger.info(f"WebSocket connected: user {user_id} in room {room}")
    
        # Setup message consumer for this room
        await setup_message_consumer(room, user_id)
        
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
        logger.info(f"WebSocket disconnected: with user id {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user id {user_id}: {e}")
    finally:
        # Cleanup
        if user_id in active_websockets:
            active_websockets[user_id] = None
        if user_id in user_rooms:
            user_rooms[user_id] = None
        
        logger.info(f"Cleaned up WebSocket connection: for user id {user_id}")

@app.get("/rooms")
async def list_rooms():
    """List active chat rooms"""
    rooms = set(user_rooms.values())
    return {
        "active_rooms": list(rooms),
        "total_connections": len(active_websockets)
    }

# For running the server directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)