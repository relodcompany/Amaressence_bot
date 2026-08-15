import logging
import os
import sqlite3
from contextlib import contextmanager
from html import escape
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

DB_PATH = Path(os.getenv("TASK_BOT_DB", "tasks.db"))

MAX_MESSAGE_LENGTH = 3900
MAX_CATEGORY_LENGTH = 100
MAX_TASK_LENGTH = 500

HELP_TEXT = (
    "📋 Task bot. Every chat keeps its own separate task list.\n"
    "\n"
    "Commands:\n"
    "/add <category> ; <task>  - add a task\n"
    "/list                     - show all tasks\n"
    "/complete <task_id>       - mark as done\n"
    "/uncomplete <task_id>     - mark as not done\n"
    "/remove <task_id>         - delete a task\n"
    "/help                     - show this message\n"
    "\n"
    "Example:\n"
    "/add Work ; write the quarterly report\n"
    "\n"
    'The ";" separator is required. You can use "|" instead.'
)

USAGE_ADD = 'Usage: /add <category> ; <task>\nExample: /add Work ; write the quarterly report'

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                category TEXT NOT NULL,
                task TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "chat_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN chat_id INTEGER")
            logger.warning(
                "Migrated tasks table: added chat_id. Tasks created before this "
                "upgrade have no chat and will not appear in any chat's list."
            )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_chat ON tasks (chat_id)")


def parse_add_payload(payload: str) -> tuple[str, str]:
    sep = ";" if ";" in payload else ("|" if "|" in payload else None)
    if sep is None:
        raise ValueError('Missing the ";" separator between category and task.')
    category, task = [part.strip() for part in payload.split(sep, 1)]
    if not category or not task:
        raise ValueError("Both category and task description are required.")
    if len(category) > MAX_CATEGORY_LENGTH:
        raise ValueError(f"Category is too long (max {MAX_CATEGORY_LENGTH} characters).")
    if len(task) > MAX_TASK_LENGTH:
        raise ValueError(f"Task is too long (max {MAX_TASK_LENGTH} characters).")
    return category, task


def parse_task_id(context: ContextTypes.DEFAULT_TYPE) -> int | None:
    args = context.args or []
    if len(args) != 1:
        return None
    raw = args[0].lstrip("#")
    return int(raw) if raw.isdigit() else None


def create_task(chat_id: int, category: str, task: str) -> int:
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (chat_id, category, task) VALUES (?, ?, ?)",
            (chat_id, category, task),
        )
        return int(cur.lastrowid)


def update_completed(chat_id: int, task_id: int, completed: bool) -> bool:
    with db() as conn:
        cur = conn.execute(
            "UPDATE tasks SET completed = ? WHERE id = ? AND chat_id = ?",
            (1 if completed else 0, task_id, chat_id),
        )
        return cur.rowcount > 0


def delete_task(chat_id: int, task_id: int) -> bool:
    with db() as conn:
        cur = conn.execute(
            "DELETE FROM tasks WHERE id = ? AND chat_id = ?",
            (task_id, chat_id),
        )
        return cur.rowcount > 0


def fetch_tasks_grouped(chat_id: int) -> dict[str, list[tuple[int, str, int]]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT id, category, task, completed FROM tasks "
            "WHERE chat_id = ? ORDER BY category, id",
            (chat_id,),
        ).fetchall()

    grouped: dict[str, list[tuple[int, str, int]]] = {}
    for task_id, category, task, completed in rows:
        grouped.setdefault(category, []).append((task_id, task, completed))
    return grouped


def chunk_lines(lines: list[str], limit: int = MAX_MESSAGE_LENGTH) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for line in lines:
        cost = len(line) + 1
        if current and length + cost > limit:
            chunks.append("\n".join(current))
            current, length = [], 0
        current.append(line)
        length += cost
    if current:
        chunks.append("\n".join(current))
    return chunks


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(HELP_TEXT)


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None:
        return

    payload = " ".join(context.args or []).strip()
    if not payload:
        await message.reply_text(USAGE_ADD)
        return

    try:
        category, task = parse_add_payload(payload)
    except ValueError as exc:
        await message.reply_text(f"{exc}\n\n{USAGE_ADD}")
        return

    task_id = create_task(chat.id, category, task)
    await message.reply_text(f"Added task #{task_id} under '{category}'.")


async def complete_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None:
        return

    task_id = parse_task_id(context)
    if task_id is None:
        await message.reply_text("Usage: /complete <task_id>\nExample: /complete 3")
        return

    if update_completed(chat.id, task_id, True):
        await message.reply_text(f"Task #{task_id} marked as completed ✅")
    else:
        await message.reply_text(f"Task #{task_id} was not found in this chat.")


async def uncomplete_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None:
        return

    task_id = parse_task_id(context)
    if task_id is None:
        await message.reply_text("Usage: /uncomplete <task_id>\nExample: /uncomplete 3")
        return

    if update_completed(chat.id, task_id, False):
        await message.reply_text(f"Task #{task_id} marked as not completed.")
    else:
        await message.reply_text(f"Task #{task_id} was not found in this chat.")


async def remove_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None:
        return

    task_id = parse_task_id(context)
    if task_id is None:
        await message.reply_text("Usage: /remove <task_id>\nExample: /remove 3")
        return

    if delete_task(chat.id, task_id):
        await message.reply_text(f"Task #{task_id} removed 🗑️")
    else:
        await message.reply_text(f"Task #{task_id} was not found in this chat.")


async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None:
        return

    grouped = fetch_tasks_grouped(chat.id)
    if not grouped:
        await message.reply_text(f"No tasks yet.\n\n{USAGE_ADD}")
        return

    lines = ["📋 <b>Tasks by category</b>"]
    for category, tasks in grouped.items():
        lines.append(f"\n<b>{escape(category)}</b>")
        for task_id, task, completed in tasks:
            status = "✅" if completed else "⬜"
            lines.append(f"{status} #{task_id} {escape(task)}")

    for chunk in chunk_lines(lines):
        await message.reply_text(chunk, parse_mode="HTML")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Handler failed for update %s", update, exc_info=context.error)


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Missing bot token. Set the TELEGRAM_BOT_TOKEN environment variable "
            "(BOT_TOKEN is also accepted)."
        )

    init_db()
    logger.info("Using database at %s", DB_PATH.resolve())

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("add", add_task))
    application.add_handler(CommandHandler("complete", complete_task))
    application.add_handler(CommandHandler("uncomplete", uncomplete_task))
    application.add_handler(CommandHandler("remove", remove_task))
    application.add_handler(CommandHandler("list", list_tasks))
    application.add_error_handler(on_error)

    logger.info("Bot started...")
    application.run_polling()


if __name__ == "__main__":
    main()
