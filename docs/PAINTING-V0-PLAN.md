# Keeper Painting Foundation V0 candidate

User work instruction dated 17 October 2026 is the implementation brief. At the time of this initial plan, installation, promotion, publication and live expression changes required later authorisation. The user subsequently authorised installation and publication; the resource HOLD remains unchanged. This document preserves the original V0 plan.

Architecture: add strict painting validation and descriptor-relative storage, expose separate save/read MCP tools through the existing launch binding, and provide an explicit assistant painting command plus a standalone yielding Canvas preview. Existing expression tools and terminal renderer stay unchanged. No autonomous composition engine is claimed.

1. Test invalid values, privacy text, schema bounds, duplicate JSON keys, exclusive saves, deduplication, concurrent numbering and symlink refusal. Implement painting_store.py.
2. Add launch-bound MCP save/read operations and the /keeper paint instruction interface; test binding refusal and expression isolation.
3. Add an independent preview renderer matching Studio geometry, gradients, Catmull-Rom, glow, seeded spray, mirrors and additive light. Yield within 20 ms, including spray primitives. Compare drawing operations against Studio's renderer.
4. Author one original composition explicitly as the permitted assistant; save in this candidate project. Run the supplied checker; prove peer read hash/mtime stability; refuse a disposable malformed painting and delete only it.
5. Run regression checks, preserve logs and source diff. Record actual screenshot/Studio acceptance gaps without substituting fixtures for human confirmation.

Review focus: concurrent deduplication; directory/file symlinks; invalid floats and bools; inherited launch project selection; maximal geometry yielding. Source snapshot is the current cyclops-keeper directory (the live directory has no usable Git metadata in this environment); a copy was selected as explicitly permitted.
