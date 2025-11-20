# ID: ai_ml_domain
## Name: AI / ML Domain
## Description:
An "AI / ML domain" is a conceptual area of AI/ML practice, such as:
- Retrieval-Augmented Generation (RAG),
- LLMs and prompting,
- fine-tuning,
- evaluation,
- observability / monitoring,
- safety / red-teaming.

Extract an "ai_ml_domain" when:
- The text discusses one of these areas as a topic (not just naming a specific model).

## Relations
  - product : applied_in_product : uses_ai_domain
  - component : applied_in_component : uses_ai_domain
  - workstream : focuses_on_domain : domain_of_workstream
  - technology : contains_technology : belongs_to_ai_domain
  - engineering_concern : overlaps_with_concern : concern_in_ai_domain

## Examples:

### Retrieval-Augmented Generation (RAG)
"RAG" is discussed as the pattern used to combine vector search with LLMs on top of the Content Lake.

### Fine-tuning
"Fine-tuning" is referenced as a capability we want to support on customer data.

### Evaluation and Observability
"LLM evaluation and observability" is mentioned as a focus area for tooling and metrics.
