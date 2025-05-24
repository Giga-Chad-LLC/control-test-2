import { useState, useEffect } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'
import config from './config/config';
import axios from 'axios';

function App() {
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState([]);
  const [connectionId, setConnectionId] = useState(null);
  const [room, setRoom] = useState('general');
  const [roomInput, setRoomInput] = useState('');

  const [messageListeningWebSocket, setMessageListeningWebSocket] = useState(null);

  // Connect
  const connect = async () => {
    return axios.get(`${config.API_URL}/connect`)
      .then((res) => {
        console.log(res.data);
        setConnectionId(res.data.connection_id);
        return res.data.connection_id;
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
      message: message,
      room: room,
    })
      .then(res => {
        console.log(res);
        setMessage('');
      });

  };

  // Listen messages
  const listenMessagesFromRoom = (connectionId) => {
    // clear messages
    setMessages([]);

    setMessageListeningWebSocket(previousWs => {
      // close previous websocket
      if (previousWs) {
        previousWs.close();
      }

      // TODO: install room
      const ws = new WebSocket(`${config.WS_URL}/chat/${connectionId}`);
      // Handle incoming messages
      ws.onmessage = (event) => {
        setMessages([...messages, JSON.parse(event.data)]);
      };

      return ws;
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

    axios.post(`${config.API_URL}/change_room`, {
      room: roomInput,
    })
      .then((res) => {
        console.log(res.data);
        setRoom(res.data.room);
      });
  };


  // connect and listen messages
  useEffect(() => {
    connect().then((connectionId) => {
      console.log(`Successfully connected: received connection id ${connectionId}`);
      listenMessagesFromRoom(connectionId);
    });
  }, []);


  useEffect(() => {
    if (connectionId) {
      listenMessagesFromRoom(connectionId);
    }
  }, [room, connectionId]);


  return (
    <div className="app-container">
      <div className="chat-container">
        <h1>RabbitMQ Chat</h1>

        <div className="chat-buttons">
          {(connectionId == null) ? (<button onClick={connect}>Connect</button>) : null}

          <div className="room-block">
            <p>Current room: <i><b>{room}</b></i></p>
            <input type="text" placeholder="New room" value={roomInput} onChange={(e) => setRoomInput(e.target.value)} />
            <button onClick={changeRoom}>Change room</button>
          </div>

          <div className="send-block">
            <input disabled={!connectionId} type="text" placeholder="Message" value={message} onChange={(e) => setMessage(e.target.value)} />
            <button disabled={!connectionId} onClick={sendMessage}>Send</button>
          </div>
        </div>

        <div>
          <h2 className="messages-title">Messages</h2>
          <div className="messages-container">
            { messages.length == 0 ? (<div className="messages-empty">No messages yet</div>) : null }

            {messages.map((message) => (
              <div className="message-block" key={message.id}>{message.content}</div>
            ))}
          </div>
        </div>

      </div>
    </div>
  )
}

export default App
