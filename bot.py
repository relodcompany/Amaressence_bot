import logging
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import Application, CommandHandler, ContextTypes

DB_PATH = Path(os.getenv("TASK_BOT_DB", "tasks.db"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def init_db() -> None:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                task TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def parse_add_payload(payload: str) -> tuple[str, str]:
    if ";" not in payload:  # ← CHANGED: ";" instead of "|"
        raise ValueError("Format must be: /add <category> ; <task description>")  # ← CHANGED: ";" 
    category, task = [part.strip() for part in payload.split(";", 1)]  # ← CHANGED: split(";", 1)
    if not category or not task:
        raise ValueError("Both category and task description are required.")

    return category, task


def create_task(category: str, task: str) -> int:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tasks (category, task) VALUES (?, ?)",
            (category, task),
        )
        conn.commit()
        return int(cur.lastrowid)


def update_completed(task_id: int, completed: bool) -> bool:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE tasks SET completed = ? WHERE id = ?",
            (1 if completed else 0, task_id),
        )
        conn.commit()
        return cur.rowcount > 0


def delete_task(task_id: int) -> bool:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return cur.rowcount > 0


def fetch_tasks_grouped() -> dict[str, list[tuple[int, str, int]]]:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        rows = conn.execute(
            "SELECT id, category, task, completed FROM tasks ORDER BY category, id"
        ).fetchall()

    grouped: dict[str, list[tuple[int, str, int]]] = {}
    for task_id, category, task, completed in rows:
        grouped.setdefault(category, []).append((task_id, task, completed))
    return grouped


def is_group(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat and chat.type in {ChatType.GROUP, ChatType.SUPERGROUP})


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
await update.message.reply_text(
    "Task bot is ready.\n"
    "Use these commands in your group:\n"
    "/add category ; task\n"  # Removed |, added ; 
    "/complete task_id\n"
    "/uncomplete task_id\n"
    "/remove task_id\n"
    "/list"
)


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_group(update):
        await update.message.reply_text("Please use this bot inside a group chat.")
        return

    payload = " ".join(context.args).strip()
    try:
        category, task = parse_add_payload(payload)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return

    task_id = create_task(category, task)
    await update.message.reply_text(f"Added task #{task_id} under '{category}'.")


async def complete_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /complete task_id")
        return

    task_id = int(context.args[0])
    if update_completed(task_id, True):
        await update.message.reply_text(f"Task #{task_id} marked as completed ✅")
    else:
        await update.message.reply_text(f"Task #{task_id} was not found.")


async def uncomplete_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /uncomplete task_id")
        return

    task_id = int(context.args[0])
    if update_completed(task_id, False):
        await update.message.reply_text(f"Task #{task_id} marked as not completed.")
    else:
        await update.message.reply_text(f"Task #{task_id} was not found.")


async def remove_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /remove task_id")
        return

    task_id = int(context.args[0])
    if delete_task(task_id):
        await update.message.reply_text(f"Task #{task_id} removed 🗑️")
    else:
        await update.message.reply_text(f"Task #{task_id} was not found.")


async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    grouped = fetch_tasks_grouped()
    if not grouped:
        await update.message.reply_text("No tasks yet. Add one with /add category ; task")
        return

    lines = ["📋 *Tasks by category*"]
    for category, tasks in grouped.items():
        lines.append(f"\n*{category}*")
        for task_id, task, completed in tasks:
            status = "✅" if completed else "⬜"
            lines.append(f"{status} #{task_id} {task}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable.")

    init_db()

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_task))
    application.add_handler(CommandHandler("complete", complete_task))
    application.add_handler(CommandHandler("uncomplete", uncomplete_task))
    application.add_handler(CommandHandler("remove", remove_task))
    application.add_handler(CommandHandler("list", list_tasks))

    logger.info("Bot started...")
    application.run_polling()


if __name__ == "__main__":
    main()
