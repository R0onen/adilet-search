# Gate check (each agent runs this at gates G0–G5)

Gate definitions are in `docs/PROJECT_PLAN.md` §10.

1. **Sync.** Run `git pull --rebase origin main`. Read all three `docs/status/*.md` files and every entry in `contracts/CHANGELOG.md` since the last gate.
2. **Your own part.**
   - Run your lint and full test suite and paste the summary.
   - Go through your current phase file's acceptance criteria and mark each one met or not met, with evidence (a command, a file, a number).
3. **Integration from your side.**
   - **ML:**
     - The `ml-service` image builds and its contract tests pass.
     - `/version` returns the current manifest.
     - Ask the human for the output of the backend indexer run on your latest data, and check the row counts against `data/MANIFEST.json`.
   - **Backend:**
     - `docker compose up` is healthy (with the real `ml-service` if one is available).
     - `contracts/openapi.json` is fresh (the regeneration produces no diff).
     - The smoke script passes.
     - Check every open item under "Requests to other agents" that is addressed to Backend.
   - **Frontend:**
     - `npm run gen:api` against the current `openapi.json` produces no diff, or you adapted to it.
     - Lint, unit tests and the build pass.
     - The e2e smoke test passes against MSW, and also against the live dev stack if it is running.
4. **Mismatches.** List every mismatch you found with the other parts. For each one give the endpoint/field/file, expected vs actual, and the contract section it violates. Do **not** fix other agents' code.
5. **Report.** Update your status file. Reply with:
   - `GATE G<N>: PASSED` or `GATE G<N>: NOT PASSED` (and if not passed: what is missing, why, and a realistic ETA);
   - the mismatches;
   - your requests to the other agents;
   - the risks you see for the next gate.
