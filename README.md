## Trello VK bot

### Step 1) Requirements

- Windows / Linux / macOS 10 (or Docker)
- Python 3.5+
- PostgreSQL

### Step 2) Install

Run in your postgres console:

```
CREATE DATABASE trello_vk_bot;
\connect trello_vk_bot;
CREATE TABLE users(
id serial primary key,
vk_id integer,
trello_api_key varchar(32), 
trello_api_token varchar(64), 
step integer, 
days integer, 
total_percent float,
trello_board varchar(512),
trello_list varchar(512));
```

Run in your console:

```
sudo apt update && sudo apt -y dist-upgrade
sudo apt install -y git python3-venv
git clone https://github.com/vahellame/trello-vk-bot.git
cd trello-vk-bot
```

View and edit `config.py`.

```
python3 -m venv venv
./venv/bin/pip install -U pip 
./venv/bin/pip install -r requirments.txt
```

### Step 3) Running bot

```
./venv/bin/python main.py
```
