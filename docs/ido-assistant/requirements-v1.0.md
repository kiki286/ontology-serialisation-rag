# IDO Assistant – Requirements Document

## 1. Introduction

The IDO Assistant is a Retrieval-Augmented Generation (RAG) web application designed to introduce the Industrial Data Ontology (IDO) to businesses.
It supports organisations, especially technology-oriented ones, that want to build IDO-aligned ontologies as part of their infrastructure.

### Purpose

The goal of the IDO Assistant is to lower the barrier for organisations to engage with IDO. Many businesses lack ontology expertise, and the Assistant provides an accessible, interactive way to learn IDO concepts, principles, and use cases.

### Objectives

* Provide accurate, source-grounded answers about IDO.
* Help organisations understand how to align their ontologies with IDO.
* Act as a trusted reference point by minimising hallucinations and surfacing authoritative sources.

### Stakeholders

* **Primary users:** Technology managers, architects, and developers in organisations exploring IDO.
* **Secondary users:** Researchers, educators, and consultants who want to illustrate or share IDO principles.
* **Administrators:** System maintainers responsible for updating sources, monitoring usage, and ensuring performance/security.

## 2. Scope

* **In scope:**

  * Answering questions about IDO concepts, ontology processes, and architecture principles.
  * Providing steps and considerations for building IDO-aligned ontologies.
  * Returning answers grounded in IDO sources.
  * User and admin features (query history, feedback, account management, source maintenance).

  For this pilot:

  * The focus is the overall application architecture, not refining the RAG specifics. An out-of-the-box Naive RAG pipeline will likely be used. 
  * The application shall be designed such that the RAG pipeline is modular and can be altered and replaced with ease.
  * The application will be deployed on an AWS EC2 VM.
  * 1-2 competency questions/answers (in-scope) will be defined to illustrate how CQs may look in a full set. A full set of CQs (out-of-scope) can be used to evaluate the system's ability to answer IDO-relevant queries in the future. 

* **Out of scope:**

  * Automatically generating ontologies.
  * Covering non-IDO ontology standards or unrelated concepts.

## 3. Sources

The Assistant will be grounded on:

* IDO documentation
* IDO principles
* Presentations
* Research papers using IDO
* YouTube talks and transcripts (e.g., PoscCaesar Association https://www.youtube.com/playlist?list=PLxbeHZDUvotn4q64ZT0dkvefpJpwO7CT5)
* Tony Seale’s talks and articles on LinkedIn
* Relevant posts on X (Twitter)

**Source management:** Administrators must be able to add, update, or remove sources with minimal technical effort (see NFR13).

## 4. Functional Requirements (FRs)

(Prioritisation: **M** = Must have, **S** = Should have, **C** = Could have)

* **FR1 (M). Query Input** – Users must be able to submit questions in natural language.
* **FR2 (M). Source-Grounded Responses** – The system must return answers based only on approved IDO sources.
* **FR3 (M). Citation** – Each answer must include references to the specific source(s).
* **FR4a (M). Scope Detection** – The system must explicitly state when a query falls outside IDO.
* **FR4b (S). Out-of-Scope Response** – The system may provide a best-effort answer to out-of-scope queries with a disclaimer to the effect of "IDO sources have not been referred to whilst generating this response"
* **FR5 (M). Feedback Mechanism** – Users must be able to give positive/negative feedback on answers.
* **FR6 (S). History Access** – Users must be able to view, resume, and optionally delete their previous queries.
* **FR7 (M). Document Retrieval** – The system must retrieve and surface relevant IDO documents or snippets, not just generated text.
* **FR8 (M). User Management** – The system must allow account creation, authentication, and MFA-secured login.
* **FR9 (C). Admin Dashboard** – Administrators should be able to:

  * Add/update/remove sources.
  * Set system budget.
  * Monitor system usage (queries (anonymised), feedback trends, COST).
  * Manage user accounts (activate/deactivate).
  * Note for this pilot: admin dashboard not mandatory, but the Django Admin page may suffice. At a minimum, tracking cost is necessary and should be easily accessible by an admin.

## 5. Non-Functional Requirements (NFRs)

(Prioritisation: **M** = Must have, **S** = Should have, **C** = Could have)

* **NFR1 (S). Performance** – Responses must be generated in ≤ 5 seconds under normal load (95% of requests).
* **NFR2 (M). Scalability** – The system must support ≥ 15 concurrent users without degradation.
* **NFR3 (M). Security** – All queries, documents, and history must be encrypted in transit (TLS 1.3+) and at rest (AES-256).
* **NFR4 (M). Multi-Factor Authentication (MFA)** – User authentication must require MFA (e.g., password + one-time code).
* **NFR5 (M). Usability** – At least 80% of new users must be able to successfully submit a query and receive an answer within 2 minutes, without external help.
* **NFR6 (M). Compatibility** – The system must run on Chrome, Edge, Safari, and Firefox, both desktop and mobile.
* **NFR7 (M). Reliability** – The system must remain available ≥ 99% of the time (measured monthly).
* **NFR8 (M). Accuracy Guardrails** – The system must minimise hallucinations and clearly label speculative or out-of-scope answers.
* **NFR9 (M). Maintainability** – Codebase and configurations must be documented and linted.
* **NFR10 (M). Data Integrity** – Retrieved information must remain unaltered, with exact source attribution preserved.
* **NFR11 (S). Embedded Guidance** – An integrated help section must exist (e.g., tooltips and FAQ).
* **NFR12 (S). Accessibility** – The interface must comply with WCAG 2.1 AA (including screen reader support, keyboard navigation, and high-contrast mode).
* **NFR13 (M). Extensibility** – The system should allow new IDO sources to be added through configuration, without major re-engineering.
* **NFR14 (M). Budget Control** – The system must enforce a query-processing budget. If the budget is exceeded, the system must halt further generation and return a clear message to the user (e.g., "This project is currently self-funded and cannot generate further responses").
