# Enterprise Claude accounts in Thurbox

## Intent and agreed scope

The user wants both a native Thurbox Accounts panel and CLI commands, supporting
Enterprise browser-login accounts for new sessions and switching an existing
conversation to another account when possible. This extends the existing
external extension; debate/adversarial remain independent features.

The user has explicitly identified that existing conversation handoff is wanted
after being told it can transfer context between Enterprise organizations.
That authorizes building the mechanism, not transferring any actual conversation
without a specific source/target confirmation at execution time.

## Approaches

1. **Selected: native Accounts panel plus CLI backend.** One service owns profile
   management, session creation and handoff. Lua is a thin client. This uses
   public Thurbox APIs and keeps installed core binaries unchanged.
2. CLI only: less interface work, but does not meet the user's chosen scope.
3. Global credential swapping or shared account history: rejected because it
   changes concurrent sessions and can mix Enterprise identities and data.

## Verified foundation

Thurbox 2.75.2 is installed. Its CLI supports `session create --agent --env`,
`--agent-arg`, `--resume`, `session get/stop`, and metadata. Launch environment
is persisted and consulted for transcript discovery and restart. The ordinary
Lua New Session form cannot pass an account environment, so an Accounts panel
will invoke the backend CLI instead of silently reusing that form.

The live UI directory reported by `plugin dir` is
`~/.config/thurbox/ui`; it does not yet exist. Implementation must materialize
the binary's own UI, then read its AGENTS.md/README.md before editing. Do not
substitute the upstream checkout's Lua for the live interface.

Official Claude documentation consulted on 26 October 2026:

- https://code.claude.com/docs/en/authentication#log-in-with-multiple-accounts
- https://code.claude.com/docs/en/authentication#credential-management
- https://code.claude.com/docs/en/cli-reference

`CLAUDE_CONFIG_DIR` separates claude.ai login, settings and history, including
the macOS Keychain entry. `claude auth login --sso` supports Enterprise login;
`auth status` exposes auth method/config directory on supported versions.
`--resume` accepts an absolute JSONL transcript path. `--fork-session` creates
a new conversation; `--session-id` pins an ID. Claude is not installed yet,
so the precise combined-flag behavior remains a compatibility gate below.

## Profile model and privacy

Store non-secret profile metadata under the extension's user-data directory:
safe slug, display name, canonical absolute configuration directory, expected
Enterprise identity/organization when available, and an enabled flag. Profile
directories have private permissions. Labels are user-entered; no real account
credentials are requested in this chat.

Each profile uses a separate configuration directory. Claude handles login,
Keychain storage, token refresh and SSO in its normal interface. Never read,
copy, export, rewrite or log credential files/Keychain values. Never share
configuration directories, history directories or credential symlinks.

Inherited API-key/token/provider overrides must not silently select another
identity. Detect conflicting credential/routing variable names and report a
clear preflight failure without printing values. Do not silently unset them or
override organization-managed settings. Validate the native auth-status result
against the selected profile before starting or handing off a conversation.
An unsupported CLI/status schema or Enterprise policy refusal is a blocker.

Existing unrelated profiles, sessions, hooks and permission settings are left
alone. Profile removal, logout/revocation and automatic account failover are
out of scope for this version.

## CLI

Proposed commands (names may be adjusted only for existing parser conventions):

```text
thurbox-loop accounts add NAME [--label TEXT]
thurbox-loop accounts list [--json]
thurbox-loop accounts login NAME
thurbox-loop accounts status NAME [--json]
thurbox-loop accounts start NAME --repo PATH --name SESSION
thurbox-loop accounts handoff --session REF --to NAME          # preview only
thurbox-loop accounts handoff --confirm PLAN_ID               # execute preview
thurbox-loop accounts ui-install                             # install the pane
```

`login` launches Claude's interactive SSO login visibly, scoped to the profile;
the user completes browser/SSO actions. Auth output is not captured into the
extension's logs. Metadata and JSON status output whitelist non-secret fields.

`start` uses the registered Claude agent and a persisted session-specific
`CLAUDE_CONFIG_DIR`. It records profile metadata on the new Thurbox session.
All existing sandbox, approval and Enterprise policies continue to apply.
Existing sessions that lack provable profile/transcript ownership are refused
for automatic handoff, rather than guessed from arbitrary paths.

## Existing-conversation handoff

1. Preview a specific source session, source profile, destination profile,
   repository/worktree, identity, and the fact conversation context will be
   available to the destination account. No transcript is transferred at preview.
2. Produce a short-lived, private confirmation plan with a random identifier.
   CLI execution requires `--confirm PLAN_ID`; the panel displays the same
   source/destination preview and requires a separate confirmation action.
3. Revalidate source identity, target auth, session revision, account metadata
   and directory ownership. Any changes invalidate the plan.
4. Refuse an actively working/blocked agent with unfinished tools; require the
   user to choose a safe stopping point. Then stop only that source session,
   verify it stopped, and snapshot its completed main transcript atomically.
5. Keep the snapshot private, immutable and separate from credentials/settings.
   Do not copy all history, plugins, hooks, skills, config or other conversations.
6. Create a new Thurbox session in the same working directory/worktree, with
   the destination profile's persisted environment. Ask Claude to resume the
   snapshot as a fork. Preserve the source session and source files.
7. Verify the new session's profile binding, conversation ID and existence;
   report a ready or needs-interactive-attention state, not model completion.
   No model prompt is sent merely to test an Enterprise account.
8. Record only source/target names, session IDs, snapshot hash and outcome in an
   audit record. Never log conversation content or credentials.

Errors must preserve the source session record/worktree and report exact recovery
steps. If destination creation fails after the source stops, leave the source
stopped and offer its existing restart command; do not auto-resume under another
account. Expired/reused confirmation plans and duplicate concurrent handoffs are
refused using an exclusive per-session lock and durable operation record.

### Compatibility gate

Before enabling handoff, install the official Claude CLI and verify its actual
help/behavior for `--resume ABSOLUTE_TRANSCRIPT --fork-session --session-id ID`.
The intended Thurbox launch uses an ordinary fresh registered-agent creation:
its normal new-session args supply the target UUID, while opaque agent args
supply resume/fork. This avoids putting a transcript pathname into Thurbox's
agent-session-ID column through `session create --resume PATH`.

Check that the fork writes into the destination profile and that Thurbox's
stored conversation ID is the actual new ID, including on restart. Tests must
prove this before enabling the action. If the installed public CLI cannot
support it reliably, keep new-session selection working, disable handoff with
a precise explanation, and return that limitation to the user. Never rewrite
JSONL session IDs or copy credential stores to simulate support.

## Accounts panel

A small switchable pane provides profile list/status, Add account, Sign in,
New session (repository/name fields), and Handoff selected session. The selected
session's profile is visible. Errors and pending login/confirmation are explicit.

Keep state transitions and command building in Python services, outside Lua.
Use existing widgets and theme roles. Run external operations on workers;
never block render or read credentials from Lua. Shell-facing arguments must be
strictly validated/quoted; prefer the native argv-capable program interface
where available. No model-generated command text is executed.

The pane declares the necessary run/program/session capabilities. The user must
grant them in Thurbox's own Interface settings; never edit trust records or
`ui.json` to grant capabilities. Installation backs up any touched layout file,
adds only the new pane/slot, and preserves unrelated UI customizations. Validate
using the installed binary's `plugin check` after every edit and inspect the
rendered pane in a real terminal.

## Architecture and tests

Add an `accounts` package for registry, Claude adapter, Thurbox session adapter,
handoff service, audit/locks and CLI. Reuse bounded execution and atomic-write
primitives where appropriate. UI payloads/install wiring stay separate. No new
runtime dependency is expected. Update AGENTS.md, README, manifest and tests.

Use fake Claude/Thurbox boundaries for deterministic tests of separate profile
environments; account mismatch; credential-env conflicts; path/symlink safety;
status redaction; concurrent plans; stale/expired confirmations; session-stop
refusal; immutable snapshots; fork UUID binding; restart; rollback instructions;
and proof no credential/settings directories are copied. Preserve existing tests.

Live checks use real Thurbox and disposable transcript/config fixtures first.
Enterprise authentication must be completed by the user through SSO. Validate
the actual installed Claude version, but do not claim full multi-account login
or cross-organization resume passed without two real authenticated profiles and
explicit confirmation for that specific test conversation.

## Non-goals and builder-owned details

No automatic quota-based switching, organization-policy bypass, account deletion,
credential import/export, global logout, or silent context sharing. No hosted
service or production deployment. Local POSIX first, matching the existing
extension. No Thurbox fork unless public extension APIs prove insufficient.

Builder-owned choices: exact internal module boundaries, private filename/lock
formats, plan expiry (proposed five minutes), UI chord without conflicts, and
masking of optional identity labels. These must be recorded and tested; they
do not need more preference questions.
