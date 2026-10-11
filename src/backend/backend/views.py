# backend/views.py
import os
import logging
import requests
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)  # <-- use the Django logger

RAG_URL = os.environ.get("RAG_URL", "http://rag:9000")
ANSWER_QUERY_URL = f"{RAG_URL}/answer_query"
CLEAR_MEMORY_URL = f"{RAG_URL}/clear_rag_memory"

@api_view(["POST"])
def answer_query(request):
    query = request.data.get("query")

    if not query:
        logger.warning("Received request without 'query' field from %s", request.META.get("REMOTE_ADDR"))
        return Response({"error": "Missing 'query' field"}, status=status.HTTP_400_BAD_REQUEST)

    logger.info("Received query from %s: %s", request.META.get("REMOTE_ADDR"), query[:200])

    try:
        rag_response = requests.post(
            ANSWER_QUERY_URL,
            json={"query": query},
            timeout=60,
        )
        rag_response.raise_for_status()

        data = rag_response.json()
        logger.debug("RAG service response: %s", data)
        logger.info("Successfully fetched RAG response for query: %s", query[:100])
        return Response(data)

    except requests.exceptions.Timeout:
        logger.error("Timeout contacting RAG service at %s", ANSWER_QUERY_URL, exc_info=True)
        return Response({"error": "RAG service timeout"}, status=status.HTTP_504_GATEWAY_TIMEOUT)

    except requests.exceptions.RequestException as e:
        logger.error("RAG service error at %s: %s", ANSWER_QUERY_URL, e, exc_info=True)
        return Response({"error": "RAG service error"}, status=status.HTTP_502_BAD_GATEWAY)

    except Exception:
        logger.exception("Unexpected error processing query: %s", query)
        return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
def clear_rag_memory(request):
    logger.warning("Client called backend memory reset endpoint.")

    try:
        res = requests.post(CLEAR_MEMORY_URL, timeout=10)
        res.raise_for_status()
        logger.info("RAG memory cleared.")
        return Response(res.json())

    except requests.exceptions.Timeout:
        logger.error("Timeout contacting RAG clear_memory service.")
        return Response({"error": "RAG clear_memory timeout"}, status=status.HTTP_504_GATEWAY_TIMEOUT)

    except requests.exceptions.RequestException as e:
        logger.error("Error contacting RAG clear_memory: %s", e, exc_info=True)
        return Response({"error": "RAG clear_memory service error"}, status=status.HTTP_502_BAD_GATEWAY)

    except Exception:
        logger.exception("Unexpected error clearing memory")
        return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
