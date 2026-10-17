# activity-face/v1

This shared protocol represents observed worker/session activity. Cyclops Keeper gives those observations a personal visual identity; the records carry no personality, memory or consciousness semantics. A future provider adapter may map verified native events to the same fields. No unverified provider hook names are asserted here.

Codex writes one atomic UTF-8 JSON file per session, under `PLUGIN_DATA/activity-face/sessions/<session-hash>.json`. The terminal's read-only snapshot adapter returns `{ "schema": "activity-face/v1", "sessions": [ ... ] }`, sorted by latest update. Private reducer keys are omitted. Public `active_tools` and `active_subagents` contain SHA-256 identifiers derived from opaque host invocation IDs, so one visible tether can be correlated with one matching return without retaining a raw ID. Tool names reduce to the finite classes `inspect`, `change`, `execute`, `service`, or `other`. Tool arguments, results, names, subagent types, transcript paths, prompt text, assistant messages, working directories, model names, and credentials are discarded.

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

`session` identifies one provider-local session. Consumers should key records by `(provider, session)`. `sequence` advances for accepted events within one session; atomic replacement protects readers from partial writes. `updated_at` is receipt time in Unix seconds, not a model-provided timestamp. It orders accepted hook receipts, not an authoritative transaction ledger. `stale` is derived by the snapshot adapter after 300 seconds without a signal, and does not replace the observed state.

The documented host events are `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `Stop`, `Interrupt`, `SessionEnd`, `PreCompact`, `PostCompact`, `SubagentStart`, and `SubagentStop`. `SessionStart` accepts `startup`, `resume`, `clear`, and `compact`; compaction hooks accept `manual` and `auto`. Their visual meanings describe the event only. `Stop` is not success. A `PostToolUse` or `SubagentStop` establishes only that the corresponding call/agent returned or stopped, not its success or the acceptance of its output. An observed `SessionStart: resume` reopens a previously stopped, interrupted, or ended observation to `idle`, while retaining unresolved invocation correlations until their own matching return. If the resume event has no turn id, the prior turn id remains for matching late returns.

Each accepted event appends only `{sequence,event,at,kind,key}` to a 32-entry private ribbon. It holds no raw event payload. `key` is null when a return does not match a tracked start; a renderer does not invent a tether for an unmatched return. Each currently tracked tool/subagent remains independently keyed until its corresponding matching return event arrives, including across Stop, Interrupt, SessionEnd, and a newer turn. A return from an old turn removes only its matching key and cannot replace the current turn's state. Unknown or malformed identifiers cannot clear another call. This makes one bounded spatial tether per observed invocation compatible with arbitrary callback order.

`PreCompact` changes the state to `compacting`; `PostCompact` restores the previous observed pose while adding an event-backed fold/unfold transition. This is not a claim about memory or retained meaning. `SubagentStart` adds a satellite and `SubagentStop` returns the exact matching satellite. Interrupt breaks a turn-level membrane filament without assigning causality to an individual outstanding call. A later prompt reconnects that broken body filament; each old call stays tethered until only its exact matching return.

Updates serialize through a short per-session file lock and atomically replace a 0600 snapshot. The hook exits 0 with `{}` even if its input or storage is unusable. It issues no allow/deny, rewritten input, additional context, or turn-continuation response. A renderer may animate the bounded observed transition ribbon; ambient animation never changes these lifecycle fields.

Rendering notes for 0.3.1: stale or unavailable evidence freezes decorative movement and old transition gestures. An ended session can still show an exact subsequently observed return; this does not reopen the ended session or establish success. Colour distinguishes material and finite invocation classes, never semantic outcomes.

## Terminal-only release (0.5.0)

This release observes local Codex events and does not broadcast Cyclops Link
records, start Link heartbeat workers or render peer overlays. Older consent
and protocol artifacts remain preserved in historical source and development
evidence. Prior consent files are not modified. Running older sessions keep
their own loaded adapter until their normal lifecycle ends.

## Explicit authored expression channel

The `keeper` stdio MCP server supplies `say`, `paint`, and `clear`. These are
creative display writes, not `activity-face/v1` events. No `signal` or `agent`
mutation tool exists. Public activity records and their privacy filtering stay
unchanged. Deliberately submitted captions and geometric strokes are the only
new content retained; they never enter the activity feed.

The MCP process inherits `KEEPER_LAUNCH_SOCKET` and `KEEPER_LAUNCH_OWNER`. It
resolves the existing launch attachment, verifies its live owner and its own
descent from the attached Codex process, and refuses unattached launches. No tool
argument selects a path, session, agent or timestamp. Writes bind to the observed
owner, session and generation and use the launch directory's private atomic file
`.keeper-expression.json`, with a nonblocking writer lock. A changed attachment
hides old expressions. Existing launch cleanup owns these `.keeper-*` files.

`say` takes a printable ASCII caption (1–120 characters) and an optional
5–120 second lifetime (default 30). `paint` takes at most 12 polylines of 2–24
normalized finite points, in glass, lavender, gold or chalk. `clear` removes both.
Writes are limited to one per second, except clearing. There is one current note
and painting, no history. Tools reject arbitrary fields, terminal controls and
nonfinite/out-of-bounds coordinates. Intentional content must not contain private
transcript data; the server cannot semantically detect secrets in valid prose.

The terminal labels this separate space `Keeper / authored`. It is static under
all motion settings; expired captions disappear while the painting stays. Small
panes hide it. Subagent seats remain exactly the existing event-owned satellites,
including independent concurrent/out-of-order return handling.
