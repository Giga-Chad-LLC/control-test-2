import { useState, useEffect, useRef } from 'react'
import './App.css'
import config from './config/config';
import axios from 'axios';

function App() {
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState([]);
  const [userId, setUserId] = useState(null);
  const [room, setRoom] = useState('general');
  const [roomInput, setRoomInput] = useState('');

  const wsRef = useRef(null);

  // Authenticate user
  const authenticate = async () => {
    return axios.get(`${config.API_URL}/auth`)
      .then((res) => {
        console.log(res.data);
        setUserId(res.data.user_id);
        return res.data.user_id;
      });
  };

  // Send message
  const sendMessage = () => {
    if (!message || message.length == 0) {
      alert("Message is empty");
      return;
    }

    console.log("Sending message", message);

    axios.post(`${config.API_URL}/send_message`, {
      user_id: userId,
      message: message,
    })
      .then(res => {
        console.log(res);
        setMessage('');
      });
  };

  // Change room
  const changeRoom = () => {
    if (!roomInput || roomInput.length == 0) {
      alert("Room input is empty");
      return;
    }
    if (roomInput == room) {
      alert("Room input is the same as the current room");
      return;
    }

    setRoom(roomInput);
  };

   // Connect to WebSocket when userId or room changes
   useEffect(() => {
    if (!userId) return;

    // Clear messages on room change
    setMessages([]);

    // If an existing WebSocket exists, close it first
    if (wsRef.current) {
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      wsRef.current.onclose = null;
      wsRef.current.close();
    }

    // Create new WebSocket connection
    const ws = new WebSocket(`${config.WS_URL}/chat/${userId}?room=${room}`);

    ws.onmessage = (event) => {
      console.log("Received message:", event.data);
      setMessages(prev => [...prev, JSON.parse(event.data)]);
    };

    ws.onclose = () => {
      console.log("WebSocket closed");
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      alert("Failed to connect to the chat room. Please try again later.");
    };

    wsRef.current = ws;

    // Cleanup when component unmounts or before next effect run
    return () => {
      if (wsRef.current) {
        wsRef.current.onmessage = null;
        wsRef.current.onerror = null;
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [userId, room]);


  return (
    <div className="app-container">
      <div className="chat-container">
        <h1>RabbitMQ Chat</h1>

        <div className="chat-buttons">
          {(userId == null) ? (<button onClick={() => {
            authenticate().then((userId) => {
              console.log(`Successfully authenticated: received user id ${userId}`);
            });
          }}>Authenticate</button>) : null}
          <div>User id: {userId}</div>

          <div className="room-block">
            <p>Current room: <i><b>{room}</b></i></p>
            <input type="text" placeholder="New room" value={roomInput} onChange={(e) => setRoomInput(e.target.value)} />
            <button onClick={changeRoom}>Change room</button>
          </div>

          <div className="send-block">
            <input disabled={!userId} type="text" placeholder="Message" value={message} onChange={(e) => setMessage(e.target.value)} />
            <button disabled={!userId} onClick={sendMessage}>Send</button>
          </div>
        </div>

        <div>
          <h2 className="messages-title">Messages</h2>
          <div className="messages-container">
            { messages.length == 0 ? (<div className="messages-empty">No messages yet</div>) : null }

            {messages.map((message, i) => (
              <div className="message-block" key={i}>
                <p className='message-user-id'>From: {message.user_id}</p>
                {message.message}
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  )
}

export default App
