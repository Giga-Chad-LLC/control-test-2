# RabbitMQ Chat Application

A real-time chat application built with RabbitMQ message broker, using FastAPI and React client.

Watch the application in action:

![Video Demo](./assets/demo.mp4)

## Overview

Project implements a chat system with RabbitMQ for message exchange. Users can join different chat rooms, send messages, and receive real-time updates via WebSocket connections.

## Architecture

### Server Components

#### **FastAPI Server** (`server/core/server.py`)
- **Framework**: FastAPI with async/await support
- **Message Broker**: RabbitMQ integration using `aio_pika`
- **Real-time Communication**: WebSocket endpoints for live chat

#### **Key Features**:
- **User Authentication**: UUID-based user identification system
- **Room Management**: Dynamic channel creation and switching
- **Message Broadcasting**: Topic-based exchange for room-specific messaging
- **Connection Management**: Tracks active WebSocket connections and user room assignments

#### **API Endpoints**:
- `GET /auth` - Generate unique user ID
- `POST /send_message` - Send chat message via HTTP
- `WS /chat/{user_id}` - WebSocket connection for real-time messaging
- `GET /rooms` - List active rooms and connections

#### **RabbitMQ Configuration**:
- **Exchange**: Topic exchange (`chat_exchange`) for routing messages
- **Routing Keys**: Pattern `chat.{room_name}` for room-based message delivery
- **Message Persistence**: Non-durable queues (no message history)

### Client Components

#### **React GUI Client** (`client/src/`)
- **Framework**: React 19 with Vite build tool
- **HTTP Client**: Axios for REST API communication
- **WebSocket**: Native WebSocket API for messaging

#### **Key Features**:
- **User Authentication**: Automatic user ID generation and management
- **Room Switching**: Change rooms on UI
- **Message Display**: Real-time message feed with sender identification

#### **Components**:
- **Authentication System**: Handles user ID generation and storage
- **Message Input**: Send messages to current room
- **Room Management**: Switch between chat rooms dynamically
- **Message Feed**: Display incoming messages with timestamps
- **Error Handling**: Connection and message validation

### Configuration

#### **Server Configuration**:
- **RabbitMQ URL**: `amqp://guest:guest@localhost:5672/`
- **Server Port**: 8000 (configurable)
- **Exchange Type**: Topic exchange for flexible routing

#### **Client Configuration** (`client/src/config/config.js`):
- **API URL**: `http://localhost:8000`
- **WebSocket URL**: `ws://localhost:8000`

## Setup and Installation

### Prerequisites
- Docker (for RabbitMQ)
- Python 3.8+ (for server)
- React.js 16+ (for client)

### RabbitMQ Setup
```bash
# Start RabbitMQ Docker container
bash rabbit.sh
```

### Server Setup
```bash
cd server
pip install -r requirements.txt
# Additional dependencies: fastapi, uvicorn, aio-pika
python -m uvicorn core.server:app --host 0.0.0.0 --port 8000
```

### Client Setup
```bash
cd client
npm install
npm run dev
```

## Usage

1. **Start Services**: Launch RabbitMQ, server, and client
2. **Authenticate**: Click "Authenticate" to receive user ID
3. **Join Room**: Enter room name and click "Change room"
4. **Send Messages**: Type message and click "Send"
5. **Real-time Updates**: Messages appear instantly via WebSocket

## Technical Implementation

### Message Flow
1. Client sends message via WebSocket or HTTP
2. Server publishes to RabbitMQ topic exchange
3. Exchange routes to room-specific queues
4. Consumers receive messages and forward to WebSocket clients
5. Real-time display in client interface

### Room Management
- Rooms created automatically when first accessed
- No persistent room storage (created on-demand)
- Users can switch rooms without losing connection
- Each room isolated via routing keys

### Connection Handling
- Robust WebSocket connection with auto-cleanup
- User session management via UUID tracking
- Graceful disconnection and resource cleanup
- Error handling for connection failures

## Dependencies

### Server
- `fastapi` - Web framework
- `aio-pika` - Async RabbitMQ client
- `uvicorn` - server

### Client
- `react` - UI framework
- `axios` - HTTP client
- `vite` - Build tool and dev server
