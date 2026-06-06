from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from agentforge.runtime.engine import AgentRuntime

logger = logging.getLogger(__name__)


def make_message_handler(runtime: AgentRuntime):
    """Returns an asynchronous handler that processes messages via AgentRuntime."""

    async def handle_message(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not update.message or not update.message.text:
            return

        text = update.message.text.strip()
        if not text:
            return

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action="typing"
        )

        try:
            result = runtime.run(text)
            output = result["output"]
            violations = result["metadata"].get("guardrail_violations")
            if violations:
                output += "\n\n⚠️ Warning: response revised by guardrails."
        except Exception as exc:
            logger.exception("Error processing Telegram message: %s", exc)
            output = "Error processing your message. Please try again."

        await update.message.reply_text(output)

    return handle_message


def create_application(runtime: AgentRuntime, token: str) -> Application:
    app = Application.builder().token(token).build()
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, make_message_handler(runtime))
    )
    return app


def run_polling(runtime: AgentRuntime, token: str) -> None:
    logger.info(
        "Telegram bot starting for agent '%s' (model: %s)",
        runtime.agent_spec.agent.id,
        runtime.runtime_config.model_default,
    )
    app = create_application(runtime, token)
    app.run_polling()
