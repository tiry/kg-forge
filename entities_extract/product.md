# ID: product
## Name: Software Product
## Description:
A software product is a distinct, named solution we build and ship.
Examples in our ecosystem include Knowledge Enrichment (KE), Knowledge Discovery (KD), and Agent Builder (AB).

Extract a "product" when:
- The text is clearly talking *about* that product (its roadmap, architecture, usage, issues, etc.).
- The product is mentioned by its full name or its common acronym (e.g. "Knowledge Discovery", "KD").

Do NOT create a product entity for generic terms like "API", "service", or "dashboard" unless they are clearly the name of a specific product.

## Relations
  - component : uses_component : component_used_by_product
  - workstream : driven_by_workstream : workstream_targets_product
  - engineering_team : owned_by_team : owns_product
  - engineering_domain : related_to_domain : domain_for_product
  - engineering_concern : addresses_concern : concern_of_product
  - ai_ml_domain : uses_ai_capability : ai_capability_used_by_product

## Examples:

### Knowledge Discovery (KD)
Knowledge Discovery (KD) is our core product for search and exploration on top of the Content Lake.

### Knowledge Enrichment (KE)
KE provides enrichment and classification capabilities that can be plugged into multiple products.

### Agent Builder (AB)
AB (Agent Builder) is the product our customers use to define and orchestrate AI agents on top of their content.
