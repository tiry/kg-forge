# Seed – KG Forge CLI (Product Seed)

This document describes *what* we want to build and *why*, from a product perspective. 
The detailed technical design and implementation plan live in `seed_architecture.md`.

---

## 1. Problem & Context

We have a large corpus of unstructured engineering knowledge in Confluence (and similar sources). 
Today we can:

- run keyword or hybrid search over pages, and
- read individual documents in isolation,

but we **cannot see the relationships** between:

- AI/ML domains,
- products and components,
- workstreams and projects,
- teams and engineers,
- engineering domains and concerns.

As a result:

- It is hard to answer questions like:
  - “Which teams are working on RAG-related components for Product X?”
  - “Where are we discussing reliability concerns for the platform?”
  - “Which engineers keep showing up in docs related to observability?”
- It is hard to maintain and grow an ontology of our work:
  - what products exist, their components,
  - which workstreams touch which areas,
  - how concerns like “Security” or “Scalability” surface across docs.

We need a **fast, experimental way** to:

- extract entities and topics from existing documentation,
- put them into a **Knowledge Graph**,
- iterate on the ontology,
- and explore the resulting graph.

---

## 2. Vision

Build a **CLI-based experimentation toolbox** (“KG Forge”) that lets us:

1. **Ingest** unstructured content from a filesystem export (initially Confluence HTML).
2. **Extract entities and topics** using an LLM-based pipeline driven by markdown-based definitions.
3. **Populate and update a Knowledge Graph** in a graph database.
4. **Query** for entities, documents, and relationships.
5. **Render** the graph for visual exploration.

The tool should feel like:

> “A command-line workbench for turning messy docs into a navigable knowledge graph, 
> where ontology, prompts, and graph structure can all be tweaked and re-run quickly.”

It is **not** a production service; it is an **experiment platform** that helps us learn what a full product should eventually do.

---

## 3. Primary Users & Use Cases

### 3.1 Primary Users

- **Ontology / Knowledge Architects**
  - Define entity types and relations.
  - Iterate on schema and examples.
- **ML / AI Engineers**
  - Experiment with LLM prompts and extraction strategies.
  - Validate how well entities and relationships are captured.
- **Platform / Product Engineers**
  - Explore cross-cutting concerns (e.g., which docs/components touch “RAG” or “Scalability”).
- **Product Managers / Tech Leads**
  - Get a structural view of workstreams, components, and teams from existing documentation.

### 3.2 Core Use Cases

1. **Bootstrap a knowledge graph from Confluence**
   - Export a space as HTML.
   - Run `kg-forge ingest` to extract entities and create a graph.
   - Use `kg-forge query` and `kg-forge render` to explore relationships.

2. **Iterate on ontology and entity definitions**
   - Edit markdown definitions for entity types (product, component, team, concern, domain, topic, etc.).
   - Re-run ingestion to see impact on the graph.
   - Export discovered entities back into markdown for curation.

3. **Discover patterns and gaps**
   - Identify which products/components are heavily or sparsely documented.
   - See which workstreams and teams map to which AI/ML domains.
   - Surface recurring concerns (e.g., security) and where they appear.

4. **Prepare for a future production-grade system**
   - Validate what ontology works.
   - Validate what extraction strategies are robust.
   - Produce a reference graph that can inform a future SaaS product 
     using KE APIs and a formal Content Lake.

---

## 4. Scope for v1

v1 is a **single-machine CLI tool** focused on one primary source (filesystem HTML export) and one graph backend.

### 4.1 In-Scope

- **Source**
  - Filesystem folder of HTML pages (Confluence export).
- **Core Commands**
  - `ingest`
    - Read curated text from HTML.
    - Extract entities/topics using an LLM backend.
    - Populate/update a graph database.
  - `query`
    - List entity types, entities, and docs.
    - Show a doc and the entities it mentions.
    - Find docs related to a given entity.
  - `render`
    - Generate an HTML file that visualizes a subgraph for exploration.
- **Ontology Management (Experimental)**
  - Entity-type definitions + examples in markdown files.
  - Relations between entity types defined in markdown.
  - Ability to export graph entities back into markdown for curation.
- **Experimentation Controls**
  - Namespaces to isolate experiments.
  - Dry-run ingestion (run extraction but don’t write to graph).
  - Interactive mode for human-in-the-loop dedup/merge decisions.

### 4.2 Out of Scope (for v1)

- Multi-tenant, production-grade service.
- Real-time ingestion from live Confluence or other systems.
- UI-based ontology editor (only markdown for now).
- Advanced GraphRAG or natural language graph querying.
- Non-HTML sources (PDF, Word, etc.).

---

## 5. Key Concepts

### 5.1 Document

- One curated unit of content (initially: one HTML page).
- Identified by a stable `doc_id` derived from file path.
- Has a relationship to entities it mentions.

### 5.2 Entity / Topic

- An **Entity** is a named thing in our world:
  - product, component, workstream, team, engineer, technology, domain, concern, etc.
- A **Topic** represents a conceptual theme:
  - e.g., “RAG”, “Evaluation”, “Observability”.
- Both are stored as graph nodes with:
  - a type (from markdown definitions),
  - a canonical name,
  - and relationships to other entities and documents.

### 5.3 Ontology

- The ontology is the set of:
  - entity types,
  - allowed relationships between them,
  - and curated examples.
- It is expressed as markdown files in a folder (e.g. `entities_extract/`).
- The ontology is used to:
  - drive LLM extraction (via merged prompt),
  - structure the resulting knowledge graph.

---

## 6. Functional Requirements (Product Level)

### 6.1 Ingest

- As a user, I can run `ingest` on a folder of HTML files and:
  - see how many documents were processed, skipped, or failed.
  - see a summary of entities created/updated.
- I can choose to:
  - **skip unchanged** documents based on a content hash,
  - **force re-processing** via a flag,
  - **run in dry-run mode** to only test extraction and configuration.
- When ingestion finishes, I can optionally be prompted (interactive mode) 
  to resolve ambiguous entities or deduplication suggestions.

### 6.2 Query

- As a user, I can:
  - list all entity types in a namespace.
  - list entities of a given type (e.g., all Products).
  - list all docs in the namespace.
  - show a specific doc by ID, along with the entities it mentions.
  - find docs related to a specific entity (e.g., all docs mentioning Product X).
- Queries should be available in:
  - a human-readable text format, and
  - a machine-readable JSON output (for scripting).

### 6.3 Render

- As a user, I can generate an HTML page that:
  - shows a subgraph (Docs + Entities + relations),
  - can be filtered by depth and maximum node count,
  - allows basic panning/zooming and inspection of node labels.

### 6.4 Ontology Round-Trip

- As a user, I can:
  - define entity types and relations in markdown.
  - re-run ingestion to see how they impact graph structure.
  - export discovered entities back into markdown files for review.

---

## 7. Non-Functional Requirements (Product Level)

- **Fast iteration**
  - Ingestion runs should be fast enough on a typical Confluence space 
    to support multiple iterations per day.
- **Local-first**
  - v1 runs locally on a developer or architect’s machine.
- **Reproducibility**
  - Given the same input content, ontology, and configuration,
    we should be able to rebuild the same graph structure.
- **Debuggability**
  - Clear logs for:
    - ingestion progress,
    - LLM extraction failures,
    - graph write failures.

(Performance, scaling, and fault tolerance beyond a single user/machine 
are explicitly out of scope for v1.)

---

## 8. Success Metrics (for v1 Experiment)

We will consider v1 successful if:

1. **Ontology Iteration**
   - Ontology and entity definitions can be adjusted and re-run easily.
   - Users can visibly see the impact of their ontology changes in the graph.

2. **Entity Extraction Quality (Qualitative)**
   - For a sample of docs, entities and relations look:
     - mostly correct,
     - useful for navigation and analysis,
     - easy to tweak via prompt and markdown changes.

3. **Graph Exploration**
   - At least a handful of real questions about our engineering landscape 
     can be answered more easily via the graph than via raw Confluence search.
     (e.g., “which docs show up under RAG + KD + Platform Engineering?”)

4. **Future Product Readiness**
   - We have enough learnings to specify:
     - what a production-grade KE + Content Lake graph solution should look like,
     - which ontology patterns work,
     - and which entity/relationship types are essential.

---

## 9. Constraints & Assumptions

- v1 is **for internal experimentation only**.
- We assume:
  - Access to a graph database instance (local is fine).
  - Access to an LLM backend (e.g., Bedrock or a KE API) for extraction.
- We accept:
  - Some manual curation and editing of markdown files.
  - Occasional LLM extraction errors, as long as:
    - they are visible,
    - and we can skip/redo documents easily.

---

## 10. Open Questions

- Which exact entity types are *must-have* for the first experiment?
- How fine-grained should “Topics” be?
- To what extent do we want human-in-the-loop deduplication in v1 vs. later?
- How important is export to other tools (e.g., CSV, JSON, or direct KG queries) in v1?

These questions will be refined as we run the first experiments and see how 
the graph behaves on real Confluence exports.
