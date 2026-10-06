# activity-face/v1

This shared protocol represents observed worker/session activity. Cyclops Keeper gives those observations a personal visual identity; the records carry no personality, memory or consciousness semantics. A future provider adapter may map verified native events to the same fields. No unverified provider hook names are asserted here.

Codex writes one atomic UTF-8 JSON file per session, under `PLUGIN_DATA/activity-face/sessions/<session-hash>.json`. The live viewer's `GET /api/state` returns `{ "schema": "activity-face/v1", "sessions": [ ... ] }`, sorted by latest update. Private reducer keys are omitted. Public `active_tools` and `active_subagents` contain SHA-256 identifiers derived from opaque host invocation IDs, so one visible tether can be correlated with one matching return without retaining a raw ID. Tool names reduce to the finite classes `inspect`, `change`, `execute`, `service`, or `other`. Tool arguments, results, names, subagent types, transcript paths, prompt text, assistant messages, working directories, model names, and credentials are discarded. `--test-feed` serves an explicitly disposable, visibly labelled public snapshot for visual review; its base64 transport contains the same sanitized fields and never raw host IDs or payloads.

Example public session record:

```json
{
  "schema": "activity-face/v1",
  "provider": "codex",
  "session": "64-character SHA-256 of the runtime session id",
  "state": "tool",
  "event": "PreToolUse",
  "updated_at": 1791029000.0,
  "sequence": 3,
  "active_tool_count": 1,
  "active_tools": [{"key": "64-character SHA-256 of tool_use_id", "kind": "execute", "sequence": 3}],
  "active_subagent_count": 0,
  "active_subagents": [],
  "transitions": [{"sequence": 3, "event": "PreToolUse", "at": 1791029000.0, "kind": "execute", "key": "64-character SHA-256 of tool_use_id"}],
  "stale": false
}
```

`session` identifies one provider-local session. Consumers should key records by `(provider, session)`. `sequence` advances for accepted events within one session; atomic replacement protects readers from partial writes. `updated_at` is receipt time in Unix seconds, not a model-provided timestamp. It orders accepted hook receipts, not an authoritative transaction ledger. `stale` is derived by the viewer after 300 seconds without a signal, and does not replace the observed state.

The documented host events are `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `Stop`, `Interrupt`, `SessionEnd`, `PreCompact`, `PostCompact`, `SubagentStart`, and `SubagentStop`. `SessionStart` accepts `startup`, `resume`, `clear`, and `compact`; compaction hooks accept `manual` and `auto`. Their visual meanings describe the event only. `Stop` is not success. A `PostToolUse` or `SubagentStop` establishes only that the corresponding call/agent returned or stopped, not its success or the acceptance of its output. An observed `SessionStart: resume` reopens a previously stopped, interrupted, or ended observation to `idle`, while retaining unresolved invocation correlations until their own matching return. If the resume event has no turn id, the prior turn id remains for matching late returns.

Each accepted event appends only `{sequence,event,at,kind,key}` to a 32-entry private ribbon. It holds no raw event payload. `key` is null when a return does not match a tracked start; a renderer does not invent a tether for an unmatched return. Each currently tracked tool/subagent remains independently keyed until its corresponding matching return event arrives, including across Stop, Interrupt, SessionEnd, and a newer turn. A return from an old turn removes only its matching key and cannot replace the current turn's state. Unknown or malformed identifiers cannot clear another call. This makes one bounded spatial tether per observed invocation compatible with arbitrary callback order.

`PreCompact` changes the state to `compacting`; `PostCompact` restores the previous observed pose while adding an event-backed fold/unfold transition. This is not a claim about memory or retained meaning. `SubagentStart` adds a satellite and `SubagentStop` returns the exact matching satellite. Interrupt breaks a turn-level membrane filament without assigning causality to an individual outstanding call. A later prompt reconnects that broken body filament; each old call stays tethered until only its exact matching return.

Updates serialize through a short per-session file lock and atomically replace a 0600 snapshot. The hook exits 0 with `{}` even if its input or storage is unusable. It issues no allow/deny, rewritten input, additional context, or turn-continuation response. A renderer may animate the bounded observed transition ribbon; ambient animation never changes these lifecycle fields.

Rendering notes for 0.3.1: stale or unavailable evidence freezes decorative movement and old transition gestures. An ended session can still show an exact subsequently observed return; this does not reopen the ended session or establish success. Colour distinguishes material and finite invocation classes, never semantic outcomes.
