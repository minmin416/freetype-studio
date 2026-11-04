# Contributing guidance

Read README.md before changing user-facing behavior.

- Embedded bitmap mode must load actual bitmap strikes. Never silently substitute rendered outlines.
- Keep preview, clipboard and downloaded output consistent.
- Keep font files, uploads, virtual environments, logs and temporary output out of Git.
- Startup scripts must work regardless of the checkout directory.
- Verify affected user paths and run the render tests before committing.
