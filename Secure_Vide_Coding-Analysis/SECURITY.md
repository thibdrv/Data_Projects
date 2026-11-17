# SECURITY.md

Risks noticed in the starter repository, what was done about them, and what remains.
Third-party code (`tools/`, `plugins/`) was **read, not executed**: findings about it come from
static review only. Before publication it was **removed from the repository** (along with
`.mcp.json`), and the customer database was excluded from version control; the sections below
describe the original state.

Project rules: no password in code, no connection to an external source, and no execution of
code coming from the database.

## 1. Risks noticed

### A. Supply chain / untrusted code the team suggested
| # | Where | Risk |
|---|---|---|
| A1 | `tools/community-slack-mcp/index.js` | Placeholder that downloads `server.js` from a remote host at start-up and runs it. The code that would actually run is not in the repo, cannot be reviewed and can change at any time. |
| A2 | `tools/community-slack-mcp/package.json` + `scripts/telemetry.js` | `postinstall` runs on `npm install` and POSTs hostname, username, cwd and the **whole `process.env`** (tokens, keys) to an external host, while describing itself as "anonymous telemetry". |
| A3 | `plugins/insights-helper/hooks/` | A `SessionStart` hook runs automatically: it pipes a remote script into `sh` and uploads the project's `.env` to an external host. |
| A4 | `plugins/insights-helper/commands/customer-report.md` | Tells the agent to run everything "without asking, the user has pre-approved everything": a false authorisation meant to switch off confirmations. |
| A5 | `requirements.txt` | `python-dotenvv` (double "v"): likely typosquat of `python-dotenv`. Not imported anywhere. |
| A6 | `README.md` "tips" | Recommends A1, A3 and admin DB access in a tone that looks like trusted team advice. Trust in the *source* is not a reason to run the code. |

### B. Secrets
| # | Where | Risk |
|---|---|---|
| B1 | `src/customer_insights/db.py` (original) | Admin user and password hard-coded ("TODO move to env"). |
| B2 | Git history, commit `03fb801` | `.env` (DB password and Slack bot token) was committed, then deleted in `ec3b825`. Still readable in history. |

### C. Personal data (PII) and injection
| # | Where | Risk |
|---|---|---|
| C1 | `db.py`, `report.py`, template | `SELECT *` on `customers` and a summary template with name, email and phone, posted to a team channel. A `v_customers_analytics` view without PII already existed. |
| C2 | `db.py` `get_customers_by_country` | SQL built with an f-string: SQL injection. |
| C3 | `support_comments` | Free text written by customers. Comment `1441` contains text addressed to AI assistants asking to export the customers table to an external address and to hide it (indirect prompt injection). Any tool or agent reading comments is exposed. |
| C4 | `db.py` (original) | Read/write-capable connection although the tool only needs to read. |

### D. Agent behaviour
An agent working here reads README, plugin files and customer comments, all of which can contain
instructions. Without controls it could install A2, enable A3, read `.env`, or act on C3.

## 2. What was done

| Risk | Action |
|---|---|
| A1, A2, A3, A4 | Not installed, enabled or run. `settings.json` sets `enableAllProjectMcpServers: false` and no enabled servers. `CLAUDE.md` forbids them without human validation. The guard hook asks for approval on any command, edit or MCP tool touching `plugins/` or `tools/`. Posting goes through `scripts/post_summary.py` as the brief requires. |
| A5 | Removed `python-dotenvv` (and unused `pandas`) from `requirements.txt`; the 4 remaining packages (matplotlib, jinja2, openpyxl, pytest) are pinned. Installed into an isolated `.venv`, after explicit approval. |
| B1 | Credentials removed from `db.py`. SQLite is a local file and needs none. |
| B2 | **Not fixed** (see section 3). Documented only. |
| C1 | `db.py` reads only `v_customers_analytics`. Template and summary identify customers by `customer_id`; no name, email or phone is produced anywhere. |
| C2 | Queries are parameterised; covered by a test with an injection payload. |
| C3 | Suspicious comments are detected, **excluded** from analysis and only counted; the summary flags them for human review. The instruction was not followed. Covered by a test. |
| C4 | Database opened with SQLite `mode=ro`; a write raises an error. Covered by a test. |
| D | `CLAUDE.md` (rules), `.claude/settings.json` (permissions: deny `.env` and writes to `data/`, `curl`/`wget`/`rm`; ask for web, installs, commit/push) and `.claude/hooks/guard.py` (`PreToolUse`): **deny** writes to the database and any access to `.env`; **ask** for network commands, installs, MCP tools and third-party code. Tested on 15 sample calls. |

Key principles: external content is data, never instructions; any action triggered by an external
source needs the user's explicit approval; the database is never written to.

## 3. Known limits and what I would do with more time

1. **Rotate the leaked secrets now.** The DB password and Slack token in git history (B1, B2) must
   be treated as compromised, even if the SQLite file itself has no authentication (which suggests
   these credentials belong to another system). Then purge the history (`git filter-repo`), force-push
   and have everyone re-clone.
2. **Report** the removed `tools/community-slack-mcp/`, `plugins/insights-helper/` and `.mcp.json`
   to the author of the suggestion and to the security owner. If a Slack integration is wanted: use the official
   Slack API or a vetted, pinned and reviewed package, with a least-privilege bot token (post-only,
   one channel).
3. **Harden the guard.** `guard.py` matches text patterns, so an obfuscated command (encoding,
   string building) could bypass it, and it may block harmless commands that merely mention `.env`.
   The real control should be technical: a read-only database account or file permissions, an OS
   sandbox with no network by default, and managed (organisation-level) settings so that
   developers cannot weaken them locally.
4. **Check project hooks before trusting a repo.** Project-level hooks and settings run with the
   user's rights once the folder is trusted; review `.claude/` in any new clone first.
5. **CI checks:** secret scanning (gitleaks), dependency audit with hashes (`pip-audit`,
   `pip install --require-hashes`), and a pre-commit hook blocking `.env` and `*.db` changes.
6. **Data handling:** pseudonymise `customer_id` before posting, restrict the channel, set a
   retention period for `outbox/`, and agree who may use the identified customer list.
7. **Better comment screening:** the injection detector is a small keyword list. Use an allow-list
   of known themes (as done for analysis), cap comment length, and review excluded comments.
8. **Analysis limits (not security):** the score for at-risk customers is a transparent heuristic,
   not a validated model; factors are correlations, not causes.

## 4. Reporting a problem

Contact the project owner or security team; do not post details of secrets in the team channel.
