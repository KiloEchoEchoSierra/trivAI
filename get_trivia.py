import logging
import requests
import random
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz
from langchain.llms.openai import OpenAI
from wikipediaapi import Wikipedia, WikipediaPage
from pymongo.database import Database


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


def get_wiki_segment(wikipedia_user_agent, nlp, given_article_name=None):
    """
    Return a segment of a random or given Wikipedia article

    Keyword arguments:
    given_article_name -- Name of a Wikipedia article to get a segment from
    """
    wikipedia_user_agent=wikipedia_user_agent
    if not given_article_name:
        url = requests.get("https://en.wikipedia.org/wiki/Special:Random")
        soup = BeautifulSoup(url.content, "html.parser")
        article_name = soup.find(class_="firstHeading").text
    else:
        article_name = given_article_name
    #article_name = "Berlin"
    wiki_connection = Wikipedia(wikipedia_user_agent, 'en')
    wiki_page = wiki_connection.page(article_name.strip())
    logging.info(wiki_page)
    try:
        wiki_url = wiki_page.fullurl
    except:
        logging.info("Page does not exist")
        return None, None, None
    
    preferred_sections = ["Trivia", "Demographics", "Etymology", "Economy", "History", "Background", "Biography", "Career", "Overview", "Description"]
    if random.randint(0,1):
        random_top_section = abs(random.randint(0, len(preferred_sections)-1)-random.randint(0, len(preferred_sections)-1))
        preferred_sections[random_top_section], preferred_sections[0] = preferred_sections[0], preferred_sections[random_top_section]
    
    delete_sections = ["See also", "Note", "Notes", "References", "External links", "Further reading"]

    sections_in_article = [section.title for section in wiki_page.sections if section.title not in delete_sections]
    #intersection_list = list(set(preferred_sections) & set(sections_in_article))
    intersection_list = [x for x in preferred_sections if x in sections_in_article]
    if not intersection_list:
        intersection_list = sections_in_article
    
    if intersection_list:
        logging.info(f"{article_name} - Using section: {intersection_list[0]}")
        section = wiki_page.section_by_title(intersection_list[0])
        if section.sections:
            random_subsec = random.randint(0, len(section.sections)-1)
            section = section.sections[random_subsec]

    else:
        if not given_article_name:
            logging.info("No Sections found. Rerunning.")
            return get_wiki_segment(wikipedia_user_agent, nlp)
        else:
            logging.info("No Sections found.")
            section = wiki_page.text
            #return None, None, None
    doc = list(nlp(str(section)).sents)
    
    if len(doc) < 3:
        if not given_article_name:
            logging.info("Too short. Rerunning.")
            return get_wiki_segment(wikipedia_user_agent, nlp)
        else:
            doc = list(nlp(str(wiki_page.text)).sents)

    len_of_text = 10

    try:
        random_text_beginning = random.randint(0, len(doc)-len_of_text-1)
    except:
        random_text_beginning = 0
        
    result = str(list(doc)[random_text_beginning:random_text_beginning+len_of_text])
    
    return article_name, result, wiki_url


def get_random_doc_from_db(db: Database) -> dict[str, any]:
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


def get_wiki_details(wiki_connection: Wikipedia, article_name: str) -> tuple[WikipediaPage, str, str]:
    wiki_page = wiki_connection.page(article_name.strip())
    wiki_url = wiki_page.fullurl
    text_content = wiki_page.summary if len(wiki_page.text) > 2000 else wiki_page.text
    text_content = text_content.split(sep="\n\nReferences")[0].replace("\n", " ").replace(r"\\", "").replace("== References ==", "")
    return wiki_page, wiki_url, text_content


def get_random_trivia_from_db(wiki_connection: Wikipedia, db: Database)  -> tuple[str, str, str, str]:
    """
    Return trivia that exists in MongoDB collection

    Keyword arguments:
    None
    """
    trivia_from_db = get_random_doc_from_db(db)
    article_name = trivia_from_db["article_name"]
    #full_text = wiki_connection.page(article_name.strip()).summary
    result = trivia_from_db["result"]
    wiki_url = trivia_from_db["wiki_url"]
    return article_name, result, wiki_url


def get_trivia(wiki_connection: Wikipedia, wikipedia_user_agent, nlp, llm: OpenAI, db: Database, article_name: str | None = None) -> tuple[str, str, str] | tuple[None, None, None]:
    """
    Extract trivia from a random or named Wikipedia article.

    Keyword arguments:
    wiki_connection: 
    article_name -- name of the Wikipedia article the trivia should come from
    """
    article_name, wiki_segment, wiki_url = get_wiki_segment(wikipedia_user_agent, nlp, article_name)

    if wiki_segment:
        wiki_query = f"Find an interesting piece of trivia in this text. Do not use the word trivia. Use only information in this text: {wiki_segment}"
        try:
            result = llm(wiki_query)
        except:
            if not article_name:
                logging.info("ChatGPT failed to retrieve trivia, falling back to trivia from db.")
                return get_random_trivia_from_db(wiki_connection, db)
            else:
                logging.info("ChatGPT failed to retrieve trivia.")
                return None, None, None 
        if not article_name:
            if fuzz.partial_ratio(wiki_segment, result) < 70:
                logging.info("Fuzzy matching score insufficient, falling back to trivia from db.")
                return get_random_trivia_from_db(wiki_connection, db)
            
    else:
        logging.info("Wikipedia article unsuitable for retrieving trivia.")
        return None, None, None 
    return article_name, result.strip(), wiki_url
