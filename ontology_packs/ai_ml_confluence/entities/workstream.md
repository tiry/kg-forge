### `entities_extract/workstream.md`
# ID: workstream
## Name: Workstream or Initiative
## Description:
A workstream is a named, ongoing initiative or project that typically spans multiple teams or components.
It often represents a roadmap theme, an investment area, or a cross-cutting effort.

Extract a "workstream" when:
- The text uses a recognizable label for an initiative or theme (e.g. "AI Safety workstream", "Scalability Benchmarking", "CIC Connectors initiative").
- The discussion is about planning, prioritization, or coordination around that initiative.

## Relations
  - product : targets_product : driven_by_workstream
  - component : changes_component : changed_by_workstream
  - engineering_team : led_by_team : leads_workstream
  - engineering_concern : addresses_concern : concern_of_workstream
  - engineering_domain : rooted_in_domain : domain_for_workstream
  - ai_ml_domain : uses_ai_capability : ai_capability_for_workstream

## Examples:

### AI Safety Workstream
The "AI Safety workstream" coordinates efforts around guardrails, red-teaming, and policy enforcement for all AI features.

### Scalability Benchmarking Initiative
The "Scalability Benchmarking" initiative aims to demonstrate that HXPR/KD can operate at billions-of-documents scale.

### CIC Connectors Initiative
The "CIC Connectors" workstream focuses on building and standardizing connectors to external repositories (Nuxeo, Alfresco, OnBase, etc.).
