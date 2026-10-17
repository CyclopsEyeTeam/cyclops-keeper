# Keeper in Studio

This repository contains the terminal mod only, including its optional activity-feed adapter. It can live anywhere; when installed in Studio, its checkout is `presences/keeper/mod`. The sibling renderer, Studio registry and Studio application are outside this Git repository.

To update the terminal mod from this checkout:

```sh
git pull --ff-only
bash install.sh
```

Use `main` tracking `origin/main`. These commands update the mod and its installed Codex copy; they do not update Studio or its renderer. Start a new Codex terminal to load the refreshed plugin. Existing sessions are not restarted.

Studio supplies `CYCLOPS_SESSION_ID`. Only a valid supplied session ID enables the optional feed under `$XDG_STATE_HOME/cyclops-presence/<id>/keeper` (default `~/.local/state`). `CYCLOPS_PRESENCE_ROOT` is a host/test override. No Studio ID means no feed. Files contain observed event types, timestamps, sequence numbers, phases, bounded relations and hashed correlation keys. Prompts, commands, paths, tool results and raw Codex session identifiers are excluded.

The adapter is carried forward from the existing `codex-keeper` Studio integration (`presence_feed.py`, `feed_state.py`), with its nine protocol tests. A heartbeat worker is bound to an identified Codex ancestor and stops when that producer disappears. Publication failure retains local terminal activity. Durable updates are paced to one second, live updates to 200 ms, and idle heartbeats to five seconds; session boundaries flush immediately.

The former no-external-write test now checks an invalid Studio ID; dedicated tests check ordinary sessions publish nothing and valid Studio sessions publish only the contracted fields. This is an explicit integration contract change, not a waiver of privacy checks.

The renderer lives separately in `../render`, preserves the accepted body and adds a restrained woven crest. No renderer timer manufactures activity. Reduced motion and disconnected states freeze the ornament.

Version 0.6.0 releases the painting, expression and side-chat additions. The historical resource HOLD remains unchanged. Studio automatic updates are configured separately by Studio. Its Keeper entry follows the newest complete installed version rather than a fixed cache path; “Keep up to date” refreshes changed local mod versions on Studio startup. Git updates remain terminal-mod-only. The previous source folder can remain in place.


## Painting side chat

Studio sends Keeper questions in `studio.json` under `keeperAsk`, with an explicit current `run`, question `id`, `text`, `t`, and optional selected `painting`. Keeper ignores Spark's `ask` field. Clearing that Keeper request cancels it. The terminal and Studio share a private per-Codex-session painting conversation. Keeper writes only bounded side answers/status/usage to its own `side.json`, tagged with the feed run; these are deliberately separate from the content-free activity feed. Studio validates current producer ownership before accepting asks or clears.

The accompanying Studio UI/backend patch is not included in this repository, and `install.sh` does not modify Studio.

The installer preserves older numeric cache versions for open sessions after a refresh, including a failed refresh. Rollback copies are retained under Codex plugin data (`cyclops-keeper-install`); they are installation state, not painting data. Existing sessions still need relaunching to load new code.
