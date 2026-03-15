# Chirp — Custom GH Component Research

**Date:** 2026-03-15
**Status:** Research complete, ready for implementation planning
**Context:** [chirp-landscape-exploration.md](2026-03-13-chirp-landscape-exploration.md)

---

## Goal

Build a single `ChirpComponent : GH_Component` class that replaces the current generic script component approach. Every Chirp component on canvas — Planner, Interpreter, Critic, Narrator, Classifier, Gate, Editor — is an instance of this one class, parameterized by category, signature, schema, and pins.

This document captures the full spectrum of GH SDK customization available to us, grounded in API research and real-world examples.

---

## Why Not Script Components

The current architecture uses generic C# script components with injected HTTP-client code. This works but has fundamental limits:

| Limitation | Impact |
|---|---|
| No custom capsule color | All Chirp components look identical to each other and to any other script component |
| No custom icon | No visual category identification |
| No persistent custom attributes | Attribute swaps via reflection are lost on file reopen — GH deserializes the default script component attributes |
| Double-click opens script editor | User sees boilerplate HTTP code, not reasoning |
| No custom right-click menu | Can't add "View Reasoning", "Change Category", etc. |
| No custom wire colors | Reasoning wires look like any other string wire |
| No Message label | No category identifier below capsule |
| Shows as "C# Script" in search | Not discoverable as a Chirp component |
| No custom serialization | Can't persist category, signature, schema, correction history |

A compiled `ChirpComponent` class eliminates all of these.

---

## GH SDK Customization — The Full Spectrum

### Layer 1: The Capsule (Visual Shell)

`GH_Capsule` is the rendered shell of every component. Through a custom `GH_ComponentAttributes` subclass, we control exactly how it draws.

**API Reference:** [GH_Capsule Class](https://mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/T_Grasshopper_GUI_Canvas_GH_Capsule.htm)

#### Render Method Overloads

| Method | What It Does |
|---|---|
| `Render(Graphics, GH_PaletteStyle)` | Render with full style override (fill, edge, text colors) |
| `Render(Graphics, Image, GH_PaletteStyle)` | Render with custom icon image + style |
| `Render(Graphics, Image, Color)` | Render with custom icon + base color (derived colors auto-computed) |
| `Render(Graphics, Color)` | Render with base color override |

#### What We Can Customize

| Capability | Mechanism |
|---|---|
| Solid fill color | `capsule.Render(graphics, Color.FromArgb(…))` — any RGB color per category |
| Gradient fills | Custom `LinearGradientBrush` in `Render()` override |
| Custom border | `GH_PaletteStyle` with configurable edge color + thickness |
| Non-standard shapes | Skip `GH_Capsule`, draw with raw `System.Drawing.Graphics` (paths, ellipses, arbitrary shapes) |
| State-dependent color | Check `Owner.Locked`, `Owner.Hidden`, error state → adjust color |
| Custom icon per category | Override `Icon` property, return different 24×24 `Bitmap` per category |
| Dynamic icon | Return different bitmaps based on component state. Call `DestroyIconCache()` to refresh |
| Message label | `this.Message = "Planner"` — text rendered below capsule by `GH_CapsuleRenderEngine.RenderMessage()` |

#### GH_PaletteStyle

`GH_PaletteStyle` controls the complete color scheme of a capsule:
- Fill color (main background)
- Edge color (border)
- Text color (label rendering)

Custom styles can be created per category:
```csharp
var plannerStyle = new GH_PaletteStyle(
    Color.FromArgb(70, 130, 210),   // blue fill
    Color.FromArgb(50, 100, 180),   // darker border
    Color.White                      // white text
);
```

#### Icon Specifications

- **Size:** 24×24 pixels (Bitmap format)
- **Convention:** 2-pixel empty border, drop-shadow (blur=2px, black, transparency 65/255, 1px right/down offset)
- **Caching:** Icon property is cached after first access. Call `DestroyIconCache()` + canvas redraw to refresh
- **Dynamic:** Can return different bitmaps based on component variables (category, state, etc.)
- **Reference:** [Grasshopper Icons Guide](https://developer.rhino3d.com/guides/grasshopper/grasshopper-icons/)

---

### Layer 2: Layout (Size and Regions)

`Layout()` override in `GH_ComponentAttributes` controls the spatial geometry of the component on canvas.

**API Reference:** [GH_ComponentAttributes.Layout()](https://mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/M_Grasshopper_Kernel_Attributes_GH_ComponentAttributes_Layout.htm)

| Capability | Mechanism |
|---|---|
| Custom size | Set `Bounds` to any `RectangleF` — wider, taller, non-standard proportions |
| Extra interactive regions | Define clickable zones beyond standard input/output grip areas |
| Embedded UI areas | Reserve space inside the capsule for custom content (GraphMapper pattern) |
| Parameter grip spacing | Control positions and spacing of input/output connectors |
| Expandable/collapsible | Toggle between compact and expanded layout based on component state |

#### The GraphMapper Pattern

GraphMapper is the canonical example of extreme layout customization:
1. `Layout()` creates a large capsule with a reserved interactive region
2. `Render()` draws a graph visualization inside that region
3. Mouse handlers enable dragging control points within the graph
4. State (control points, curve type) persists via `Write()`/`Read()`

**This is directly applicable to Chirp.** An expanded mode could show a reasoning preview inside the capsule — text instead of a graph, but the same SDK pattern.

---

### Layer 3: Interaction (Mouse + Menu)

Custom `GH_ComponentAttributes` subclass enables full interactivity within component bounds.

#### Mouse Event Handlers

| Method | What It Enables |
|---|---|
| `RespondToMouseDown(GH_Canvas, GH_CanvasMouseEvent)` | Click detection, drag initiation, button presses inside capsule |
| `RespondToMouseUp(GH_Canvas, GH_CanvasMouseEvent)` | Drag completion, click finalization |
| `RespondToMouseMove(GH_Canvas, GH_CanvasMouseEvent)` | Hover effects, drag operations, cursor changes |
| `RespondToMouseDoubleClick(GH_Canvas, GH_CanvasMouseEvent)` | Open custom editors, toggle modes, expand/collapse |

**For Chirp:** Double-click opens a reasoning viewer panel instead of the script editor. Hover over the reasoning region shows a tooltip with the full reasoning text.

**Limitation:** Mouse events only fire within the component's `Bounds` rectangle. UI elements extending beyond bounds (e.g., dropdown lists) require workarounds.

#### Context Menu Customization

| Method | What It Does |
|---|---|
| `AppendAdditionalComponentMenuItems(ToolStripDropDown)` | Add items between standard Bake and Help entries |
| `AppendMenuItems(ToolStripDropDown)` | Full context menu override (replaces default menu) |

**API Reference:** [Custom Component Options Guide](https://developer.rhino3d.com/guides/grasshopper/custom-component-options/)

**For Chirp — custom menu entries:**
- "View Full Reasoning…" — opens reasoning in a panel
- "Change Category ▸" — submenu: Planner, Interpreter, Critic, Narrator, Classifier, Gate, Editor
- "Edit Signature…" — modify the DSPy signature
- "Reasoning History…" — browse past reasoning outputs
- "Clear Cache" — force fresh LLM call on next solve

**Implementation pattern:**
```csharp
protected override void AppendAdditionalComponentMenuItems(ToolStripDropDown menu)
{
    Menu_AppendItem(menu, "View Full Reasoning…", OnViewReasoning);
    Menu_AppendSeparator(menu);

    var catMenu = Menu_AppendItem(menu, "Change Category");
    foreach (var cat in ChirpCategories.All)
        Menu_AppendItem(catMenu.DropDown, cat.Name, (s, e) => OnChangeCategory(cat));
}
```

#### Tooltip Customization

| Method | What It Does |
|---|---|
| `SetupTooltip(PointF, GH_TooltipDescriptor)` | Populate tooltip with custom content on hover |

**API Reference:** [GH_Attributes.SetupTooltip()](https://mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/M_Grasshopper_Kernel_GH_Attributes_1_SetupTooltip.htm)

**For Chirp:** Hover shows category, signature, last reasoning summary, and latency of the last LLM call.

**Limitation:** SetupTooltip only works for standard layout items. Custom regions beyond component bounds need manual tooltip logic in mouse handlers.

---

### Layer 4: Rendering Channels

The `Render()` method is called once per channel per frame. Drawing happens in four ordered passes:

**API Reference:** [GH_CanvasChannel Enumeration](https://mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/T_Grasshopper_GUI_Canvas_GH_CanvasChannel.htm)

| Channel | Draw Order | What Draws | Chirp Use |
|---|---|---|---|
| **Groups** | 1st (behind all) | Group backgrounds | Background glow/halo effect per category color |
| **Wires** | 2nd | Parameter connections | Custom Reasoning wire color/style |
| **Objects** | 3rd | Components themselves | Main capsule, icon, text, embedded reasoning |
| **Overlay** | 4th (on top) | Floating UI | Category badge, status indicator, "reasoning…" spinner |

**Implementation:**
```csharp
protected override void Render(GH_Canvas canvas, Graphics graphics, GH_CanvasChannel channel)
{
    switch (channel)
    {
        case GH_CanvasChannel.Objects:
            RenderChirpCapsule(graphics);  // Custom colored capsule
            break;
        case GH_CanvasChannel.Overlay:
            RenderCategoryBadge(graphics); // Floating label
            break;
    }
}
```

---

### Layer 5: Wire Customization

| Capability | Mechanism |
|---|---|
| Wire color per parameter type | Custom `IGH_Param` subclass with color property override |
| Wire display mode | `WireDisplay` property on param: `Default`, `Faint`, `Hidden` |
| Custom wire rendering | Handle `CanvasPostPaintWires` event, draw custom wires over defaults |
| Fancy vs plain | GH global setting toggles dashed/continuous styles |

#### Custom Parameter Type for Reasoning

To give Reasoning wires a distinct color, create a custom parameter type:

```csharp
public class GH_ReasoningParam : GH_Param<GH_String>
{
    // Custom wire color — e.g., purple/magenta to distinguish from standard string wires
    public override Color DefaultWireColor => Color.FromArgb(180, 100, 220);
}
```

**Alternative approach:** Handle `CanvasPostPaintWires` event and draw custom wires on top of the defaults. Must be thicker than originals to fully cover them. Less clean but doesn't require a custom param type.

---

### Layer 6: Viewport Preview

**Interface:** `IGH_PreviewObject` (already implemented by `GH_Component`)

| Method | What It Does |
|---|---|
| `DrawViewportWires(IGH_PreviewArgs)` | Draw custom wireframe/curves in Rhino 3D viewport |
| `DrawViewportMeshes(IGH_PreviewArgs)` | Draw custom shaded geometry in Rhino 3D viewport |
| `ClippingBox` | Bounding box for preview frustum culling |
| `Hidden` | Toggle preview visibility |

**For Chirp (future):** A Chirp component could draw its reasoning as 3D text annotations attached to the geometry it's reasoning about. Not essential for v1 but the capability exists.

---

### Layer 7: Serialization (Persistence)

**Interface:** `GH_ISerializable` (inherited from `GH_DocumentObject`)

| Method | What It Does |
|---|---|
| `Write(GH_IWriter)` | Save custom state to GH file binary format |
| `Read(GH_IReader)` | Restore custom state from GH file |

**What Chirp persists:**
- Category (Planner, Interpreter, etc.)
- DSPy signature string
- Output schema (type mapping)
- Pin configuration (names, types, order)
- Last reasoning output (for display before re-solve)
- Correction history (for optimizer training data)
- Adapter endpoint URL
- Cache settings

**Implementation:**
```csharp
public override bool Write(GH_IWriter writer)
{
    writer.SetString("ChirpCategory", _category);
    writer.SetString("ChirpSignature", _signature);
    writer.SetString("ChirpSchema", JsonSerializer.Serialize(_schema));
    writer.SetString("ChirpLastReasoning", _lastReasoning);
    return base.Write(writer);
}

public override bool Read(GH_IReader reader)
{
    _category = reader.GetString("ChirpCategory");
    _signature = reader.GetString("ChirpSignature");
    _schema = JsonSerializer.Deserialize<Dictionary<string, string>>(
        reader.GetString("ChirpSchema"));
    _lastReasoning = reader.GetString("ChirpLastReasoning");
    return base.Read(reader);
}
```

**Key detail:** `Message` property is NOT serialized by GH — it must be reassigned in `Read()` or on every solution.

---

### Layer 8: Component Identity & Palette Placement

| Property | What It Controls | Chirp Value |
|---|---|---|
| `Name` | Full component name | "Chirp Component" |
| `NickName` | Display label on capsule | Per-instance: "Pergola Spacing" |
| `Description` | Tooltip description | Per-instance: signature + category |
| `Category` | Component palette tab | "Chirp" |
| `SubCategory` | Palette subtab | Per-category: "Planners", "Interpreters", etc. |
| `Exposure` | Visibility in palette | `GH_Exposure.primary` |
| `ComponentGuid` | Unique type GUID | One GUID for the ChirpComponent class |
| `Icon` | 24×24 capsule bitmap | Per-category icon |

**Palette placement:** The component appears in the GH ribbon under a "Chirp" tab. Users can drag it onto canvas and configure it — but the primary creation path is through `chirp_create` / Claude, not manual drag-and-drop.

---

### Layer 9: Dynamic Parameters

**Interface:** `IGH_VariableParameterComponent`

| Method | What It Does |
|---|---|
| `CanInsertParameter(GH_ParameterSide, int)` | Whether new params can be added at this position |
| `CanRemoveParameter(GH_ParameterSide, int)` | Whether params can be removed from this position |
| `CreateParameter(GH_ParameterSide, int)` | Build a new parameter at runtime |
| `DestroyParameter(GH_ParameterSide, int)` | Remove a parameter at runtime |
| `VariableParameterMaintenance()` | Called after param changes for validation/cleanup |

**For Chirp:** `chirp_create` creates an instance with zero custom pins, then adds pins dynamically based on the category and domain. The Reasoning output and Correction input are always present (auto-added). Domain-specific pins are added per-instance.

**Persistence:** Dynamic parameters survive save/reload through GH's built-in parameter serialization — each parameter's name, type, access mode, and data are saved automatically. Our `Write()`/`Read()` overrides handle Chirp-specific metadata on top.

---

## Real-World Examples of Extreme Customization

### GraphMapper (Built-in)

Interactive curve editor embedded in the capsule. Demonstrates the full custom attributes pattern:
- `Layout()` creates enlarged capsule with interactive graph region
- `Render()` draws axes, grid, control points, interpolated curve
- Mouse handlers enable dragging control points to reshape the mapping curve
- `Write()`/`Read()` persist curve type and control point positions
- Extension: [RichedGraphMapper](https://github.com/DanielAbalde/RichedGraphMapper) adds 5 new graph types

### Human UI

Paradigm-shifting: creates **WPF windows** outside the GH canvas. Tabbed views, sliders, checkboxes, 3D viewports, web browsers — completely decoupled from the canvas.
- Source: [github.com/andrewheumann/humanui](https://github.com/andrewheumann/humanui)
- Not relevant to Chirp's capsule customization but demonstrates the breadth of GH extensibility.

### GhPython (Built-in)

Custom attributes for Python script components:
- Source: [PythonComponentAttributes.cs](https://github.com/mcneel/ghpython/blob/master/Component/PythonComponentAttributes.cs)
- Custom `DrawViewportWires()` and `DrawViewportMeshes()` for 3D preview
- Reference implementation for script-component custom attributes

### Metahopper

Components that query and manipulate other GH components — enable/disable, change preview settings, modify properties dynamically. Similar to Rook's reflection-based approach but as GH components.

### Heteroptera

Network visualization and topology display. Interactive graph editing with node numbering. Demonstrates embedded interactive visualizations in component capsules.

---

## Proposed ChirpComponent Architecture

### One Class, Many Instances

```csharp
[Guid("...")]
public class ChirpComponent : GH_Component, IGH_VariableParameterComponent
{
    // === Per-instance state (set at creation, persisted on save) ===
    private ChirpCategory _category;           // Planner, Interpreter, Critic, etc.
    private string _signature;                  // DSPy signature string
    private Dictionary<string, string> _schema; // Output field → type mapping
    private string _lastReasoning;              // Cached for display before re-solve
    private string _adapterUrl = "http://localhost:9900/chirp/call";

    // === Component identity ===
    public override string Name => "Chirp Component";
    public override string NickName { get; set; }  // Per-instance: "Pergola Spacing"
    public override string Description => $"Chirp {_category}: {_signature}";
    public override string Category => "Chirp";
    public override string SubCategory => _category.PaletteName;  // "Planners", "Interpreters", etc.

    // === Dynamic icon per category ===
    protected override Bitmap Icon => ChirpIcons.ForCategory(_category);

    // === Custom attributes (visual customization) ===
    public override void CreateAttributes()
    {
        m_Attributes = new ChirpComponentAttributes(this);
    }

    // === The solve: HTTP call to Chirp adapter ===
    protected override void SolveInstance(IGH_DataAccess DA)
    {
        // 1. Collect inputs into dict
        // 2. POST to adapter with signature + inputs + schema
        // 3. Parse response, coerce types
        // 4. Set outputs via DA.SetData
        // 5. Set Reasoning output
        // 6. Update Message: "Planner • 1.2s"
        // 7. Cache reasoning for display
    }

    // === Serialization ===
    public override bool Write(GH_IWriter writer) { /* persist all state */ }
    public override bool Read(GH_IReader reader) { /* restore all state */ }

    // === Dynamic pins ===
    public bool CanInsertParameter(GH_ParameterSide side, int index) => true;
    public bool CanRemoveParameter(GH_ParameterSide side, int index) => true;
    public IGH_Param CreateParameter(GH_ParameterSide side, int index) { ... }
    public bool DestroyParameter(GH_ParameterSide side, int index) { ... }
    public void VariableParameterMaintenance() { ... }

    // === Custom right-click menu ===
    protected override void AppendAdditionalComponentMenuItems(ToolStripDropDown menu)
    {
        Menu_AppendItem(menu, "View Full Reasoning…", OnViewReasoning);
        Menu_AppendItem(menu, "Edit Signature…", OnEditSignature);
        Menu_AppendSeparator(menu);
        var catMenu = Menu_AppendItem(menu, "Change Category");
        foreach (var cat in ChirpCategory.All)
            Menu_AppendItem(catMenu.DropDown, cat.DisplayName,
                (s, e) => OnChangeCategory(cat));
    }
}
```

### Custom Attributes Class

```csharp
public class ChirpComponentAttributes : GH_ComponentAttributes
{
    public ChirpComponentAttributes(ChirpComponent owner) : base(owner) { }

    private ChirpComponent Chirp => (ChirpComponent)Owner;

    protected override void Render(GH_Canvas canvas, Graphics graphics, GH_CanvasChannel channel)
    {
        if (channel == GH_CanvasChannel.Objects)
        {
            // Create capsule with category-specific color
            var capsule = GH_Capsule.CreateCapsule(Bounds, GH_Palette.Transparent);
            var style = ChirpStyles.ForCategory(Chirp.Category);
            capsule.Render(graphics, style);
            capsule.Dispose();

            // Render parameter grips (standard)
            RenderComponentParameters(canvas, graphics);

            // Render icon + name
            // ... standard rendering with category icon
        }
    }

    public override GH_ObjectResponse RespondToMouseDoubleClick(GH_Canvas sender,
        GH_CanvasMouseEvent e)
    {
        // Open reasoning viewer instead of script editor
        Chirp.ShowReasoningViewer();
        return GH_ObjectResponse.Handled;
    }
}
```

### Category Color Scheme (Proposed)

| Category | Color | Hex | Rationale |
|---|---|---|---|
| Planner | Blue | `#4682B4` | Primary/authoritative — sets the direction |
| Interpreter | Green | `#5B9A6B` | Growth/branching — domain-specific growth from trunk |
| Critic | Orange | `#D4873F` | Caution/attention — flags issues |
| Narrator | Purple | `#7B68AE` | Creative/expressive — prose output |
| Classifier | Teal | `#4A9B9B` | Analytical/categorical — sorting/routing |
| Gate | Red-brown | `#A0522D` | Control/constraint — rule activation |
| Editor | Gold | `#C4A035` | Human/intervention — where the designer steers |
| Reasoning wire | Magenta | `#B464A8` | Distinct from all standard GH wire colors |

### Custom Reasoning Parameter

```csharp
public class ChirpReasoningParam : GH_Param<GH_String>
{
    public ChirpReasoningParam()
        : base("Reasoning", "R", "LLM chain-of-thought reasoning",
               "Chirp", "Parameters", GH_ParamAccess.item) { }

    public override Guid ComponentGuid => new Guid("...");

    // Distinct wire color — magenta, unlike any standard GH type
    public override Color DefaultWireColor => Color.FromArgb(180, 100, 168);
}
```

---

## Visual Mockup

```
Standard Script Component (current):                 ChirpComponent (proposed):

┌──────────────────────┐                    ┌──────────────────────────────────┐
│  ⚙  C# Script       │                    │  🧠  Pergola Spacing            │
├──────────────────────┤                    ├──────────────────────────────────┤
│ x ─┤          ├─ A   │                    │ Brief ─────┤        ├── Span    │
│ y ─┤          ├─ B   │                    │ Correction─┤        ├── Depth   │
│    │          │      │                    │            │        ├── BayCount│
└──────────────────────┘                    │            │        ╞══ Reason  │ ← magenta wire
                                            └──────────────────────────────────┘
 (no label)                                              Planner   ← Message
 (orange capsule)                                    (blue capsule)
 (generic icon)                                   (category icon)
 (opens script editor on dblclick)           (opens reasoning viewer on dblclick)
 (standard right-click menu)              (custom menu: View Reasoning, Change Category)
 (lost on file reopen)                       (fully persisted via Write/Read)
```

---

## Implementation Phases

### Phase 1: Minimal Viable Component
- `ChirpComponent` class with dynamic pins, `SolveInstance` HTTP call, `Write`/`Read` serialization
- `ChirpComponentAttributes` with category-colored capsule
- `Message` property showing category name
- Per-category `NickName` set by `chirp_create`
- No custom icon yet (use default), no embedded reasoning preview, no custom wire color

### Phase 2: Identity & Discoverability
- Per-category 24×24 icons (7 icons)
- `ChirpReasoningParam` with custom magenta wire color
- `ChirpCorrectionParam` (optional input, visually distinct)
- Custom right-click menu: View Reasoning, Edit Signature, Change Category
- Tooltip showing signature + last reasoning summary

### Phase 3: Interaction
- Double-click opens reasoning viewer (not script editor)
- GraphMapper-style expanded mode with reasoning preview inside capsule
- Reasoning history browser (right-click → Reasoning History)
- Hover regions with rich tooltips per capsule area

### Phase 4: Polish
- Category color scheme finalized with user feedback
- Overlay channel: subtle status indicator ("reasoning…" spinner during solve)
- Viewport preview: 3D text annotations (experimental)
- Cache indicator in capsule (subtle icon showing cached vs fresh result)

---

## SDK Reference Links

| Resource | URL |
|---|---|
| GH SDK Documentation Hub | [mcneel.github.io/grasshopper-api-docs](https://mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/723c01da-9986-4db2-8f53-6f3a7494df75.htm) |
| GH_Capsule Class | [API Docs](https://mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/T_Grasshopper_GUI_Canvas_GH_Capsule.htm) |
| GH_ComponentAttributes Class | [API Docs](https://mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/T_Grasshopper_Kernel_Attributes_GH_ComponentAttributes.htm) |
| Custom Attributes Guide (C#) | [Developer Docs](https://developer.rhino3d.com/api/grasshopper/html/8a7974ab-7b2b-4f48-84d0-6e81b184e6b0.htm) |
| Custom Component Options | [Developer Docs](https://developer.rhino3d.com/guides/grasshopper/custom-component-options/) |
| Grasshopper Icons Guide | [Developer Docs](https://developer.rhino3d.com/guides/grasshopper/grasshopper-icons/) |
| GH_CanvasChannel Enum | [API Docs](https://mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/T_Grasshopper_GUI_Canvas_GH_CanvasChannel.htm) |
| GH_PaletteStyle Class | [API Docs](https://mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/T_Grasshopper_GUI_Canvas_GH_PaletteStyle.htm) |
| Your First Component Guide | [Developer Docs](https://developer.rhino3d.com/guides/grasshopper/your-first-component/) |
| GraphMapper Extension | [RichedGraphMapper (GitHub)](https://github.com/DanielAbalde/RichedGraphMapper) |
| GhPython Custom Attributes | [PythonComponentAttributes.cs (GitHub)](https://github.com/mcneel/ghpython/blob/master/Component/PythonComponentAttributes.cs) |
| Human UI | [GitHub](https://github.com/andrewheumann/humanui) |

---

## Why Not Script Components — The Deeper Argument

### No Runtime Compilation

The current script component approach has a hidden cost: **RhinoCode compiles C# on every file open.** The lifecycle is:

1. `chirp_create` generates a C# source string in Python
2. String is sent over HTTP to the script component via `SetSource()`
3. RhinoCode stores the source in memory
4. RhinoCode compiles it into an in-memory assembly
5. The compiled `RunScript` method executes on each solve
6. On save, the source string is serialized into the .gh file
7. On reopen, the source is deserialized and recompiled

Nothing ever hits disk as a `.cs` file — it's strings in memory and in the .gh binary. But the compilation step happens every time the file opens, and compilation errors are possible if the environment changes.

With a compiled `ChirpComponent`, steps 1-5 disappear. The HTTP call logic is baked into the .rhp plugin at build time. No source strings, no RhinoCode compiler, no runtime assembly generation. Faster load, zero compilation errors.

### The LLM Replaces the Code

The script component's C# code is always the same ~30 lines of HTTP boilerplate. The actual intelligence lives in the Chirp adapter (Python/DSPy) on port 9900. The C# is a thin pipe — serialize inputs, POST, deserialize outputs.

In a `ChirpComponent`, that pipe logic is compiled once into `SolveInstance()`. There's nothing to generate per-component because there's nothing unique per-component in the C# — the uniqueness is in the **signature, schema, and pins**, which are data, not code.

The shift: **"let AI write the code" → "let AI be the code."** There is no code to write because the LLM reasoning at runtime IS the component logic.

---

## Pin-Agnostic SolveInstance

A critical design insight: `SolveInstance` never hardcodes pin names. It discovers them at runtime.

### The Script Component Problem

Script components compile `RunScript` with hardcoded parameter names:
```csharp
void RunScript(string Brief, string Correction, ref int Span, ref int Depth)
```
Add a pin → you MUST update the script → requires recompilation. Claude must rework the internals every time pins change.

### The ChirpComponent Solution

`SolveInstance` iterates over whatever pins currently exist:
```csharp
protected override void SolveInstance(IGH_DataAccess DA)
{
    // Collect ALL inputs dynamically — whatever they are right now
    var inputs = new Dictionary<string, object>();
    for (int i = 0; i < Params.Input.Count; i++)
    {
        object val = null;
        DA.GetData(i, ref val);
        inputs[ToSnakeCase(Params.Input[i].NickName)] = val?.ToString();
    }

    // POST to adapter with signature + inputs + schema
    var response = CallAdapter(_signature, inputs, _schema);

    // Distribute ALL outputs dynamically — whatever they are right now
    for (int i = 0; i < Params.Output.Count; i++)
    {
        var key = ToSnakeCase(Params.Output[i].NickName);
        if (response.Outputs.TryGetValue(key, out var val))
            DA.SetData(i, val);
    }
}
```

Pin names map to DSPy signature fields via snake_case conversion (`SeismicZone` → `seismic_zone`). Adding a pin doesn't require touching any compiled code — the loop picks it up automatically on the next solve.

**The only thing that must stay in sync is the signature string** — it must list the same fields the pins provide. This can be auto-rebuilt in `VariableParameterMaintenance()`:

```csharp
public void VariableParameterMaintenance()
{
    var ins = Params.Input
        .Where(p => p.NickName != "Correction")  // skip universal pin
        .Select(p => ToSnakeCase(p.NickName));
    var outs = Params.Output
        .Where(p => p.NickName != "Reasoning")    // skip universal pin
        .Select(p => ToSnakeCase(p.NickName));
    _signature = $"{string.Join(", ", ins)} -> {string.Join(", ", outs)}";
}
```

---

## Manual Editability Without Claude

### What a designer can do manually (no Claude needed):

| Action | How | Works? |
|---|---|---|
| Rename the component | Double-click NickName | Yes, standard GH |
| Wire inputs/outputs | Drag connections | Yes, standard GH |
| Lock/unlock, hide/show | Right-click | Yes, standard GH |
| Move, copy, group | Canvas interaction | Yes, standard GH |
| Change category | Right-click → Change Category | Yes (custom menu) |
| View reasoning | Right-click → View Reasoning / double-click | Yes (custom menu + handler) |
| Add/remove pins via ZUI | Right-click → add parameter | Partially — see below |

### Pin editing: works with guardrails

When a user adds a pin via GH's ZUI (right-click → insert parameter):
1. GH creates the pin with a default name ("New Param")
2. User renames it (e.g., "SeismicZone")
3. `VariableParameterMaintenance()` fires, auto-rebuilds the signature
4. The schema defaults new output pins to `string` type
5. Next solve includes the new field in the adapter call

**What the user CAN'T do manually:**
- Edit the signature phrasing (the descriptive version vs bare field names)
- Change output type mappings in the schema (`int` vs `float` vs `string`)
- Change the adapter endpoint
- Edit the component's solve logic (there's no script to open)

### Design decision: configured, not hand-coded

A `ChirpComponent` is more like a **configured instrument** than an editable script. The user describes what they need, Claude configures it. If they need to tweak it, they tell Claude "add a seismic zone input" and Claude updates pin + signature + schema in one call.

For power users who want direct access without Claude, a right-click **"Edit Chirp Component…"** dialog could expose signature, schema, and pins in one form. This is a Phase 3 feature — not essential for v1.

### What this preserves

The important thing: **the component is not a black box.** The user can see every pin, read every output, inspect reasoning, change the category, rename things, rewire the graph. They just can't edit the HTTP call logic, which they'd never want to anyway. The meaningful flexibility (what the LLM reasons about) is in the signature and schema — and those can be surfaced through a dialog when needed.

---

## Open Questions

1. **Where does ChirpComponent live?** In `src/Rook/` (the companion plugin) or in a new `src/Chirp/` C# project? The companion plugin already loads into GH — adding here is simplest. But Chirp might deserve its own .rhp for independent deployment.

2. **One GUID or seven?** One `ChirpComponent` class with one GUID, parameterized by category, is simpler. But seven separate classes (one per category) give each its own palette entry and could have slightly different `SolveInstance` logic. Lean: one class, seven is premature.

3. **Async solve?** The HTTP call to the adapter blocks the GH thread for seconds. `GH_TaskCapableComponent<T>` enables async solve — the component shows "reasoning…" and the canvas stays responsive. Important for UX but adds complexity. Could be Phase 2.

4. **Correction pin: always visible or auto-hide?** If the Correction input is always visible, every component has an unused pin. If it auto-hides when disconnected, it's cleaner but less discoverable. Lean: always visible but `Optional = true` so no warnings when empty.

5. **How does `chirp_create` talk to the new component?** Currently it generates C# script code via `gh_edit`. With a compiled component, it needs to: (a) create an instance of `ChirpComponent` by GUID, (b) set its category/signature/schema/pins via reflection or a dedicated endpoint. The GH handler needs a new route or an extension to `/gh/edit`.

6. **Signature auto-sync vs explicit control?** `VariableParameterMaintenance()` can auto-rebuild the signature from current pin names. This is convenient for manual pin editing but loses any descriptive phrasing in the signature. Alternative: only auto-sync when a flag is set, otherwise require Claude or the Edit dialog to update the signature. Lean: auto-sync as default, with an option to lock the signature for advanced use.
