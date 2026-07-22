# CampusHub — AI Module Design

**Document Phase:** 11 of 18
**Status:** Draft for Approval (Post-MVP / P3)
**Version:** 1.0
**Date:** 2026-07-15

---

## 0. Positioning

The AI Module is explicitly **post-GA** (Phase 3 §7 priority P3). It is designed now so the data model and API surface (Phases 5–6) don't need retrofitting later, but no AI feature ships in the MVP. All AI features are **opt-in per tenant** (institution admins enable/disable) and degrade gracefully offline (cached results remain available; generation requires connectivity).

## 1. Architecture Overview

```
Flutter Client → FastAPI "AI Module" (new bounded module, Phase 4 pattern)
                     │
                     ├── Retrieval layer (pgvector extension on PostgreSQL, or dedicated vector store)
                     │     — embeds resource text content per-tenant, isolated by tenant_id
                     │
                     └── LLM Gateway (provider-agnostic interface)
                           — calls a hosted LLM API for generation/summarization tasks
                           — request/response logged for audit + cost tracking
```

The module is provider-agnostic by design: an internal `LLMProvider` interface abstracts the underlying model/vendor so it can be swapped without touching feature code.

## 2. AI Study Assistant

- Conversational interface scoped to a student's enrolled courses; answers are grounded in retrieved course resources (retrieval-augmented generation), not open-ended, to reduce hallucination risk in an academic context.
- Every answer cites the source resource(s) it drew from, giving students a path back to primary material.

## 3. Document Search (Semantic)

- Extends the keyword search (Phase 2 FR-SRCH-1) with embedding-based semantic search: resource text is chunked and embedded on upload/update, stored per-tenant in the vector index.
- Falls back transparently to keyword search when semantic search is disabled or unavailable (e.g., tenant hasn't opted in, or offline).

## 4. Lecture Summarization

- Applies to uploaded lecture materials and, where enabled, session recording transcripts (requires a transcription step — speech-to-text — before summarization).
- Summaries are generated once per resource/recording and cached (not regenerated per view) to control cost.
- Lecturer review/approval step before a summary is shown to students (avoids surfacing an inaccurate AI summary unchecked).

## 5. Quiz Generator

- Lecturers request auto-generated draft quiz questions from a selected resource; output is always a **draft** requiring lecturer review/edit/publish — never auto-published to students.
- Generated questions and answer keys are stored as regular `assignments`-adjacent content (quiz becomes a first-class content type in a future schema extension), reusing existing grading infrastructure where objective (auto-gradable) question types are used.

## 6. Flashcard Generator

- Derives flashcards (term/definition or Q&A pairs) from a resource, for the student's personal study use; stored client-side/per-user, not shared institutional content, minimizing schema impact.

## 7. Resource Recommendation

- Lightweight recommendation based on course enrollment + engagement signals already captured (Phase 5 `v_course_engagement`) plus semantic similarity between resources — no separate heavy ML pipeline required at this scale.

## 8. Study Planner

- Given a student's assignments/due dates (already modeled in `assignments`/`submissions`), the AI module proposes a study schedule; purely additive/read-only against existing data — does not require new core schema, only a planner-output cache table.

## 9. Natural Language Search

- Extends FR-SRCH-2 (Phase 2): allows queries like "what did Dr. Bello say about recursion last week" to route through intent parsing → structured filters (course, date range, speaker) → semantic search (§3), combining structured and vector retrieval.

## 10. Cross-Cutting Design Requirements

- **Tenant isolation:** vector embeddings and any cached AI output are tenant-scoped exactly like all other data (Phase 5 §1); no shared/global embedding index across institutions.
- **Cost control:** all generation calls are cached by content hash to avoid redundant LLM calls; usage metering surfaced to institution admins (extends Phase 4 §admin analytics).
- **Privacy:** no student personal data is sent to the LLM provider beyond what's necessary for the specific feature (e.g., study planner sends due dates, not full profile); configurable per-tenant data processing agreement awareness flagged in admin settings.
- **Offline behavior:** previously generated/cached AI content (summaries, flashcards) remains viewable offline via the same SQLite sync mechanism (Phase 9) as any other resource; new generation requests queue and fail gracefully offline with a clear "requires connection" state.

---

*Next document: Phase 12 — Testing Strategy.*
