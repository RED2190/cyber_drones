"""
Юнит-тесты для Dispatcher.
Проверяем маршрутизацию сообщений по топикам.
"""
import pytest
from unittest.mock import AsyncMock
from src.regulator_component.src.dispatcher import Dispatcher


class TestDispatcher:
    @pytest.fixture
    def dispatcher(self):
        return Dispatcher()

    @pytest.mark.asyncio
    async def test_registered_handler_is_called(self, dispatcher):
        handler = AsyncMock()
        dispatcher.register("test.topic", handler)
        await dispatcher.dispatch("test.topic", {"key": "value"})
        handler.assert_called_once_with({"key": "value"})

    @pytest.mark.asyncio
    async def test_unknown_topic_does_not_raise(self, dispatcher):
        # Нет handler — просто логирует warning, не падает
        await dispatcher.dispatch("unknown.topic", {"key": "value"})

    @pytest.mark.asyncio
    async def test_json_string_is_parsed_to_dict(self, dispatcher):
        handler = AsyncMock()
        dispatcher.register("test.topic", handler)
        await dispatcher.dispatch("test.topic", '{"key": "value"}')
        handler.assert_called_once_with({"key": "value"})

    @pytest.mark.asyncio
    async def test_bytes_message_is_parsed_to_dict(self, dispatcher):
        handler = AsyncMock()
        dispatcher.register("test.topic", handler)
        await dispatcher.dispatch("test.topic", b'{"key": "value"}')
        handler.assert_called_once_with({"key": "value"})

    @pytest.mark.asyncio
    async def test_invalid_json_does_not_raise(self, dispatcher):
        handler = AsyncMock()
        dispatcher.register("test.topic", handler)
        await dispatcher.dispatch("test.topic", "not valid json {{{")
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_topics_route_independently(self, dispatcher):
        handler_a = AsyncMock()
        handler_b = AsyncMock()
        dispatcher.register("topic.a", handler_a)
        dispatcher.register("topic.b", handler_b)

        await dispatcher.dispatch("topic.a", {"msg": "for a"})
        handler_a.assert_called_once_with({"msg": "for a"})
        handler_b.assert_not_called()

    @pytest.mark.asyncio
    async def test_handler_exception_does_not_crash_dispatcher(self, dispatcher):
        async def bad_handler(msg):
            raise RuntimeError("something went wrong")

        dispatcher.register("test.topic", bad_handler)
        # Не должно пробросить исключение наружу
        await dispatcher.dispatch("test.topic", {"key": "value"})
