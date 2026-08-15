# Telegram Group Task Bot

A Telegram bot that stores tasks, organized by category.

**Every chat has its own separate task list.** Tasks added in one group are
invisible to any other group, and to private chats. Task IDs are unique across
the whole bot, and commands only affect tasks belonging to the chat they are
sent from.

## Features

- Add a task to a category.
- Mark tasks as completed.
- Mark tasks as not completed.
- Remove tasks.
- Print a full grouped task list.

## Commands

- `/add <category> ; <task description>`
- `/complete <task_id>`
- `/uncomplete <task_id>`
- `/remove <task_id>`
- `/list`
- `/help`

The `;` separator between category and task is **required**. `|` works too.

```
/add Work ; write the quarterly report
```

Task IDs may be given with or without a `#`, so `/complete 3` and
`/complete #3` are equivalent.

Category is limited to 100 characters, task text to 500.

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the bot token.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Export your token:
   ```bash
   export TELEGRAM_BOT_TOKEN="YOUR_TOKEN_HERE"
   ```
4. Run the bot:
   ```bash
   python bot.py
   ```
5. Add the bot to your Telegram group and grant it permission to read/send messages.

## Environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | yes | Bot token from @BotFather. `BOT_TOKEN` is accepted as a fallback. |
| `TASK_BOT_DB` | no | Path to the SQLite file. Defaults to `tasks.db` in the working directory. |

## Storage

The bot uses SQLite and creates `tasks.db` in the current directory by default.
You can change the location with:

```bash
export TASK_BOT_DB="/path/to/tasks.db"
```

**When deploying in a container, point `TASK_BOT_DB` at a mounted volume.**
The default path lives inside the container filesystem, so every rebuild or
restart destroys all tasks.

Upgrading from a version before per-chat lists is handled automatically: the
`chat_id` column is added on startup. Tasks created before the upgrade have no
chat assigned and will not appear in any list.
