# ID: technology
## Name: Technology
## Description:
A "technology" is a third-party or generic technical building block:
- databases (MongoDB, PostgreSQL),
- cloud services (AWS S3, EKS),
- AI services or models (Claude, GPT-4, Bedrock),
- infrastructure (Kubernetes, Knative),
- frameworks or libraries.

Extract a "technology" when:
- The text names a specific third-party or standard technology used by our products or components.
- It is clearly not one of our own products (KE, KD, AB, etc.).

## Relations
  - product : used_by_product : uses_technology
  - component : used_by_component : uses_technology
  - ai_ml_domain : belongs_to_ai_domain : ai_domain_contains_technology

## Examples:

### AWS S3
"AWS S3" is used as the object storage backend for document binaries.

### MongoDB / DocumentDB
"MongoDB" or "DocumentDB" is the document database used by our repositories.

### GPT-4
"GPT-4" is an LLM used behind the scenes for summarization and question answering features.
