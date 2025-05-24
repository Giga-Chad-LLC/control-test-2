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

  const sendMessage = () => {
    console.log("Sending message", message);
    setMessage('');
  };

  const connect = () => {
    // const ws = new WebSocket(`ws://localhost:8000/chat/${connectionId}`);
    // ws.onmessage = (event) => {
    //   setMessages([...messages, JSON.parse(event.data)]);
    // };

    axios.get(`${config.API_URL}/connect`)
      .then((res) => {
        console.log(res.data);
        setConnectionId(res.data.connection_id);
      });

  };

  // get connection id
  useEffect(() => connect(), []);

  return (
    <div className="app-container">
      <div className="chat-container">
        <h1>RabbitMQ Chat</h1>
        <div className="chat-buttons">

          {(connectionId == null) ? (<button onClick={connect}>Connect</button>) : null}

          <input type="text" placeholder="Message" value={message} onChange={(e) => setMessage(e.target.value)} />
          <button onClick={sendMessage}>Send</button>
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
