# ID: component
## Name: Service or Component
## Description:
A "component" is a technical building block used *inside* products or services.
It can be:
- a microservice,
- a backend component,
- a pipeline stage,
- a storage or indexing component,
- or a well-identified internal subsystem.

Extract a "component" when:
- The text refers to a specific part of the system that is smaller than a product.
- It has a recognizable name or role in the architecture (e.g. "Context Engine indexer", "embedding pipeline", "tenant manager", "vector store").

Avoid treating generic technology names (e.g. "PostgreSQL", "MongoDB", "Redis") as components; those are usually "technology" entities.

## Relations
  - product : belongs_to_product : uses_component
  - component : depends_on_component : dependency_of_component
  - technology : implemented_with_tech : tech_used_by_component
  - engineering_team : owned_by_team : owns_component
  - engineering_domain : related_to_domain : domain_for_component
  - engineering_concern : addresses_concern : concern_of_component

## Examples:

### Embedding Pipeline
The "embedding pipeline" is the internal component that computes vector representations for documents and stores them in the vector index.

### Tenant Manager
The "Tenant Manager" is a shared component responsible for provisioning and managing tenants across products.

### Content Ingestion Service
The "content ingestion service" is a microservice responsible for importing documents and pushing them into KD or KE.

