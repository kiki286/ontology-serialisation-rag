# IDO Assistant - Architecture

## 1. High-Level Design

The IDO Assistant is a **modular web application** that separates core application logic from RAG.

* **Web Application (frontend + backend):** Handles users, queries, history, authentication, and administration.
* **RAG Service (modular API):** Encapsulates retrieval and generation logic. Exposed via a simple API contract.

This separation allows the core application to remain stable while the RAG implementation evolves (vector DB, graph DB, hybrid, etc.).

## 2. Frontend

* **Framework:** React
* **Styling:** Tailwind CSS
* **Responsibilities:**

  * Provide user interface for query input, responses, and feedback.
  * Display query history.
  * Show citations with (optional) expandable source information.
  * Admin dashboard for managing users and monitoring usage.

## 3. Backend

* **Framework:** Django
* **Responsibilities:**

  * Manage users, authentication, and MFA (leveraging Django’s auth system).
  * Expose REST/GraphQL API endpoints to frontend.
  * Store queries, responses+sources, and conversation history in relational DB.
  * Proxy queries to the RAG API via the `answer_query(query, conversation_history)` function.

## 4. Database

* **Relational DB:** PostgreSQL
* **Stored Data:**

  * User accounts & authentication data.
  * Query history (query, answer, timestamp).
  * Feedback (positive/negative).
  * Source metadata returned from RAG API (at minimum: `source_id`, `source_name`, `source_url`).

> Note: RAG storage (embeddings, graphs, document chunks) lives **outside** this database.

## 5. RAG API

* **Core Function Contract:**

```python
result = answer_query(query, conversation_history)
```

* **Return Format (JSON):**

```json
{
  "response": "The Industrial Data Ontology defines ...",
  "sources": [
    {
      "source_id": "doc123",
      "source_name": "IDO Principles v2.1",
      "source_url": "https://storage.example.com/docs/ido_principles.pdf"
    },
    {
      "source_id": "talk2024",
      "source_name": "Tony Seale Talk 2024",
      "source_url": "https://youtube.com/watch?v=xyz&t=230"
    }
  ]
}
```

* **Notes:**

  * Sources are guaranteed to include document-level references (name + URL).
  * Optional enrichment (chunks, scores, graph context) may be added depending on RAG backend.
  * RAG DB may be a vector DB, graph DB, or hybrid. This choice is deferred.

## 6. Deployment

* **Containerisation:** Docker Compose
* **Runtime Environment:** VM (e.g. AWS EC2, Azure VM, Digital Ocean Droplet)
* **Services:**

  * `frontend` (React app)
  * `backend` (Django app + Gunicorn)
  * `postgres` (user data, queries, convo history, etc.)
  * `documents` (raw documents)
  * `rag` (exposes Python function `answer_query` for the `backend` to use)
  * OPTIONAL: (any extra services needed for `rag`, e.g., vector DB or graph DB, or could be stored in cloud elsewhere, e.g., docs may be in S3)

> This setup allows for local development and simple cloud deployment, with potential migration to Kubernetes for scale.

## 7. Future Considerations

* **UI Enhancements:**

  * Option to expand sources to reveal exact text chunks (if available).

* **Monitoring & Logging:**

  * Add metrics and logging (Prometheus/Grafana or SaaS).
  * Track query latency, accuracy, and feedback trends.
