# Painting Side Chat Implementation Plan

> Execute natively with superpowers:executing-plans. Design approved in conversation on 17 October 2026.

**Goal:** A terminal Chat button and Studio Ask entry share a separate painting conversation, with cancellation and actual token reporting.

**Architecture:** A private per-launch chat controller owns bounded history, selected painting and one background reply job. The terminal rendering child polls it without blocking terminal input. Studio sends requests through its existing producer-bound ask mailbox; the same controller consumes them. Replies use an isolated ephemeral Codex invocation with tools disabled and an empty working directory. Only artwork and side messages enter its prompt, not the main conversation. No autonomous requests.

**Tech Stack:** Python standard library, existing terminal worker, Codex CLI JSON events, Studio JS/Python mailbox.

**Spec:** User-approved in-chat design: both entry points, shared follow-up history, answering/cancel status, reported usage, selected painting and side-chat messages only.

## Constraints
- Preserve existing terminal input/focus, artwork and Studio source separation.
- Private chat state is not saved in paintings, Git or public activity feed.
- Bound input, history, provider output and runtime; reject symlinks/nonregular files.
- Actual provider usage only; no fabricated percentage or price.
- Studio requests are bound to the current producer, and clearing cancels a pending request.
- HDD isolated copy; under 100 MiB expected before browser profile, 348 GiB free verified.

## Review Focus
- Cancel or attachment change while a reply finishes: no late reply accepted.
- Non-ASCII questions and terminal escapes: safe display and UTF-8 editing.
- Missing Codex/auth/provider failure: visible error, no invented answer.
- Studio request targeted at Spark: Keeper never answers it.
- Repeated polling/restart: no duplicate model request.

## Tasks
- [x] Add failing tests for side prompt isolation, no-tool provider invocation, bounded output, cancellation and usage parsing; implement `painting_chat.py` controller and provider worker.
- [x] Add terminal Chat/Send/Cancel/Back controls and safe text input, retaining input ownership; test editor and panel routing.
- [x] Add producer-bound Keeper Studio mailbox polling and shared history; test wrong producer, clearing and duplicate request behaviour.
- [x] Enable Keeper Ask in the isolated Studio copy, preserve Spark's behaviour and add status/cancel rendering; test backend and browser flow.
- [x] Run focused plus full mod tests and a real short artwork reply; review final diff; install checked mod and separate Studio patch with backups. Commit each repository separately; never add Studio files to mod Git.


## Execution record

Implemented inline in an HDD worktree. Regression tests drove prompt isolation, UTF-8 editing, request ownership, cancellation, EOF handling, immutable artwork and busy-request deduplication. A real Codex reply returned separate history and actual usage. Keeper and Spark browser ask/reply flows preserve both terminal sessions. The pre-existing Spark menu-order assertion fails against both unchanged Studio and this candidate; its evidence is retained and unrelated UI order is unchanged. Mod and Studio changes are committed independently.
