import pika
import logging
import uuid
from typing import List, Dict, Set
from collections import defaultdict



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConnectionInfo:
    connection_id: str
    queue_name: str
    host: str
    port: int
    # channel: pika.BlockingConnection


class Message:
    connection_id: str
    message: str
    sender: str



class ConnectionManager:
    def __init__(self):
        self.connections: Dict[str, ConnectionInfo] = defaultdict(ConnectionInfo)
        self.queue_subscribers: Dict[str, Set[str]] = defaultdict(set)

    def connect(self, host: str, port: int, queue_name: str) -> str:
        connection_id = uuid.uuid4()

        if connection_id in self.connections:
            raise ValueError(f"Connection {connection_id} already exists")
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=host, port=port))
            channel = connection.channel()
            channel.queue_declare(queue=queue_name)
            logger.info(f"Created RabbitMQ channel for connection {connection_id}")
        except Exception as e:
            logger.error(f"Failed to create RabbitMQ channel: {str(e)}")
            raise

        connection_info = ConnectionInfo(connection_id, queue_name, host, port)
        self.connections[connection_id] = connection_info

        return connection_id


    def change_queue(self, connection_id: str, queue_name: str):
        self._validate_connection_id(connection_id)

        old_queue_name = self.connections[connection_id].queue_name
        self.connections[connection_id].queue_name = queue_name
        # add into new queue
        self.queue_subscribers[queue_name].add(connection_id)
        # remove from old queue
        if connection_id in self.queue_subscribers[old_queue_name]:
            self.queue_subscribers[old_queue_name].remove(connection_id)


    def notify_queue_subscribers(self, queue_name: str, message: Message):



    def _validate_connection_id(self, connection_id: str):
        if connection_id not in self.connections:
            raise ValueError(f"Connection {connection_id} not found")
