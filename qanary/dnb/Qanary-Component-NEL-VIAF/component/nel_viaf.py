import os
import json
import logging

from openai import OpenAI
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from qanary_helpers.qanary_queries import insert_into_triplestore, get_text_question_in_graph
from component.common import llm_ner, dbpedia_search


logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)

if not os.getenv("PRODUCTION"):
    from dotenv import load_dotenv
    load_dotenv() # required for debugging outside Docker


SERVICE_NAME_COMPONENT = os.environ['SERVICE_NAME_COMPONENT']
LANG = os.environ['LANG']



headers = {'Content-Type': 'application/json'}

router = APIRouter(
    tags=[SERVICE_NAME_COMPONENT],
    responses={404: {"description": "Not found"}},
)

@router.post("/annotatequestion")
async def qanary_service(request: Request):
    request_json = await request.json()
    triplestore_endpoint_url = request_json["values"]["urn:qanary#endpoint"]
    triplestore_ingraph_uuid = request_json["values"]["urn:qanary#inGraph"]
    # get question text from triplestore
    question_text = get_text_question_in_graph(triplestore_endpoint_url, triplestore_ingraph_uuid)[0]['text']
    question_uri = get_text_question_in_graph(triplestore_endpoint=triplestore_endpoint_url, graph=triplestore_ingraph_uuid)[0]['uri']

    logging.info("Identifying named entities for question: %s", question_text)
    entities = llm_ner(question_text)

    viaf_ids = []
    for entity in entities:
        logging.info("Querying endpoint for: %s", entity)
        viaf_ids.extend(dbpedia_search(entity, LANG))

    logging.info("Endpoint response: %s", viaf_ids)

    for viaf_id in viaf_ids:
        sparql_query = f"""
                        PREFIX dbr: <http://dbpedia.org/resource/>
                        PREFIX dbo: <http://dbpedia.org/ontology/>
                        PREFIX qa: <http://www.wdaqua.eu/qa#>
                        PREFIX oa: <http://www.w3.org/ns/openannotation/core/>
                        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
                        INSERT {{
                        GRAPH <{triplestore_ingraph_uuid}> {{
                            ?newAnnotation rdf:type qa:AnnotationOfEntity ;
                                oa:hasBody <{viaf_id}> ;
                                qa:score \"1.0\"^^xsd:float ;
                                oa:annotatedAt ?time ;
                                oa:annotatedBy <urn:qanary:{SERVICE_NAME_COMPONENT.replace(" ", "-")}> ;
                                oa:hasTarget [ 
                                    a    oa:SpecificResource ;
                                    oa:hasSource <{question_uri}> ;
                                ] .
                            }}
                        }}
                        WHERE {{
                            BIND (IRI(str(RAND())) AS ?newAnnotation) .
                            BIND (now() as ?time) 
                        }}
                    """

        insert_into_triplestore(triplestore_endpoint_url,
                                sparql_query)  # inserting new data to the triplestore

    return JSONResponse(content=request_json)


@router.get("/health")
def health():
    return PlainTextResponse(content="alive")
