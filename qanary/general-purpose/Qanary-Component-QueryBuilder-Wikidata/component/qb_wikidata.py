import os
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from qanary_helpers.qanary_queries import insert_into_triplestore, get_text_question_in_graph, query_triplestore


logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)

if not os.getenv("PRODUCTION"):
    from dotenv import load_dotenv
    load_dotenv() # required for debugging outside Docker
    
SERVICE_NAME_COMPONENT = os.environ['SERVICE_NAME_COMPONENT']

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
    # question_text = get_text_question_in_graph(triplestore_endpoint_url, triplestore_ingraph_uuid)[0]['text']
    question_uri = get_text_question_in_graph(triplestore_endpoint=triplestore_endpoint_url, graph=triplestore_ingraph_uuid)[0]['uri']

    sparql = f"""
    PREFIX qa: <http://www.wdaqua.eu/qa#> 
    PREFIX oa: <http://www.w3.org/ns/openannotation/core/> 
    SELECT ?entity 
    FROM <{triplestore_ingraph_uuid}> 
    WHERE {{ 
        ?a a qa:AnnotationOfEntity ;
        OPTIONAL {{ ?a oa:hasBody ?entity }} 
    }}
    ORDER BY DESC(?score) LIMIT 1
    """

    logging.info(f"Querying for entities: {sparql}")

    entity_list = []
    
    entity_result = query_triplestore(triplestore_endpoint_url, sparql)

    for bind in entity_result["results"]["bindings"]:
        entity_list.append(bind["entity"]["value"])

    logging.info(f"Entity candidates: {entity_list}")

    for candidate in entity_list:
        # answer_sparql
        answer_sparql = f"""
            PREFIX wikibase: <http://wikiba.se/ontology#>
            PREFIX bd: <http://www.bigdata.com/rdf#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?label ?pLabel ?oLabel WHERE {{
            <{candidate}> rdfs:label ?label .
            <{candidate}> ?p ?o .
            ?o rdfs:label ?oLabel .
            
            ?prop wikibase:directClaim ?p ;
                    rdfs:label ?pLabel .
            
            FILTER(LANG(?pLabel) = 'en')
            FILTER(LANG(?oLabel) = 'en')
            FILTER(LANG(?label) = 'en')
            }}
        """

        answer_sparql = answer_sparql.replace("\n", " ")
        # query candidate
        sparql_AnnotationOfAnswerSPARQL = f"""
            PREFIX dbr: <http://dbpedia.org/resource/>
            PREFIX oa: <http://www.w3.org/ns/openannotation/core/>
            PREFIX qa: <http://www.wdaqua.eu/qa#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            INSERT {{
                GRAPH <{triplestore_ingraph_uuid}>  {{
                    ?newAnnotation rdf:type qa:AnnotationOfAnswerSPARQL .
                    ?newAnnotation oa:hasTarget <{question_uri}> .
                    ?newAnnotation oa:hasBody "{answer_sparql}" .
                    ?newAnnotation qa:score "1.0"^^xsd:float .
                    ?newAnnotation oa:annotatedAt ?time .
                    ?newAnnotation oa:annotatedBy <urn:qanary:{SERVICE_NAME_COMPONENT}> .
                }}
            }}
            WHERE {{
                BIND (IRI(CONCAT("urn:qanary:annotation:answer:sparql:", STR(RAND()))) AS ?newAnnotation) .
                BIND (now() as ?time) .
            }}
        """

        logging.debug(f"SPARQL for query candidates:\n{sparql_AnnotationOfAnswerSPARQL}")

        insert_into_triplestore(triplestore_endpoint_url, sparql_AnnotationOfAnswerSPARQL)

    return JSONResponse(content=request_json)


@router.get("/health")
def health():
    return PlainTextResponse(content="alive") 
