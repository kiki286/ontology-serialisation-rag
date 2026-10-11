import asyncio
from openai import AsyncOpenAI, OpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import AnswerRelevancy, AnswerAccuracy, SemanticSimilarity
from ragas.metrics._factual_correctness import FactualCorrectness
from ragas.dataset_schema import SingleTurnSample
from ragas.embeddings.base import embedding_factory
from ragas.embeddings import OpenAIEmbeddings
from dotenv import load_dotenv
import pandas as pd


async def measure_answer_relevancy(user_input: str, response: str):
    client = AsyncOpenAI()
    llm = llm_factory("gpt-4o-mini", client=client)
    embeddings = embedding_factory(
        "openai",
        model="text-embedding-3-small",
        client=client,
        interface="async",
    )
    scorer = AnswerRelevancy(llm=llm, embeddings=embeddings)
    return await scorer.ascore(user_input=user_input, response=response)


async def measure_answer_accuracy(user_input: str, response: str, reference: str):
    client = AsyncOpenAI()
    llm = llm_factory("gpt-4o-mini", client=client)
    scorer = AnswerAccuracy(llm=llm)
    return await scorer.ascore(
        user_input=user_input, response=response, reference=reference
    )


async def measure_semantic_similarity(reference: str, response: str):
    client = AsyncOpenAI()
    llm = llm_factory("gpt-4o-mini", client=client)
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        client=client
    )
    scorer = SemanticSimilarity(embeddings=embeddings)
    return await scorer.ascore(reference=reference, response=response)


# def measure_context_precision(user_input: str, reference: str, retrieved_contexts: list[str]):
#     scorer = ContextPrecision(llm=llm)
#     result = scorer.score(
#         user_input=user_input,
#         reference=reference,
#         retrieved_contexts=retrieved_contexts
#     )
#     return result

# def measure_context_recall(user_input: str, response: str, reference: str, retrieved_contexts: list[str]):
#     context_recall = LLMContextRecall(llm=llm)
#     sample = SingleTurnSample(
#         user_input=user_input,
#         response=response,
#         reference=reference,
#         retrieved_contexts=retrieved_contexts,
#     )
#     result = context_recall.single_turn_score(sample)
#     return result

# def measure_noise_sensitivity(user_input: str, response: str, reference: str, retrieved_contexts: list[str]):
#     scorer = NoiseSensitivity(llm=llm)
#     result = scorer.score(
#         user_input=user_input,
#         response=response,
#         reference=reference,
#         retrieved_contexts=retrieved_contexts
#     )
#     return result

# def measure_faithfulness(user_input: str, response: str, retrieved_contexts: list[str]):
#     scorer = Faithfulness(llm=llm)
#     result = scorer.score(
#         user_input=user_input,
#         response=response,
#         retrieved_contexts=retrieved_contexts
#     )
#     return result