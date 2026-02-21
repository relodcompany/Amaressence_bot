# Telegram Group Task Bot

A Telegram bot that stores tasks for a group chat, organized by category.

## Features

- Add a task to a category.
- Mark tasks as completed.
- Mark tasks as not completed.
- Remove tasks.
- Print a full grouped task list.

## Commands

- `/add <category> | <task description>`
- `/complete <task_id>`
- `/uncomplete <task_id>`
- `/remove <task_id>`
- `/list`

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

## Storage

The bot uses SQLite and creates `tasks.db` in the current directory by default.
You can change the location with:

```bash
export TASK_BOT_DB="/path/to/tasks.db"
```
