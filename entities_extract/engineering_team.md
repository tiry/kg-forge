# ID: engineering_team
## Name: Engineering Team
## Description:
An engineering team is a stable group of engineers with a shared name and mission
(e.g. "KD team", "Platform Engineering", "AI Safety guild").

Extract an "engineering_team" when:
- The text references a named team or group responsible for a product, component, or workstream.

## Relations
  - product : owns_product : owned_by_team
  - component : owns_component : owned_by_team
  - workstream : leads_workstream : led_by_team
  - engineer : has_member : member_of_team
  - engineering_domain : operates_in_domain : domain_for_team

## Examples:

### KD Team
The "KD team" owns the Knowledge Discovery product and its core services.

### Platform Engineering
The "Platform Engineering" team maintains the shared Kubernetes and deployment tooling.

### AI Safety Guild
The "AI Safety guild" is a cross-functional team focusing on AI safety practices and tooling.
