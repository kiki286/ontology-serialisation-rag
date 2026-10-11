"""RAG chain construction."""

import os
from langchain.chat_models import init_chat_model
from langchain_openai import OpenAIEmbeddings
import faiss
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, PromptTemplate
from langchain.memory import ConversationSummaryMemory
from typing_extensions import List, TypedDict
from langgraph.graph import START, StateGraph
from langchain_core.messages import SystemMessage, HumanMessage
from app.document_loaders import (
    RETRIEVAL_INDEX_FILTER_VERSION,
    filter_retrieval_index_documents,
    load_all_documents,
    load_always_include_documents,
    get_loader_version,
    iter_loadable_data_files,
)
from pathlib import Path
import hashlib
import json

RAG_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = RAG_DIR / "data"
NAIVE_RAG_PROMPT_PATH = RAG_DIR / "prompts" / "naive_rag_prompt.txt"
QUERY_REWRITE_PROMPT_PATH = RAG_DIR / "prompts" / "query_rewrite_prompt.txt"
QUERY_BREAKDOWN_PROMPT_PATH = RAG_DIR / "prompts" / "query_breakdown_prompt.txt"

# Strategy-aware index paths
CHUNKING_STRATEGY = os.getenv("CHUNKING_STRATEGY", "entity-based")
CORPUS_FORMAT = os.getenv("CORPUS_FORMAT", "turtle")
ASSISTANT_CORPUS_MODE = os.getenv("ASSISTANT_CORPUS_MODE", "full")
FAISS_INDEX_PATH = RAG_DIR / "app" / "embeddings" / "db" / CHUNKING_STRATEGY / ASSISTANT_CORPUS_MODE / CORPUS_FORMAT
CHECKSUM_PATH = RAG_DIR / "app" / "embeddings" / f"index_checksum_{CHUNKING_STRATEGY}_{ASSISTANT_CORPUS_MODE}_{CORPUS_FORMAT}.json"

RETRIEVAL_K = int(os.getenv("RETRIEVAL_K", 4))
VECTOR_BATCH_SIZE = 100

memory = None

def compute_data_checksum():
    """Compute SHA256 hash of all files in the data directory, plus strategy/format/version."""
    hash_obj = hashlib.sha256()
    loader_version = get_loader_version(CHUNKING_STRATEGY, CORPUS_FORMAT)
    hash_obj.update(
        (
            f"{CHUNKING_STRATEGY}:{ASSISTANT_CORPUS_MODE}:{CORPUS_FORMAT}:"
            f"{loader_version}:{RETRIEVAL_INDEX_FILTER_VERSION}"
        ).encode()
    )
    for filename, file_path in iter_loadable_data_files():
        hash_obj.update(filename.encode())
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                hash_obj.update(chunk)
    return hash_obj.hexdigest()


def load_rag_prompt(path: str) -> ChatPromptTemplate:
    template_str = Path(path).read_text()

    prompt_template = PromptTemplate(
        input_variables=["question", "context", "history"],
        template=template_str,
    )

    human_message = HumanMessagePromptTemplate(prompt=prompt_template)
    return ChatPromptTemplate.from_messages([human_message])


def load_query_rewrite_prompt(path: str) -> ChatPromptTemplate:
    template_str = Path(path).read_text()

    prompt_template = PromptTemplate(
        input_variables=["question", "history"],
        template=template_str,
    )

    human_message = HumanMessagePromptTemplate(prompt=prompt_template)
    return ChatPromptTemplate.from_messages([human_message])


def load_query_breakdown_prompt(path: str) -> ChatPromptTemplate:
    template_str = Path(path).read_text()

    prompt_template = PromptTemplate(
        input_variables=["question"],
        template=template_str,
    )

    human_message = HumanMessagePromptTemplate(prompt=prompt_template)
    return ChatPromptTemplate.from_messages([human_message])


def build_vector_store(embeddings):
    data_checksum = compute_data_checksum()
    index_exists = os.path.exists(FAISS_INDEX_PATH)

    previous_checksum = None
    if os.path.exists(CHECKSUM_PATH):
        previous_checksum = json.loads(Path(CHECKSUM_PATH).read_text()).get("checksum")

    # If checksum differs → rebuild
    if index_exists and previous_checksum == data_checksum:
        print(f"Loading FAISS index from {FAISS_INDEX_PATH}")
        return FAISS.load_local(
            FAISS_INDEX_PATH,
            embeddings,
            allow_dangerous_deserialization=True,
        )

    # Otherwise: rebuild
    print("Creating new FAISS index (data changed)...")
    loaded_docs = load_all_documents()
    docs = filter_retrieval_index_documents(loaded_docs)
    print(f"Loaded docs; indexing {len(docs)} of {len(loaded_docs)} chunks.")

    dim = len(embeddings.embed_query("hello world"))
    index = faiss.IndexFlatL2(dim)
    vector_store = FAISS(
        embedding_function=embeddings,
        index=index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={}
    )

    print("Vectorising...")

    for i in range(0, len(docs), VECTOR_BATCH_SIZE):
        batch = docs[i : i + VECTOR_BATCH_SIZE]
        print(f"Embedding batch {i} → {i + len(batch)} ({len(batch)} docs)")
        vector_store.add_documents(batch)

    vector_store.save_local(FAISS_INDEX_PATH)

    print("Saving new index checksum...")
    Path(CHECKSUM_PATH).write_text(json.dumps({"checksum": data_checksum}, indent=2))

    print("Saved vector embeddings and checksum.")
    return vector_store


def build_rag_chain():
    global memory
    print("Initializing RAG chain...")
    llm = init_chat_model("gpt-4o-mini", model_provider="openai")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    vector_store = build_vector_store(embeddings)
    rag_prompt = load_rag_prompt(NAIVE_RAG_PROMPT_PATH)
    query_rewrite_prompt = load_query_rewrite_prompt(QUERY_REWRITE_PROMPT_PATH)
    query_breakdown_prompt = load_query_breakdown_prompt(QUERY_BREAKDOWN_PROMPT_PATH)
    memory = ConversationSummaryMemory(llm=llm)

    class State(TypedDict):
        question: str
        retrieval_units: List[str]
        context: List[Document]
        history: str
        answer: str

    def load_memory(state: State):
        mem = memory.load_memory_variables({})
        print(mem.get("history", ""))
        return {"history": mem.get("history", "")}

    def rewrite_query(state: State):
        if state["history"] == "":
            print("No conversation history, skipping rewrite.")
            return {"question": state["question"]}
        messages = query_rewrite_prompt.invoke({
            "question": state["question"],
            "history": state["history"],
        })
        rewritten_query = llm.invoke(messages).content.strip()
        return {"question": rewritten_query}

    def break_down_query(state: State):
        messages = query_breakdown_prompt.invoke({"question": state["question"]})
        raw = llm.invoke(messages).content.strip()
        units = [ln.strip() for ln in raw.splitlines() if ln.strip()]

        if not units and raw:
            units = [raw]
        print("Retrieval units:")
        for u in units:
            print(f" - {u}")
        return {"retrieval_units": units}

    def retrieve(state: State):
        units = state.get("retrieval_units") or [state["question"]]

        all_retrieved: List[Document] = []
        for u in units:
            hits = vector_store.similarity_search(u, k=int(RETRIEVAL_K / len(units)))
            for hit in hits:
                if hit not in all_retrieved:
                    all_retrieved.append(hit)

        always_docs = load_always_include_documents()
        all_context = always_docs + all_retrieved

        print(
            f"(from {len(all_retrieved)} hits across {len(units)} units) "
            f"+ {len(always_docs)} always-include docs"
        )

        return {"context": all_context}

    def generate(state: State):
        messages = rag_prompt.invoke({
            "question": state["question"],
            "context": state["context"],
            "history": state["history"],
        })
        response = llm.invoke(messages)
        return {"answer": response.content}

    def save_memory(state: State):
        memory.save_context(
            {"input": state["question"]},
            {"output": state["answer"]},
        )
        history_messages = memory.chat_memory.messages
        print(history_messages)
        return {}

    graph_builder = StateGraph(State)

    graph_builder.add_node("load_memory", load_memory)
    graph_builder.add_node("rewrite_query", rewrite_query)
    graph_builder.add_node("break_down_query", break_down_query)  # NEW
    graph_builder.add_node("retrieve", retrieve)
    graph_builder.add_node("generate", generate)
    graph_builder.add_node("save_memory", save_memory)

    graph_builder.add_edge(START, "load_memory")
    graph_builder.add_edge("load_memory", "rewrite_query")
    graph_builder.add_edge("rewrite_query", "break_down_query")   # NEW
    graph_builder.add_edge("break_down_query", "retrieve")        # NEW
    graph_builder.add_edge("retrieve", "generate")
    graph_builder.add_edge("generate", "save_memory")

    graph = graph_builder.compile()
    return graph


def clear_memory():
    global memory
    if memory:
        memory.chat_memory.messages = []
        memory.buffer = ""
        print("Conversation memory reset.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    ENV_PATH = RAG_DIR.parent / ".env"
    load_dotenv(dotenv_path=ENV_PATH)

    graph = build_rag_chain()

    # First user message
    print("\n--- USER TURN 1 ---")
    query1 = input("User: ")
    result1 = graph.invoke({
        "question": query1,
    })
    print("Assistant:", result1["answer"])

    # Second user message (tests memory)
    print("\n--- USER TURN 2 ---")
    query2 = input("User: ")
    result2 = graph.invoke({
        "question": query2,   
    })
    print("Assistant:", result2["answer"])



