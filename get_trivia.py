import requests
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz
from langchain.llms.openai import OpenAI
from wikipediaapi import Wikipedia, WikipediaPage
from pymongo.database import Database

def get_random_doc_from_db(db):
    """
    Return a random document containing a trivia fact from MongoDB collection

    Keyword arguments:
    None
    """
    res = db.trivia.aggregate([
        {
            "$sample": {
            "size": 1
            }
        }
    ])

    res = list(res)[0]

    return res


def get_wiki_details(wiki_connection: Wikipedia, article_name: str) -> WikipediaPage | str | str:
    wiki_page = wiki_connection.page(article_name.strip())
    wiki_url = wiki_page.fullurl
    text_content = wiki_page.summary if len(wiki_page.text) > 2000 else wiki_page.text
    text_content = text_content.split(sep="\n\nReferences")[0].replace("\n", " ").replace(r"\\", "").replace("== References ==", "")
    return wiki_page, wiki_url, text_content


def get_random_trivia_from_db(wiki_connection: Wikipedia, db: Database)  -> str | str | str | str:
    """
    Return trivia that exists in MongoDB collection

    Keyword arguments:
    None
    """
    trivia_from_db = get_random_doc_from_db(db)
    article_name = trivia_from_db["article_name"]
    full_text = wiki_connection.page(article_name.strip()).summary
    result = trivia_from_db["result"]
    wiki_url = trivia_from_db["wiki_url"]
    return article_name, full_text, result, wiki_url


def get_random_trivia(wiki_connection: Wikipedia, llm: OpenAI, db: Database) -> str | str | str | str:
    """
    Extract trivia from a random Wikipedia article.

    Keyword arguments:
    None
    """
    url = requests.get("https://en.wikipedia.org/wiki/Special:Random")
    soup = BeautifulSoup(url.content, "html.parser")
    article_name = soup.find(class_="firstHeading").text
    wiki_page, wiki_url, text_content = get_wiki_details(wiki_connection, article_name)
    result = None

    if wiki_page.exists() and len(text_content) > 300:
            wiki_query = f"Find an interesting piece of trivia in this text. Do not use the word trivia. Use only information in this text: {text_content}"
            try:
                result = llm(wiki_query)
            except:
                return get_random_trivia_from_db(wiki_connection, db)

            if fuzz.partial_ratio(text_content, result) < 70:
                print("Fuzzy matching failed, fall back to trivia from db.")
                return get_random_trivia_from_db(wiki_connection, db)
    else:
        print("Getting new trivia")
        return get_random_trivia_from_db(wiki_connection, db)
    return article_name, text_content, result.strip(), wiki_url
    

def get_specific_trivia(article_name: str, wiki_connection: Wikipedia, llm: OpenAI) -> str | str | str | str:
    """
    Extract trivia from a named Wikipedia article.

    Keyword arguments:
    article_name -- name of the Wikipedia article the trivia should come from
    """
    wiki_page = None
    try:
        wiki_page, wiki_url, text_content = get_wiki_details(wiki_connection, article_name)
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