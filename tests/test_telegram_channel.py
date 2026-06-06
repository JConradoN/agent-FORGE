"""Testes do canal Telegram (sem conexão real — mocks de Update/Context)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from agentforge.channels.telegram import create_application, make_message_handler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_runtime(output: str = "Resposta do agente.", violations: list | None = None) -> Mock:
    runtime = MagicMock()
    runtime.agent_spec.agent.id = "test_agent"
    runtime.agent_spec.agent.name = "Test Agent"
    runtime.runtime_config.model_default = "qwen3.5:9b"
    runtime.runtime_config.provider = "ollama"
    runtime.run.return_value = {
        "output": output,
        "metadata": {
            "guardrail_violations": violations,
        },
    }
    return runtime


def _make_update(text: str | None = "olá") -> MagicMock:
    update = MagicMock()
    update.effective_chat.id = 12345
    if text is None:
        update.message = None
    else:
        update.message.text = text
        update.message.reply_text = AsyncMock()
    return update


def _make_context() -> MagicMock:
    context = MagicMock()
    context.bot.send_chat_action = AsyncMock()
    return context


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# make_message_handler
# ---------------------------------------------------------------------------

class TestMakeMessageHandler:
    def test_valid_message_calls_runtime_and_replies(self) -> None:
        runtime = _make_runtime("Tudo certo.")
        handler = make_message_handler(runtime)
        update = _make_update("como está o servidor?")
        context = _make_context()

        _run(handler(update, context))

        runtime.run.assert_called_once_with("como está o servidor?")
        update.message.reply_text.assert_awaited_once_with("Tudo certo.")

    def test_sends_typing_action_before_reply(self) -> None:
        runtime = _make_runtime("ok")
        handler = make_message_handler(runtime)
        update = _make_update("ping")
        context = _make_context()

        _run(handler(update, context))

        context.bot.send_chat_action.assert_awaited_once_with(
            chat_id=12345, action="typing"
        )

    def test_none_message_does_nothing(self) -> None:
        runtime = _make_runtime()
        handler = make_message_handler(runtime)
        update = _make_update(text=None)
        context = _make_context()

        _run(handler(update, context))

        runtime.run.assert_not_called()

    def test_empty_text_does_nothing(self) -> None:
        runtime = _make_runtime()
        handler = make_message_handler(runtime)
        update = _make_update(text="   ")
        context = _make_context()

        _run(handler(update, context))

        runtime.run.assert_not_called()

    def test_runtime_error_replies_with_error_message(self) -> None:
        runtime = _make_runtime()
        runtime.run.side_effect = RuntimeError("ollama timeout")
        handler = make_message_handler(runtime)
        update = _make_update("teste")
        context = _make_context()

        _run(handler(update, context))

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Erro" in reply_text

    def test_guardrail_violations_appends_warning(self) -> None:
        runtime = _make_runtime(
            output="Resposta revisada.",
            violations=["inventar dados"],
        )
        handler = make_message_handler(runtime)
        update = _make_update("estado?")
        context = _make_context()

        _run(handler(update, context))

        reply_text = update.message.reply_text.call_args[0][0]
        assert "guardrails" in reply_text.lower()

    def test_no_violations_no_warning(self) -> None:
        runtime = _make_runtime(output="Resposta limpa.", violations=None)
        handler = make_message_handler(runtime)
        update = _make_update("estado?")
        context = _make_context()

        _run(handler(update, context))

        reply_text = update.message.reply_text.call_args[0][0]
        assert "guardrail" not in reply_text.lower()


# ---------------------------------------------------------------------------
# create_application
# ---------------------------------------------------------------------------

class TestCreateApplication:
    def test_creates_application_with_handler(self) -> None:
        runtime = _make_runtime()

        with patch("agentforge.channels.telegram.Application") as mock_app_cls:
            mock_builder = MagicMock()
            mock_app_cls.builder.return_value = mock_builder
            mock_builder.token.return_value = mock_builder
            mock_builder.build.return_value = MagicMock()

            app = create_application(runtime, "fake-token-123")

            mock_builder.token.assert_called_once_with("fake-token-123")
            mock_builder.build.assert_called_once()
            assert app is not None

    def test_handler_registered(self) -> None:
        runtime = _make_runtime()

        with patch("agentforge.channels.telegram.Application") as mock_app_cls:
            mock_builder = MagicMock()
            mock_app_cls.builder.return_value = mock_builder
            mock_builder.token.return_value = mock_builder
            mock_app_obj = MagicMock()
            mock_builder.build.return_value = mock_app_obj

            create_application(runtime, "tok")

            mock_app_obj.add_handler.assert_called_once()
