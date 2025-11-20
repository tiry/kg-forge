
## What we want to build

I want to build a CLI tool that can be used to:

 - ingest:
    - extract entities from input content
    - populate a Knowledge Graph
 - query:
    - get entities associated to a chunk of content
    - find related chunks 
 - render graph
    - provides a way to nagivate the graphs

The 3 main sub commands should be `ingest`, `query`, `render`.

The main goal of this CLI is to help us figure out how we can build a Knowledged Graph from existing unstructured data.

## What questions we want to answer

This experiment aims at having a way to easily and quickly extract KG from a corpus of text.
We want to easily be able to ingest content, look at the graph, update the definition and reprocess. 

The type of questions we are trying to answer include:

 - what is the best strategy to extract meaningful entities and topics from content?
 - what is the best strategy to store, organize, merge, prune a Knowledge Graph?
 - how do we create and maintain  useful ontology?

The idea is to use this CLI tool as a way to experiment and tweak as we learn:

 - create a bootstrap ontology and entities 
 - ingest some content and see how this impacts the KG
 - experiment in merging and pruning the KG (remove duplicated, add relations, ...)

## Scope of the experimentation

We want to build a simple end-to-end solution that allows us to focus on the part we really want to experiment with: the Knowledge Graph creation and usage.

For this project, the `ingest` source will be a simple filesystem containing folders and html page.
(This is a Confluence Site html export)

At least as a first step, we want to have very basic implementation of each of the pipeline with as little dependencies on external services:

   - curate text : simple html text extraction should be fine
   - extract entities : rest call to bedrock API using a configurable prompt template
   - auto-determine topics : rest call to bedrock API using a configurable prompt template

The part we really want to focus on are:

   - store graph / update
   - prune / merge entities 

In the long term, we will want to use our KnowledgeEnrichment SaaS API to run the full orchestrated pipeline and use our Content Lake as the storage system.
Our design needs to be modular so we can clearly idenfify responsibilities and replace "backends" as needed later.

## Design Guidelines

### Technology

For the coding

 - python 
 - create a `venv`
 - use pip and define a requirements.txt
 - use pytest

Ensure proper test coverage.
Generate test data when needed in tests/data.

### LLamaIndex / Neo4J

Use llamaindex and the llamaindex KnowledgeGraphIndex plugged to neo4j.

https://developers.llamaindex.ai/python/examples/property_graph/property_graph_neo4j/
https://neo4j.com/labs/genai-ecosystem/llamaindex/

Be sure to update your knowldge to recent version of these frameworks:

@https://developers.llamaindex.ai/python/examples/llm/bedrock/

### LLM call and KE abstraction

We want to have an abstraction that will be responsible for extracting the entities and topics from the content.

We will use LLM and prompts for that, but we want to encapsulate that logic so we can swap it for a call to KE REST API at a later stage.

We can use LLamaIndex client for bedrock to do the current implementation.

If LLM output cannot be parsed:

 - log the error
 - retry once
 - If more than 10 calls fail in a row, abort the ingest with a non-zero exit code
 - otherwise skip the document, and continue

### Entities definitions

The entities and topics to extract are defined in a folder as markdown files:

    entities_extract
      - product.md
      - component.md
      - workstream.md

For this first version, we will consider that entites and topics are defined the same way : the only real difference being that entities can be explicitly named in the input text whereas the topics will probably not be directly integrated in the text itself, but the link must be inferred.

Each file describe a type of entity and provide some examples values:

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

The `ID` from each markdown file is used as the `entity_type` value in the graph.

Entity types can be:

 - A software product
 - A service or component
   - software are composed of services and components
   - services can have components too
 - A technology
   - product, services and components can use a technology
 - An Engineering Team
   - works on a product and on components
   - team has members
 - An Engineer
   - is part of a team
 - An engineering domain
   - Architecture, Platform Engineering, CI/CD, QA
 - An engineering concern
   - Security, AI Safety, Scalability, Robustness
 - A AI/Ml Domain
   - RAG, LLMs, fine-tuning, evaluation, observability

The entities_extract/prompt_template.md contains a prompt template that must be merged with the data from the entities defined in the other md files.

    ... prompt

    You must strictly follow these definitions.

    {{ENTITY_TYPE_DEFINITIONS}}


`ENTITY_TYPE_DEFINITIONS` is the concatenation of the Markdown text from all the emtites definition files.

No validation of the md file is needed, the only strictly required "field" is the ID that should default to the filename. If some fields are not defined, we will still merge the content with the prompt template.

We will start with an "on LLM call" approach: send one prompt asking the LLM to extract all entities.
Later, we can implement a more granular version that use different calls for different types of entities.

NB: While importing content, we will discover new examples of entities, we will need a wait to "dump" all entities stored in the graph back to a markdown format.

### Extensibility

We want to expose a few hooks that can be easily registered.
We can start by having a python file containing a list of the hook functions - no need for a fancy dynamic registration system.

`process_before_store`
Called at the end of the pipeline of "llm extractors" just before persisting the entities in the graph.

The call back should receive:

 - the content
 - metadata is the parsed JSON-like structure produced by the pipeline (e.g. {"entities": [...]})
 - a client to query/update the knowledge graph

The callback should return the modified metadata.

`process_after_batch`
Called at the end of an import.
Used to cleanup / prune the KG graph.

The call back should receive:

 - a list of all entities that were added to the graph
 - a client to query/update the knowledge graph
 - a interactive_session client to interact with the user if the interactive flag was activated

This call back has void return.

### About KG manipulations

Extracting entites from content is the easy part, adding these entities to a KG in a meaningful way is the tricky part.

Inside the `process_after_batch` we may want to experiment with multiple approaches:

 - misspelled entities
 - similarly sounding entities like "Catherine J." instead of "Katherine Jones"
 - abbreviated names like Kubernetes and K8S
 - partial names like James Earl Jones and James Jones
 
To solve some of these issues, we will need "a human im the loop".

For that, let's add a `--interactive` (alias `--biraj`) to force the interactive mode for the `inject` command.
In that mode, the `process_after_batch` code should have a way to access command line to ask questions to the user.

### Configuration

The code will need a few parameters like:

 - credentials to access bedrock
 - neo4j location / credentials
 - bedrock model name

Use a `.env` file for that.
Provide a sample `.env.example`

### Commands

Let's use `Click` to have a nice CLI.

#### `ingest`

Should ingest from folder located by `--source`.
We should use the sub-path/filename (lower case without extension) as `doc_id`.

The import should also compute the md5 digest on the content and keep track of that information.
If re-importing, if the same digest already exist, we can skip the import unless the --refresh flag is activated.

We need a `--dry-run` to run extraction but not write to the graph (useful during ontology/prompt tweaks).

Chunking : We can start with one page = one chunk since I am not sure semantic indexing will be used in this version.

I also want to be able to easily override parameters:

 --prompt-template alternate_prompt_template
 --model bedrock_model_name

#### `query`

We need to be able to:

 - `list-types` : list entity types
 - `list-entities --type Product` : list entities for a type
 - `list-docs`
 - `show-doc --id <chunk-id>`
 - `find-related --entity "<value>" --type Product`

The max result is set using `--max-results` with default at 10.

Output format should be selectable : `--format` <json|text>

#### `render`

For the rendering, the best option is probably to generate an html page and use neovis.js to display the graph.

https://github.com/neo4j-contrib/neovis.js

  - `--out` graph.html
  - `--depth 2` (default 2)
  - `--max-nodes 200` (default 100)

#### Additional commands

I probably need a few more commands

`neo4j-start|neo4j-stop` wrap neo4j start / stop process
`export-entities` generate the markdown files in `entities_extract/` from the content of neo4j 

### Ingestion / Curation

Basic HTML to markdown parsing.
Keep visible HTML text, headings, and list items. Remove elements with CSS classes header, sidebar, nav, or Confluence export boilerplate.

## Graph

### Pipeline output

The output of the ingest pipeline and of all LLM extractor should be similar:

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

### Schema

We use **two node types** and a small set of relationships.

#### Node Types

##### `:Doc`

Represents an ingested document (one HTML page = one Doc).

**Label**

* `:Doc`

**Required properties**

* `namespace` – string, experiment / environment name (e.g. `"default"`).
* `doc_id` – string, stable ID (e.g. relative path without extension).
* `source_path` – string, relative file path (e.g. `"platform/kd/intro.html"`).
* `content_hash` – string, MD5 of curated text (used to skip unchanged docs).

**Merge key**

* `(namespace, doc_id)`

##### `:Entity`

Represents both **entities and topics**.

**Label**

* Always `:Entity`
* Optionally additional label per type (e.g. `:Entity:Product`, `:Entity:Topic`).

**Required properties**

* `namespace` – string, experiment / environment name.
* `entity_type` – string, one of the types defined in `entities_extract/*.md` (e.g. `"Product"`, `"Team"`, `"Topic"`).
* `name` – string, canonical name (e.g. `"Knowledge Discovery"`).
* `normalized_name` – string, normalized name for matching 

Normalize by lowercasing, trimming, collapsing whitespace, and removing punctuation except alphanumeric characters.

**Merge key**

* `(namespace, entity_type, normalized_name)`

Topics are just entities with `entity_type = "Topic"` (and optionally label `:Topic`).


#### Relationships

##### Marrkdown and orientation

Canonical direction: the entity whose .md file defines the relation is the source.

So in team.md, the relation

    Product : WORKS_ON : WORKED_ON_BY

means 

    (Team)-[:WORKS_ON]->(Product)


##### `(:Doc)-[:MENTIONS]->(:Entity)`

Links a document to the entities (including topics) mentioned in it.

**Required properties**

* `namespace` – string, same namespace as the connected nodes.

(Other properties like `confidence` are optional and can be added later.)

##### `(:Entity)-[:<RELATION>]->(:Entity)`

Domain / ontology relationships between entities (e.g. team works on product).

* Relation type names (e.g. `WORKS_ON`, `USES`, etc.) are derived from the `Relations` section in the entity definition markdown.
* Direction is defined by the schema; for v1, use a **single canonical direction** per relation.

**Required properties**

* `namespace` – string, same namespace as the connected nodes.

#### Namespace

All commands accept --namespace, default "default", and operate only on nodes and relationships with that namespace.

The `namespace` is used to keep different experiments isolated in the same Neo4j database.

Ingest commands must set namespace on all created nodes and relationships; query and render commands must always filter by the given namespace.

## Implementation

The first step is to build an implementation plan that decompose the work into steps that allow to test / verify / adjust the spec.

Typically, we could consider:

 - 1: implement the CLI logic 
   - cmd parsing, help, config loading 
   - unit tests
   - readme file
   - no actual processing or LLM calls
 - 2: implement data curation part
   - generate some test data
   - test that parsing is clean
 - 3: load entities definitions
   - load entitie definition from markdown files
   - unit tests   
   - add CLI command to load entities and print in the stdout
 - 4: neo4j bootstrap
   - Connects to Neo4j and init data and schemas
   - add CLI command to create db and init graph with loaded entities  
   - unit tests (use docker and a pytest fixture)
   - implenent CLI basic queries
 - 5: plug LLM
   - implement and test the prompt generation
   - implement the parsing logic
   - generate test data to be able to test without LLM
   - implement the call to BedRock
   - add CLI command to test calling model with sample data
 - 6: ingest pipeline
   - implement the ingestion pipeline : read - extract entities - store in kg
   - end-to-end test with fake LLM calls 
   - at this point we are likely to also refine the query
 - 7: Rendering
   - implement the redering 
 - 8: We will update the plan when we get there

For each step, I want you to write a detailed spec, ask clarifying questions, let me review the new spec and then implement.

We should not move to the next step until I explicitly ask to do so.

