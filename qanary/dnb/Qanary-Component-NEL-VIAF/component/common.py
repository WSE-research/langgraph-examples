import os
import json
import logging

from openai import OpenAI
from qanary_helpers.qanary_queries import query_triplestore


logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_API_BASE = os.environ.get('OPENAI_API_BASE')
MODEL_NAME = os.environ.get("MODEL_NAME")
NEL_SPARQL_ENDPOINT = os.environ['SPARQL_ENDPOINT']

client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_API_BASE,
)

def llm_ner(text):
    """
    Perform Named Entity Recognition (NER) on the given text using a language model.
    Args:
        text (str): The input text to analyze for named entities.
    Returns:
        list: A list of recognized named entities. If the response cannot be parsed as JSON, an empty list is returned.
    Example:
        >>> llm_ner("Show me works created by Friedrich Schiller")
        ["Friedrich Schiller"]
    Note:
        This function uses a language model to perform NER and expects the model to return the recognized entities
        in a structured JSON format. If the response is not valid JSON, an error is logged and an empty list is returned.
    """

    example_string = "Show me works created by Friedrich Schiller"
    assistant_docstring = """["Friedrich Schiller"]"""

    chat_response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": """You are a Named Entity Recognition Tool.
Recognize named entities and output the structured data as a LIST. **Output ONLY the structured data.**
Below is a text for you to analyze."""},
            {"role": "user", "content": example_string},
            {"role": "assistant", "content": assistant_docstring},
            {"role": "user", "content": text}
        ]
    )

    result = chat_response.choices[0].message.content
    
    logging.info("LLM NER Result: %s", result)

    try:
        return json.loads(result)
    except json.JSONDecodeError:
        logging.error("JSONDecodeError: %s", result)

    return []


def dbpedia_search(label, lang="de"):
    """
    Searches for VIAF IDs in a DBpedia triplestore based on a given label and language.
    Args:
        label (str): The label to search for in the DBpedia triplestore.
        lang (str, optional): The language of the label. Defaults to "de".
    Returns:
        list: A list of VIAF IDs that match the given label and language.
    """

    query = f"""
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?viaId WHERE {{
            ?s rdfs:label "{label}"@{lang} .
            ?s owl:sameAs ?viaId .
            FILTER REGEX(?viaId, "^http://viaf", "i")
        }}
    """

    entity_result = query_triplestore(NEL_SPARQL_ENDPOINT, query)
    entities = []

    for bind in entity_result["results"]["bindings"]:
        entities.append(bind["viaId"]["value"])

    return entities
