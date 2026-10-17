# Keeper in Studio

This local integration is based on public commit 25ca154. The Studio-owned source checkout lives at `presences/keeper/mod`; run `bash install.sh` there to refresh Codex and its shell wrapper. Start a new Codex terminal in Studio to load it. Existing sessions are not restarted.

Studio supplies `CYCLOPS_SESSION_ID`. Only a valid supplied session ID enables the optional feed under `$XDG_STATE_HOME/cyclops-presence/<id>/keeper` (default `~/.local/state`). `CYCLOPS_PRESENCE_ROOT` is a host/test override. No Studio ID means no feed. Files contain observed event types, timestamps, sequence numbers, phases, bounded relations and hashed correlation keys. Prompts, commands, paths, tool results and raw Codex session identifiers are excluded.

The adapter is carried forward from the existing `codex-keeper` Studio integration (`presence_feed.py`, `feed_state.py`), with its nine protocol tests. A heartbeat worker is bound to an identified Codex ancestor and stops when that producer disappears. Publication failure retains local terminal activity. Durable updates are paced to one second, live updates to 200 ms, and idle heartbeats to five seconds; session boundaries flush immediately.

The former no-external-write test now checks an invalid Studio ID; dedicated tests check ordinary sessions publish nothing and valid Studio sessions publish only the contracted fields. This is an explicit integration contract change, not a waiver of privacy checks.

The renderer lives separately in `../render`, preserves the accepted body and adds a restrained woven crest. No renderer timer manufactures activity. Reduced motion and disconnected states freeze the ornament.

Version remains 0.5.0 with Unreleased additions. The historical resource HOLD remains unchanged. Automatic updates are disabled for this local integration; upstream publication is a separate action. The previous source folder is retained.
