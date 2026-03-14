# Cascade Patterns

Pre-built topologies for common Chirp reasoning cascades. Choose a pattern, then customize
the signatures for the specific project.

## 1. Design Language (Fan-out)

One Planner interprets a design brief. Its Reasoning fans out to N domain interpreters.
Best for: multi-discipline projects where one intent drives all systems.

```
[Brief Panel]
      |
  * Planner
      |
      +-- Reasoning --> * Structure
      +-- Reasoning --> * Envelope
      +-- Reasoning --> * Environment
```

**Planner signature example:**
```
pins_in:  ["DesignBrief:string"]
pins_out: ["CeilingHeight:float", "BaySpacing:float", "GlazingRatio:float"]
signature: "design_brief -> ceiling_height, bay_spacing, glazing_ratio"
```

**Downstream signature example (Structure):**
```
pins_in:  ["PlannerReasoning:string", "Span:float"]
pins_out: ["BeamDepth:float", "ColumnDiameter:float", "SystemType:string"]
signature: "planner_reasoning, span -> beam_depth, column_diameter, system_type"
```

## 2. Brief-to-Build (Chain)

Linear cascade where each component reads the previous one's Reasoning.
Best for: sequential design processes where each decision constrains the next.

```
[Brief Panel]
      |
  * Massing --> Reasoning --> * Structure --> Reasoning --> * Envelope --> Reasoning --> * Critic
```

Each component's reasoning accumulates context. The Critic at the end evaluates
the full chain. Note: later components in the chain have richer context because
they receive reasoning that already incorporates upstream decisions.

## 3. Wasp Aggregation Config

Specialized pattern for discrete design with Wasp plugin.
Best for: modular architecture, aggregation-based workflows.

```
[Intent Panel]
      |
  * Aggregation Config
      |
      +-- wall_ratio, opening_ratio --> [Wasp Parts Catalog]
      +-- field_direction, field_strength --> [Wasp Field]
      +-- constraint_mode, target_parts --> [Wasp Aggregation]
      +-- Reasoning --> * Post-Aggregation Critic
```

**Aggregation Config signature:**
```
pins_in:  ["DesignIntent:string", "PartTypes:string", "SiteConstraints:string"]
pins_out: ["WallRatio:float", "OpeningRatio:float", "RoofRatio:float",
           "FieldDirectionX:float", "FieldDirectionY:float", "FieldDirectionZ:float",
           "FieldStrength:float", "ConstraintMode:int", "TargetParts:int"]
signature: "design_intent, part_types, site_constraints -> wall_ratio, opening_ratio, roof_ratio, field_direction_x, field_direction_y, field_direction_z, field_strength, constraint_mode, target_parts"
```

## 4. Multi-Option Exploration

Parallel Planners generate contrasting options from the same brief.
A Comparator reads all Reasoning outputs to evaluate trade-offs.
Best for: early design exploration, presenting options to clients.

```
[Brief Panel]
      |
      +----> * Planner (Conservative)  --> Reasoning --+
      +----> * Planner (Moderate)      --> Reasoning --+--> * Comparator
      +----> * Planner (Bold)          --> Reasoning --+
```

Each planner has the same output pins but different signature phrasing:
- Conservative: `"design_brief -> conservative_ceiling_height, conservative_bay_spacing, ..."`
- Bold: `"design_brief -> ambitious_ceiling_height, generous_bay_spacing, ..."`

The field names in the signature steer the LLM's interpretation. Same inputs, different
semantic framing, different numerical outputs.

## 5. Hybrid (Fan-out + Critic)

Combines fan-out with a downstream Critic that reads ALL Reasoning outputs.
Best for: quality assurance, catching incoherences.

```
[Brief Panel]
      |
  * Planner
      |
      +-- Reasoning --> * Structure  --> Reasoning --+
      +-- Reasoning --> * Envelope   --> Reasoning --+--> * Critic
      +-- Planner Reasoning -------------------------+
```

The Critic receives three Reasoning inputs and cross-checks them:
```
pins_in:  ["PlannerReasoning:string", "StructureReasoning:string", "EnvelopeReasoning:string"]
pins_out: ["Coherent:bool", "Issues:string", "Suggestions:string"]
signature: "planner_reasoning, structure_reasoning, envelope_reasoning -> coherent, issues, suggestions"
```
