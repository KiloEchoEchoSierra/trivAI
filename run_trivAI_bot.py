import logging
import os
import requests
import random
import wikipediaapi
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, constants
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes
from langchain.llms import OpenAI
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz
from pymongo import MongoClient
from dotenv import load_dotenv


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


def get_random_doc_from_db():
    res = db.trivia.aggregate([
        {
            "$sample": {
            "size": 1
            }
        }
    ])

    res = list(res)[0]

    return res


def get_random_advice(chance_of_advice=0.1):
    advice_list = ["You can write me the name of a topic that you want to hear trivia about and I will do my best to find an interesting fact about it.",
                   "If you find a fact particularly interesting, please let me know via the button, so I can share it with other users.", 
                   "Please note that I am based on ChatGPT so I may make mistakes and misunderstand some things. You can always ask me to tell you more about a topic to check my sources.",
                   "If you ask me to tell you more about a topic twice, I will give you a link to the original Wikipedia article.",
                   "When people tell me that they like a particular piece of trivia, I save it to a database. If I run out of OpenAI credits for the month, I can still show these facts!",
                   "Just write me a topic that interests you or let me choose a random trivia fact!",
                   "By telling me when a trivia fact is interesting, you can help me improve for everyone :)",
                   "That's interesting, huh?"
                   ]
    if random.random() < chance_of_advice:
        advice_str = advice_list[random.randint(0,len(advice_list)-1)]
        return advice_str
    return None



def get_random_trivia_from_db()  -> str | str | str | str:
    trivia_from_db = get_random_doc_from_db()
    article_name = trivia_from_db["article_name"]
    full_text = wiki_wiki.page(article_name.strip()).summary
    result = trivia_from_db["result"]
    wiki_url = trivia_from_db["wiki_url"]
    return article_name, full_text, result, wiki_url


def get_random_trivia() -> str | str | str | str:
    url = requests.get("https://en.wikipedia.org/wiki/Special:Random")
    soup = BeautifulSoup(url.content, "html.parser")
    article_name = soup.find(class_="firstHeading").text
    wiki_page = wiki_wiki.page(article_name.strip())
    wiki_url = wiki_page.fullurl
    text_content = wiki_page.summary if len(wiki_page.text) > 2000 else wiki_page.text
    text_content = text_content.split(sep="\n\nReferences")[0].replace("\n", " ").replace(r"\\", "").replace("== References ==", "")
    result = None

    if wiki_page.exists() and len(text_content) > 300:
            wiki_query = f"Find an interesting piece of trivia in this text. Do not use the word trivia. Use only information in this text: {text_content}"
            try:
                result = llm(wiki_query)
            except:
                return get_random_trivia_from_db()

            if fuzz.partial_ratio(text_content, result) < 70:
                print("Fuzzy matching failed, fall back to trivia from db.")
                return get_random_trivia_from_db()
    else:
        print("Getting new trivia")
        return get_random_trivia_from_db()
    return article_name, text_content, result.strip(), wiki_url
    

def get_specific_trivia(article_name: str) -> str | str | str | str:
    wiki_page = None
    try:
        wiki_page = wiki_wiki.page(article_name.strip())
        wiki_url = wiki_page.fullurl
        text_content = wiki_page.summary if len(wiki_page.text) > 2000 else wiki_page.text
        text_content = text_content.split(sep="\n\nReferences")[0].replace("\n", " ").replace(r"\\", "").replace("== References ==", "")
    except: 
        print("Could not find Wikipedia entry")

    result = None

    if wiki_page.exists() and len(text_content) > 300:
            wiki_query = f"Find an interesting piece of trivia in this text. Do not use the word trivia. Use only information in this text: {text_content}"
            try:
                result = llm(wiki_query)
            except:
                print("Could not produce trivia from Wikipedia entry.")
    if result:
        return article_name, text_content, result.strip(), wiki_url
    else:
        return None, None, None, None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hi, I am a bot that loves to share trivia! I get my information from Wikipedia. Nevertheless, since I am based on ChatGPT, I may sometimes misunderstand some things. You can always ask me to tell you more about the latest trivia fact and I will give you the original info from Wikipedia!")
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Here's a random piece of trivia I found on Wikipedia for you:")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    article_name, full_text, result, wiki_url = get_random_trivia()
    last_result_dict[update.effective_chat.id] = [article_name, result, wiki_url]
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{article_name}: {result}", reply_markup=ReplyKeyboardMarkup(buttons))


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(context)
    advice = get_random_advice(chance_of_advice=0.1)
    if update.message.text == "Tell me some more trivia!":
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
        article_name, full_text, result, wiki_url = get_random_trivia()
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{article_name}: {result}", reply_markup=ReplyKeyboardMarkup(buttons))
        last_result_dict[update.effective_chat.id] = [article_name, result, wiki_url]
        await context.bot.send_message(chat_id=update.effective_chat.id, text=advice, reply_markup=ReplyKeyboardMarkup(buttons)) if advice else None
    elif update.message.text == "Tell me more about this!":
        if len(last_result_dict[update.effective_chat.id]) < 4:
            article_text = wiki_wiki.page(last_result_dict[update.effective_chat.id][0].strip()).summary
            max_len_of_message = 4000
            parts_of_article = [article_text[i:i+max_len_of_message] for i in range(0, len(article_text), max_len_of_message)]
            for part_of_article in parts_of_article:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=part_of_article)
            last_result_dict[update.effective_chat.id].append(last_result_dict[update.effective_chat.id][2])
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{last_result_dict[update.effective_chat.id][3]}", reply_markup=ReplyKeyboardMarkup(buttons))
    elif update.message.text ==  "I like this fact!":
        if not collection.find_one({'article_name': last_result_dict[update.effective_chat.id][0]}):
            print(f"Saving {last_result_dict[update.effective_chat.id][0]} to database")
            collection.insert_one({"article_name": last_result_dict[update.effective_chat.id][0], "result": last_result_dict[update.effective_chat.id][1], "wiki_url": last_result_dict[update.effective_chat.id][2]})
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Thanks! I will share this fact about {last_result_dict[update.effective_chat.id][0]} with other users!", reply_markup=ReplyKeyboardMarkup(buttons))
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Thanks! I will share this fact about {last_result_dict[update.effective_chat.id][0]} with other users!", reply_markup=ReplyKeyboardMarkup(buttons))

    else:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
        article_name, full_text, result, wiki_url = get_specific_trivia(article_name=update.message.text)
        if article_name:
            last_result_dict[update.effective_chat.id] = [article_name, result, wiki_url]
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{article_name}: {result}", reply_markup=ReplyKeyboardMarkup(buttons))
            await context.bot.send_message(chat_id=update.effective_chat.id, text=advice, reply_markup=ReplyKeyboardMarkup(buttons)) if advice else None
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Sorry, I could not produce any trivia on this topic. This may be because I could not find any information on this or because I'm out of credits for the month. Please try something else or use the interactive buttons.", reply_markup=ReplyKeyboardMarkup(buttons))
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"If you don't see the buttons, you can tap the icon with the four circles at the top right of your keyboard to open the menu.", reply_markup=ReplyKeyboardMarkup(buttons))


if __name__ == '__main__':
    load_dotenv()
    last_result_dict = {}

    api_key = os.environ.get("OPENAI_API_KEY")
    telegram_api_key = os.environ.get("TELEGRAM_API_KEY")
    mongo_db_key = os.environ["MONGO_DB_KEY"]

    client = MongoClient(f"mongodb+srv://admin:{mongo_db_key}@cluster0.3r2po1q.mongodb.net/?retryWrites=true&w=majority")
    db = client.chatbot
    collection = db.trivia
    
    llm = OpenAI(temperature=0.1)
    wiki_wiki = wikipediaapi.Wikipedia('trivAI_user_agent', 'en')

    application = ApplicationBuilder().token(telegram_api_key).build()
    
    start_handler = CommandHandler('start', start)
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), echo)

    application.add_handler(start_handler)
    application.add_handler(echo_handler)

    buttons = [[KeyboardButton("Tell me some more trivia!")], [KeyboardButton("Tell me more about this!")], [KeyboardButton("I like this fact!")]]

    application.run_polling()

