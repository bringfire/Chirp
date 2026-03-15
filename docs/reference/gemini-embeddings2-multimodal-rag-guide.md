# Gemini Embeddings 2 — Multimodal RAG Implementation Guide

## What It Is
Google's first **natively multimodal embedding model**. A single model embeds text, images, videos, audio, and documents into the **same vector space**, understanding nuanced cross-modal relationships. No separate pipelines per modality.

## Architecture Overview

```
Data Sources (text, images, video, audio, PDFs)
    ↓
Gemini Embeddings 2 (single model, all modalities)
    ↓
Vector Points (numerical representations placed in multi-dimensional space by semantic meaning)
    ↓
Pinecone Vector Database (stores embeddings + metadata)
    ↓
RAG Query Layer (user query → embed → similarity search → retrieve relevant chunks)
    ↓
LLM Chat Model (e.g. Sonnet) generates response using retrieved context
```

## Key Implementation Details

### Ingestion Pipeline
- **PDFs**: Can be chunked automatically. A 68-page instruction manual PDF was ingested with both text and diagram images preserved. The model handles chunking across pages while maintaining context.
- **Images**: Stored with text descriptions/metadata alongside the embedding. Better descriptions = better retrieval. Up to **6 images per request**, supporting **PNG and JPEG**.
- **Videos**: Up to **120 seconds**, **MP4 or MOV** only. Stored similarly to images — a text description is embedded alongside the video embedding. Good descriptions are critical for retrieval quality.
- **Audio**: Same pattern — embed with quality text descriptions so the AI understands content.
- **Mixed data**: You can drop all file types into a single folder without pre-sorting. The model identifies modality automatically.

### Vector Database (Pinecone)
- Free starter plan is sufficient for prototyping.
- One index can hold all modalities together in the same vector space.
- Store metadata per record (cost, duration, team size, categories — whatever domain context matters).
- When re-ingesting updated records, **upsert** to avoid duplicates rather than inserting new records.

### Chat/Query App
- Build a local web app that queries Pinecone, retrieves matching embeddings, and passes results to an LLM for response generation.
- The app should be able to **serve media inline** (display retrieved images/videos in the chat), not just return filenames.
- Include **source attribution**: show which pages/documents matched and their confidence/similarity scores.

### API Keys Needed
1. **Gemini API Key** — from Google AI Studio (for the embeddings model)
2. **Pinecone API Key** — from pinecone.io (for the vector database)
3. **LLM API Key** — OpenRouter, OpenAI, or Anthropic (for the chat/response generation model)

Store in a `.env` file with placeholders.

## Critical Insights for Quality

1. **Metadata and descriptions are everything.** The embedding captures semantic meaning, but retrieval quality depends heavily on the quality of text descriptions stored alongside media. Subject matter expertise in crafting these descriptions matters more than technical configuration.

2. **The model places semantically similar items near each other in vector space.** E.g., images of water-damaged roofs cluster separately from age-deteriorated roofs. This enables similarity search across modalities — upload a photo, find similar past projects.

3. **Cross-modal querying works.** You can ask a text question and get back images, or upload an image and get back text descriptions of similar items. The shared vector space makes this native.

4. **Plan mode first.** Use plan mode to lay out the project structure, dependencies, and step-by-step build before executing. Review the plan and correct before auto-accepting.

5. **Iterative debugging via conversation.** If retrieval isn't returning expected results, paste the actual conversation back and ask *why* — understand how the system represents each record so you can improve descriptions/metadata.

## Practical Use Cases Demonstrated

- **Instruction Manual Chat**: Drop a complex PDF → chat with it, get text answers + relevant diagrams with page-level source attribution.
- **Visual Similarity Search (Roofing)**: Upload a photo → find similar past project images with metadata (cost, timeline, team size) → get instant project briefs and estimates.

## Current Limitations
- Video: max 120 seconds, MP4/MOV only
- Images: max 6 per request, PNG/JPEG only
- By default, ingested media may only store basic text descriptions — you need to explicitly enrich metadata and configure the app to serve media inline for full multimodal responses.

## Reference
- Google API docs for embeddings: https://ai.google.dev/gemini-api/docs/embeddings
- Pinecone: https://www.pinecone.io
- OpenRouter (multi-model access): https://openrouter.ai
