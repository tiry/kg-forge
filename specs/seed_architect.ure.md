# Architecture Seed – KG Forge CLI & Knowledge Graph

This document describes the **technical architecture** for a CLI tool that:

- **ingests** unstructured content,
- **extracts entities/topics** via an LLM or Knowledge Enrichment (KE) backend,
- **populates a Neo4j-backed Knowledge Graph**,
- **queries** entities and related chunks,
- **renders** the graph for exploration.

The system is designed as an **experimental playground** to learn:

- how to extract meaningful entities/topics from content,
- how to store/merge/prune a KG,
- how to design and iterate on a useful ontology.

---

## 1. Goals & Scope

### 1.1 What We Want to Build

A **Python CLI tool** with three primary subcommands:

- `ingest`
  - extract entities/topics from input content,
  - populate/update a Knowledge Graph.
- `query`
  - get entities associated with a chunk (Doc),
  - find related chunks via graph traversal.
- `render`
  - render the graph to HTML,
  - provide a way to navigate the graph visually.

The main goal is to help us **figure out how to build a Knowledge Graph from existing unstructured data** (starting from a Confluence HTML export), and to iterate quickly on ontology + extraction strategies.

### 1.2 Scope of Experimentation

The system should provide a **simple end-to-end pipeline** so we can focus on:

- **KG creation & usage**, not infrastructure plumbing.

For this project:

- `ingest` source = **filesystem** with folders and HTML pages  
  (e.g. a **Confluence site HTML export**).

For the first step, we want **basic implementations** with minimal external dependencies:

- curate text: simple HTML → curated text extraction,
- extract entities: REST call to **Bedrock** (via LlamaIndex client) using a configurable prompt template,
- auto-determine topics: same Bedrock call / prompt template.

The primary focus areas:

- storing/updating the graph,
- pruning/merging entities,
- iterating on ontology.

In the long term, we may:

- use a **KnowledgeEnrichment SaaS API** to run the full orchestrated pipeline,
- use a **Content Lake** as the storage system.

The architecture must therefore be **modular**, with clear boundaries so that backends (LLM vs KE API, filesystem vs Content Lake, etc.) can be swapped.

---

## 2. Technology & Dependencies

### 2.1 Languages & Tools

- **Language:** Python
- **Environment:**
  - Use `venv` for virtual environments.
  - Use `pip` and a `requirements.txt` to manage dependencies.
- **Testing:**
  - Use `pytest` as the test framework.
  - Generate test data under `tests/data` as needed.
  - Aim for good test coverage, especially around:
    - HTML curation,
    - entity-definition loading,
    - LLM prompt & parsing logic,
    - graph schema operations.

### 2.2 Core Libraries

- **CLI:** `click`
- **Graph DB:** Neo4j (official Python driver)
- **Graph Visualization:** `neovis.js` (via generated HTML)
- **LLM & KG Integration:** **LlamaIndex**
  - Use LlamaIndex **KnowledgeGraphIndex** plugged into Neo4j where helpful.
  - Use LlamaIndex **Bedrock client** for LLM calls.
- **Environment Configuration:**
  - Use `.env` for configuration (e.g., via `python-dotenv` or similar).

### 2.3 Configuration

Parameters such as:

- Bedrock credentials (access keys / region),
- Neo4j location & credentials,
- Bedrock model name,

are provided via a `.env` file.

- Provide `.env.example` as a template.
- The CLI must read configuration from `.env` (and can allow overrides via flags where relevant).

---

## 3. High-Level Architecture

### 3.1 Pipeline Overview

1. **Ingestion Source**
   - Read from a folder of HTML files and subfolders.
   - Typically a Confluence HTML export.

2. **Curation (HTML → Curated Text)**
   - Convert HTML to markdown-ish text:
     - Keep visible HTML text, headings, and list items.
     - Remove elements with CSS classes:
       - `header`, `sidebar`, `nav`, and Confluence export boilerplate.
   - **Chunking**:
     - Start with **one page = one chunk** (one `Doc` node per HTML page).

3. **Ontology / Entity-Type Loading**
   - Load entity & topic definitions from `entities_extract/*.md` (see §4).

4. **LLM / KE-based Extraction**
   - Build a prompt from:
     - `entities_extract/prompt_template.md`, and
     - concatenated entity-type definitions.
   - Call Bedrock via LlamaIndex client.
   - Parse output into a JSON-like metadata structure:
     {
       "entities": [
         {
           "type": "Product",
           "name": "Knowledge Discovery",
           "confidence": 0.92
         },
         {
           "type": "EngineeringTeam",
           "name": "Platform Engineering",
           "confidence": 0.89
         }
       ]
     }

5. **Extensibility Hooks (Optional Transform & Cleanup)**
   - `process_before_store(content, metadata, kg_client)`:
     - last step before writing to the KG.
   - `process_after_batch(entities, kg_client, interactive_session)`:
     - batch cleanup / dedup / pruning after ingest completes.

6. **Graph Storage**
   - Persist into Neo4j using a **simple property graph schema**:
     - `:Doc` and `:Entity` nodes,
     - `:MENTIONS` and typed `:RELATION` relationships,
     - all scoped by `namespace`.
   - Optionally expose this to LlamaIndex KnowledgeGraphIndex.

7. **Query & Render**
   - `query` CLI:
     - list entity types, entities, docs, related docs.
   - `render` CLI:
     - export a subgraph to HTML & visualize with neovis.js.

8. **Experimentation & Iteration**
   - Adjust entity definitions, prompts, hooks.
   - Re-ingest with `--dry-run` or new `--namespace`.
   - Observe impact in Neo4j & rendered graph.

---

## 4. Ontology Source – `entities_extract/` Definitions

This section defines how we describe **entity types** and **topics** that the LLM should extract, and how those definitions are used to build prompts and the graph.

---

### 4.1 Entities & Topics

Entities and topics are defined as **markdown files** in a dedicated folder:

entities_extract/
  product.md
  component.md
  workstream.md
  team.md
  engineer.md
  domain.md
  concern.md
  topic.md
  ...

For v1:

- We treat **entities and topics the same way** in the pipeline.
  - **Entities** are often explicitly named in text (e.g., product names, team names).
  - **Topics** may not appear verbatim and are usually inferred from context.
- In the graph, both are stored as `:Entity` nodes; the distinction is via `entity_type` (e.g., `"Product"`, `"Topic"`).

Typical entity types (not exhaustive):

- Software product  
- Service / component  
- Technology  
- Engineering team  
- Engineer  
- Engineering domain (Architecture, Platform Eng, CI/CD, QA, …)  
- Engineering concern (Security, AI Safety, Scalability, Robustness, …)  
- AI/ML domain (RAG, LLMs, fine-tuning, evaluation, observability, …)  
- Topic (generic concept)


---

### 4.2 Entity Definition File Structure

Each markdown file in `entities_extract/` describes **one entity type** and provides example values and relations.

Canonical structure:

# ID: <unique_type_identifier>
## Name: <Label for the entity type>
## Description: <Text description provided to LLM for extraction>
## Relations
  - <linked_entity_type_1> : <to_label> : <from_label>
  - <linked_entity_type_2> : <to_label> : <from_label>
## Examples:

### <example 1>
<additional description>

### <example 2>
<additional description>

Semantics:

- `ID`  
  - Becomes the `entity_type` value in the graph (e.g. "Product", "EngineeringTeam").
- `Name`  
  - Human-friendly label for the type (used in prompts/docs).
- `Description`  
  - Text fed to the LLM to explain what this entity type is and how to recognize it.
- `Relations`  
  - Defines **schema-level relations** between this entity type and others.
  - Format:  
    OtherType : TO_LABEL : FROM_LABEL
  - Example in `team.md`:
    Product : WORKS_ON : WORKED_ON_BY
    means the canonical graph relation is:
    (Team)-[:WORKS_ON]->(Product)
- `Examples`  
  - Realistic examples to anchor the LLM’s understanding.

---

### 4.3 Prompt Template & ENTITY_TYPE_DEFINITIONS

We maintain a prompt template:

entities_extract/prompt_template.md

This file contains the **base prompt** used for LLM extraction, including a placeholder:

... prompt text ...

You must strictly follow these definitions:

{{ENTITY_TYPE_DEFINITIONS}}

At runtime:

- The system:
  - Loads all `entities_extract/*.md` files (excluding `prompt_template.md`),
  - Concatenates their markdown content into a single string,
  - Replaces `{{ENTITY_TYPE_DEFINITIONS}}` in `prompt_template.md` with that string.
- The resulting prompt is what we send to the LLM (along with the curated document text) via the extraction backend.

This ensures the LLM always sees **the current ontology** as markdown text.

---

### 4.4 Validation & Tolerance

We intentionally keep validation **lightweight** to support fast iteration.

Rules:

- **Required field**
  - Only `ID` is strictly required.
  - If `ID` is missing, it should **default to the filename** (without extension).
- **Optional fields**
  - `Name`, `Description`, `Relations`, `Examples` are optional.
  - If present, they are included in the concatenated definitions.
  - If absent, the file is still valid; it just contributes less guidance.
- **No hard schema enforcement**
  - We do not block ingestion if a definition file is “imperfect”.
  - The system should:
    - log parsing problems at debug level,
    - skip only the broken parts, not the entire pipeline.

This design lets us rapidly tweak definitions without constantly fighting validation.

---

### 4.5 Round-trip: Graph → Markdown (export-entities)

As ingestion runs, we will **discover new entities** from content that are not yet curated in `entities_extract/`.

To support iterative ontology improvement:

- Provide an `export-entities` CLI command that:
  - Reads entities from Neo4j (`:Entity` nodes),
  - Groups them by `entity_type`,
  - Generates / updates markdown files under `entities_extract/` for each type.

Expected behaviour:

- For each `entity_type`, e.g. "Product":
  - Create or update `entities_extract/product.md`.
  - Append newly discovered `name` values as additional examples (or in a dedicated "Discovered" section).

This enables a virtuous loop:

1. Define initial types and examples in markdown.
2. Ingest content, discover more entities.
3. Export entities back to markdown.
4. Curate and refine those definitions.
5. Re-ingest with improved ontology.

This round-trip is critical for the **“experiment, observe, refine”** workflow that this CLI is designed to support.

---

## 5. LLM Call & KE Abstraction

### 5.1 Abstraction Layer

We define an **abstraction** responsible for:

- Extracting **entities** and **topics** from curated content.
- Being swappable between:
  - the current LLM implementation (Bedrock via LlamaIndex client),
  - a future **KnowledgeEnrichment SaaS API**.

Conceptually:

class ExtractionBackend:
    def extract(self, content: str, entity_type_definitions: str) -> dict:
        """Returns a dict like {"entities": [...]} as per pipeline output spec."""

### 5.2 LlamaIndex + Bedrock (Initial Backend)

- Use LlamaIndex **Bedrock client** to:
  - construct a prompt from `prompt_template.md` + concatenated entity definitions,
  - call the Bedrock model specified via configuration / --model flag,
  - return JSON-like {"entities": [...]}.

### 5.3 Error Handling Strategy

If the LLM output **cannot be parsed** into the expected JSON:

- Log the error.
- Retry once (with the same prompt).
- Track consecutive failures; if **more than 10 calls fail in a row**:
  - Abort the ingest with a **non-zero exit code**.
- If a single document fails but we have not crossed the threshold:
  - Skip that document,
  - Continue with the rest of the batch.

### 5.4 Call Strategy

- Start with **one LLM call per document**:
  - Ask the model to extract **all entities** in one shot.
- Later iterations can:
  - move to more granular strategies (e.g. per entity-type call),
  - or use multi-pass extraction.

---

## 6. Extensibility Hooks & Human-in-the-Loop

To support experimentation and custom logic, we expose **hooks**.

### 6.1 Hook Registration

- For v1, this can be simple:
  - a Python module containing a list of hook functions (no dynamic plugin system needed).
- Hooks are imported statically and called at well-defined points in the pipeline.

### 6.2 process_before_store

Called **after** LLM extraction and ontology parsing, **before** writing to the KG.

Signature:

def process_before_store(content: str, metadata: dict, kg_client) -> dict:
    """
    content: curated text of the document
    metadata: parsed JSON-like structure, e.g. {"entities": [...]}
    kg_client: client to query/update the KG if needed
    returns: modified metadata
    """

Use cases:

- custom filtering / normalization,
- adding derived attributes,
- pre-merge tweaks before graph persistence.

### 6.3 process_after_batch

Called **at the end of an import batch**.

Signature:

def process_after_batch(entities: list[dict], kg_client, interactive_session) -> None:
    """
    entities: list of entity records that were added to the graph
    kg_client: client to query/update the KG
    interactive_session: object able to ask questions to the user when interactive mode is enabled
    """

Responsibilities:

- Cleanup / prune the KG.
- Experiment with **dedup/merging strategies**, e.g.:
  - misspelled entities,
  - similarly sounding entities (“Catherine J.” vs “Katherine Jones”),
  - abbreviations (“Kubernetes” vs “K8S”),
  - partial names (“James Earl Jones” vs “James Jones”).

### 6.4 Interactive Mode (--interactive / --biraj)

- Add --interactive (alias --biraj) flag to the ingest command.
- In interactive mode:
  - process_after_batch can use interactive_session to:
    - ask questions on the command line,
    - have a **human in the loop** to resolve ambiguous merges/dedup operations.

---

## 7. Knowledge Graph Schema & Storage

We use a **simple property graph schema** with two primary node types and a few relationships.

### 7.1 Node Types

#### 7.1.1 :Doc

Represents an ingested document. In v1, one HTML page = one Doc.

Label

- :Doc

Required properties

- namespace – string, experiment/environment name (e.g. "default").
- doc_id – string, stable ID (e.g. relative path without extension, lowercased).
- source_path – string, relative file path (e.g. "platform/kd/intro.html").
- content_hash – string, MD5 of curated text (used to skip unchanged docs).

Merge key

- (namespace, doc_id)

#### 7.1.2 :Entity

Represents both **entities and topics**.

Label

- Always :Entity.
- Optionally additional label per type (e.g. :Entity:Product, :Entity:Topic).

Required properties

- namespace – string, experiment/environment name.
- entity_type – string, one of the types defined in entities_extract/*.md
  (e.g. "Product", "Team", "Topic").
- name – string, canonical name (e.g. "Knowledge Discovery").
- normalized_name – string, normalized name for matching.

Normalization:

- lowercase,
- trim whitespace,
- collapse multiple spaces,
- remove punctuation except alphanumeric characters.

Merge key

- (namespace, entity_type, normalized_name)

Topics

- Topics are simply entities with entity_type = "Topic" (and optionally label :Topic).

### 7.2 Relationships

#### 7.2.1 Markdown & Orientation

Canonical direction rule:

- The entity whose .md file defines the relation is the source.

Example from team.md:

Product : WORKS_ON : WORKED_ON_BY
means:

(Team)-[:WORKS_ON]->(Product)

#### 7.2.2 (:Doc)-[:MENTIONS]->(:Entity)

Links a document to the entities (including topics) mentioned in it.

Required properties

- namespace – string, same namespace as the connected nodes.

Other properties (e.g. confidence) are optional and can be added later.

#### 7.2.3 (:Entity)-[:<RELATION>]->(:Entity)

Domain / ontology relationships between entities (e.g. team works on product, product uses technology).

- Relation type names (e.g. WORKS_ON, USES, etc.) are derived from the Relations section in entity definition markdown.
- Direction is defined by the schema (as described above).
- For v1, always use a **single canonical direction** per relation.

Required properties

- namespace – string, same namespace as the connected nodes.

### 7.3 Namespace

All commands accept --namespace (default "default"), and **always operate only** on nodes and relationships with that namespace.

- namespace is used to:
  - keep different experiments isolated in the same Neo4j database,
  - allow re-ingestion with changed ontology/prompts without clobbering other experiments.

Rules:

- Ingest commands **must set namespace** on all created nodes and relationships.
- Query and render commands **must filter** by the given namespace.

---

## 8. CLI Design & Commands

We use Click to implement a robust, discoverable CLI.

### 8.1 Global Structure

Top-level command exposes subcommands:

- ingest
- query
- render
- render-ontology
- neo4j-start
- neo4j-stop
- export-entities

Common options:

- --namespace (default "default").

### 8.2 ingest Command

Responsibilities:

- Read HTML files from a folder,
- Curate text from HTML,
- Run extraction (LLM/KE abstraction),
- Call hooks (process_before_store, process_after_batch),
- Write graph to Neo4j.

Options:

- --source PATH (required)
  - Folder containing HTML files.
- --namespace TEXT (default "default")
- --refresh (flag)
  - If not set:
    - skip re-import when content_hash is unchanged.
- --dry-run (flag)
  - Run extraction but **do not write** to the graph.
  - Useful for ontology/prompt tweaks.
- --prompt-template PATH
  - Override default entities_extract/prompt_template.md.
- --model TEXT
  - Override default Bedrock model name from config.
- --interactive / --biraj (flag)
  - Enable interactive mode for process_after_batch.

Behaviour:

- For each HTML file under --source:
  - Compute doc_id as:
    - sub-path + filename, lower case, without extension.
  - Curate HTML to text.
  - Compute MD5 content_hash on curated text.
  - If a :Doc already exists with same (namespace, doc_id, content_hash):
    - and --refresh is not provided → skip.
  - Otherwise:
    - run the extraction pipeline (LLM backend),
    - produce metadata {"entities": [...]},
    - call process_before_store,
    - write Doc, Entity, MENTIONS, and domain relationships,
    - collect entities for batch summary.

- After all docs:
  - call process_after_batch with list of entities, kg_client, and interactive_session
    (if --interactive / --biraj is set, interactive_session can ask user questions).

### 8.3 query Command

Subcommands:

- list-types
  - list distinct entity_type values in the namespace.
- list-entities --type Product
  - list entities for a given type.
- list-docs
  - list Docs in the namespace (with optional pagination / filters).
- show-doc --id <chunk-id>
  - show curated text and metadata for a Doc by doc_id.
- find-related --entity "<value>" --type Product
  - find Docs and/or Entities related to a given entity name and type.

Common options:

- --namespace TEXT (default "default")
- --max-results INT (default 10)
- --format TEXT (json | text)

Behaviour:

- All subcommands must:
  - respect --namespace,
  - limit results to --max-results,
  - format output according to --format.

### 8.4 render Command

For rendering, we:

- generate an HTML page that uses neovis.js to display the graph.

Options:

- --namespace TEXT (default "default")
- --out PATH
  - output HTML file (e.g. graph.html).
- --depth INT (default 2)
  - max hop distance from seed nodes.
- --max-nodes INT (default 100, allow larger caps e.g. up to 200).

Behaviour:

- Extract a subgraph from Neo4j (respecting namespace, depth, and node limit).
- Emit HTML + embedded JS that:
  - uses vis.js,
  - connects to Neo4j or uses a pre-fetched dataset,
  - visualizes :Doc and :Entity nodes and relationships.

### 8.4.1 render-ontology Command

For rendering ontology structure visualization:

Options:

- --ontology-pack TEXT
  - ontology pack to visualize (default: active or auto-detected).
- --out PATH
  - output HTML file (default: ontology.html).
- --layout [force-directed|hierarchical|circular|grid]
  - graph layout algorithm (default: force-directed).
- --include-examples
  - include entity examples as additional nodes.
- --theme [light|dark]
  - visualization theme (default: light).

Behaviour:

- Load entity definitions from active ontology pack.
- Build graph data showing entity types and their relationships.
- Generate self-contained HTML file using Cytoscape.js for visualization.
- Support interactive exploration with tooltips, zooming, and layout controls.

### 8.5 Additional Commands

- neo4j-start / neo4j-stop
  - Wrap starting/stopping a local Neo4j process,
  - Helpful for local dev & tests.

- export-entities
  - Read entities from Neo4j,
  - Generate entities_extract/*.md from KG content,
  - Used to sync discovered entities back into ontology files.

---

## 9. Ingestion & Curation Details

### 9.1 Basic HTML → Text Rules

- Use an HTML parser to:
  - keep:
    - visible text,
    - headings,
    - list items.
  - drop:
    - elements with CSS classes:
      - header,
      - sidebar,
      - nav,
      - Confluence export boilerplate.

- Output:
  - curated text suitable as input to the LLM,
  - minimal noise.

### 9.2 Chunking

- Start with **one page = one chunk = one Doc**.
- No semantic chunking / splitting in v1.
- This assumption simplifies the schema and pipeline.

---

## 10. Neo4j & LlamaIndex Integration

### 10.1 Neo4j Layer

Implement a kg_client (e.g. Neo4jClient) wrapping the official Neo4j driver:

- Methods:
  - create/merge :Doc,
  - create/merge :Entity,
  - create/merge :MENTIONS,
  - create/merge :RELATION edges,
  - query for types, entities, docs, related nodes.

Ensure:

- proper indexes/constraints on:
  - (:Doc {namespace, doc_id}),
  - (:Entity {namespace, entity_type, normalized_name}).

### 10.2 LlamaIndex KnowledgeGraphIndex

Use LlamaIndex’s KnowledgeGraphIndex to:

- plug into Neo4j,
- optionally:
  - run experiments on KG building,
  - expose KG to LLMs for higher-level graph queries.

The underlying schema in Neo4j must remain consistent with:

- :Doc,
- :Entity,
- :MENTIONS,
- typed :RELATION edges.

---

## 11. Implementation Plan (Steps 0–8)

We decompose the work into steps that allow us to test, verify, and adjust the spec.

Each step will have its own detailed spec (docs/specs/*.md), tests, and code.

### Step 0 – CLI Skeleton

- Implement the CLI logic:
  - command parsing,
  - help,
  - config loading from .env,
  - top-level subcommands (ingest, query, render, neo4j-start, neo4j-stop, export-entities).
- Add basic unit tests for CLI.
- Add a README.
- No actual processing or LLM calls yet.

### Step 1 – Ontology Management 🎉 **COMPLETED**

- Implement ontology pack system for organizing entity definitions:
  - Dynamic loading and activation of ontology packs.
  - Validation framework for ontology definitions.
  - CLI commands for ontology inspection and management.
  - Extensible architecture for custom ontology formats.
- Add comprehensive test coverage and documentation.

### Step 2 – Ontology Visualization 🎉 **COMPLETED**

- Implement ontology structure visualization using Cytoscape.js:
  - Interactive HTML generation showing entity types and relationships.
  - Multiple layout algorithms (force-directed, hierarchical, circular, grid).
  - Theme support (light/dark) and entity examples integration.
  - CLI render-ontology command with comprehensive options.
- Add comprehensive test coverage:
  - 6 test functions covering all functionality.
  - HTML generation, layout options, theme support, and error handling.
- Self-contained HTML output with no external dependencies.

### Step 3 – Data Curation

- Implement HTML → curated text logic.
- Generate test HTML in tests/data.
- Add tests to verify:
  - unwanted elements are removed,
  - visible text, headings, lists are preserved.

### Step 4 – Load Entity Definitions

- Implement loading of entity definitions from entities_extract/*.md.
- Implement loading & merging of prompt_template.md with entity definitions.
- Unit tests for:
  - parsing ID, Name, Description, Relations, Examples,
  - handling missing optional fields.
- Add CLI command to:
  - load entities and print them to stdout (for inspection).

### Step 5 – Neo4j Bootstrap

- Implement connection to Neo4j.
- Initialize schema:
  - :Doc and :Entity node definitions,
  - indexes/constraints on merge keys.
- Implement CLI command to:
  - create DB structures,
  - initialize graph with loaded entity types (if needed).
- Add unit/integration tests:
  - using Docker-based Neo4j fixture in pytest.
  - implement initial CLI query behaviours (e.g. list-types).

### Step 6 – Plug LLM

- Implement prompt generation from:
  - curated text + merged prompt + entity definitions.
- Implement parsing logic that:
  - converts LLM output → {"entities": [...]}.
- Generate test data:
  - use fake LLM responses for tests.
- Implement the actual Bedrock call via LlamaIndex client.
- Add CLI command to:
  - test model calling with sample data (e.g. test-llm).

### Step 7 – Ingest Pipeline

- Implement full ingestion pipeline:
  - read HTML → curate text → LLM extract → process_before_store → store in KG.
- Implement --dry-run, --refresh, --namespace, and --interactive flags.
- Implement process_after_batch invocation.
- Add end-to-end tests:
  - with fake LLM calls (no real Bedrock).
  - verify Neo4j content matches expectations.
- Refine query behaviour based on early usage.

### Step 8 – Graph Rendering

- Implement render command:
  - subgraph extraction based on namespace, depth, and max_nodes.
  - HTML/JS generation using vis.js.
- Test:
  - HTML is generated,
  - configuration options are respected.

### Step 9 – Further Iterations

- Update this plan as we learn:
  - more granular LLM strategies,
  - better dedup and merging,
  - integration with KE SaaS and Content Lake,
  - advanced graph queries and GraphRAG integrations.
  - expanded ontology visualization features and layouts.

For each step:

- we will write a **detailed spec**,
- implement code + tests,
- only move to the next step when the current one is accepted.
