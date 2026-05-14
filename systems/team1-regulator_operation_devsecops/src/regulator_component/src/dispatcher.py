import json
import logging

logger = logging.getLogger(__name__)

class Dispatcher:
    def __init__(self):
        self.routes = {}

    def register(self, topic, handler):
        self.routes[topic] = handler

    async def dispatch(self, topic, message):
        try:
            # ПРОВЕРКА 1: Если пришла строка, превращаем в словарь
            if isinstance(message, str):
                data = json.loads(message)
            elif isinstance(message, bytes):
                data = json.loads(message.decode())
            else:
                data = message

            # Теперь data ГАРАНТИРОВАННО словарь
            handler = self.routes.get(topic)
            if handler:
                # ПРОВЕРКА 2: Вызываем обработчик
                await handler(data) 
            else:
                logger.warning(f"No handler for topic {topic}")

        except json.JSONDecodeError:
            logger.error(f"Crictical: Message on {topic} is not valid JSON: {message}")
        except Exception as e:
            logger.error(f"Error in dispatcher: {e}", exc_info=True)
