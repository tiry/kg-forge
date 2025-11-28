# Ontology Packs Architecture

## Overview

KG Forge now supports pluggable **Ontology Packs** that decouple the core knowledge graph engine from domain-specific entity definitions. This allows the same KG Forge installation to work across different domains (AI/ML, software engineering, business processes, etc.) by simply switching ontology packs.

## Architecture

```
KG Forge Core (ontology-agnostic)
├── Generic pipeline & schema  
├── Configurable entity loading
├── Pluggable render styles
└── Domain-agnostic CLI

Ontology Packs (pluggable)
├── ai_ml_confluence/           # AI/ML products & teams
├── software_engineering/       # Code & architecture entities  
├── business_processes/         # Business workflows
└── custom_domain/             # Your custom entities
```

## Ontology Pack Structure

Each ontology pack is a directory with the following structure:

```
ontology_packs/
└── my_pack/
    ├── pack.yaml              # Pack metadata & configuration
    └── entities/              # Entity type definitions
        ├── entity_type1.md    # Markdown entity definition
        ├── entity_type2.md    # Another entity type
        └── prompt_template.md # LLM extraction template
```

### pack.yaml Configuration

```yaml
id: my_domain_pack
name: My Domain Ontology
description: Entity definitions for my specific domain
version: 1.0.0
author: Your Name
license: MIT
tags:
  - domain
  - specific

# Visual styling configuration
styles:
  entity_colors:
    EntityType1: "#2ca02c"
    EntityType2: "#ff7f0e"
  
  relationship_colors:
    RELATIONSHIP_TYPE: "#1f77b4"
    
  relationship_styles:
    RELATIONSHIP_TYPE:
      width: 2
      arrows: "to"
      dashes: false
```

## Usage

### List Available Ontology Packs

```bash
kg-forge ontology list
```

### Activate an Ontology Pack

```bash
kg-forge ontology activate ai_ml_confluence
```

### Get Information About a Pack

```bash
kg-forge ontology info ai_ml_confluence
```

### Validate Ontology Pack Structure

```bash
kg-forge ontology validate ai_ml_confluence
```

### Configure Default Ontology Pack

In your `kg_forge.yaml`:

```yaml
app:
  ontology_pack: ai_ml_confluence
  ontology_packs_dir: ontology_packs
```

### Run Ingest with Specific Ontology

The ingest pipeline automatically uses the configured or active ontology pack:

```bash
# Uses configured ontology pack
kg-forge ingest test_data/

# Ontology pack provides entity definitions and styling
kg-forge render --namespace default --out graph.html
```

## Migration from Legacy Entity Definitions

The existing `entities_extract/` directory has been migrated to the `ai_ml_confluence` ontology pack. The system provides automatic fallback to legacy loading if no ontology packs are available.

## Creating Custom Ontology Packs

1. **Create Directory Structure**:
   ```bash
   mkdir -p ontology_packs/my_pack/entities
   ```

2. **Create pack.yaml**:
   ```yaml
   id: my_pack
   name: My Custom Pack
   description: Custom entity definitions
   version: 1.0.0
   ```

3. **Add Entity Definitions**:
   Create `.md` files in `entities/` directory following the existing format.

4. **Add Prompt Template**:
   Create `entities/prompt_template.md` for LLM extraction.

5. **Discover and Activate**:
   ```bash
   kg-forge ontology discover
   kg-forge ontology activate my_pack
   ```

## Benefits

- **Domain Flexibility**: Switch between different entity schemas easily
- **Reusability**: Share ontology packs between teams/projects  
- **Maintainability**: Centralized entity definitions per domain
- **Styling**: Domain-specific visualization styling
- **Extensibility**: Easy to add new domains without core changes

## Backward Compatibility

The system maintains full backward compatibility with existing `entities_extract/` directory usage through automatic fallback mechanisms.