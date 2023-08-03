# TrivAI: Trivia Telegram Chatbot by Roman Kees

## What this is:
This is a chatbot for Telegram that provides you with fresh trivia every day.

## What it does:
It extracts trivia from Wikipedia articles using OpenAI's ChatGPT to identify trivia in articles.
Articles are selected randomly, or users can send the bot the name of a topic that they want to see trivia about.
ChatGPT output is validated through fuzzywuzzy partial_ratio matching to minimize hallucinations being sent to users.
Users can ask the bot for more info on a given topic and it will send the official summarized version of the Wikipedia article, and a link to the full article when asked again.
Users can give feedback about good triva, and the bot will save these pieces of trivia to a MongoDB Atlas instance and retrieve these on occassion, to save on costly API calls.

__CAUTION__: Because this chatbot uses the ChatGPT API, the usual caveats about LLM hallucinations apply. Ask the bot about more information on the topic to check the sources.

## Setup

### Prerequisites:

Create a free Telegram bot using BotFather: https://core.telegram.org/bots#how-do-i-create-a-bot 
Create a free MongoDB Atlas account: https://www.mongodb.com/cloud/atlas/register 
Create an OpenAI account and set up a payment method: https://openai.com/blog/openai-api 

### Installation
Install the required packages from requirements.txt in your virtual environment:

```bash
pip install -r requirements.txt
```

Install the required spacy language package:
```bash
python -m spacy download en_core_web_sm
```

Create a `.env` file in the main folder.

Add the environment variables to the `.env` file:

```
OPENAI_API_KEY=/Your OpenAI API token/
TELEGRAM_API_KEY=/Your telegram access token for your Telegram bot/
MONGO_DB_KEY=/The key for your MongoDB Atlas cluster/
MONGO_DB_CLUSTER=/The name of your MongoDB Atlas cluster (e.g. cluster0.1x2xy3z)/
WIKIPEDIA_USER_AGENT=/A user agent name to inform Wikipedia about who is requesting access, you can choose this freely/
```

## Usage

### Run the TrivAI Chatbot
```bash
python3 run_trivAI_bot.py
```