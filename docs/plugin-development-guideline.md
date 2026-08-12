# Cross-Platform AI Coding Assistant Plugin and Skill Development

This guideline explains how to build reusable agent skills and package them for GitHub Copilot, OpenAI Codex, Claude Code, and Google Antigravity.

> Last verified: 2026-08-12. Plugin systems evolve quickly. Treat each platform's official documentation and local CLI `--help` output as authoritative when they differ from this guide.

## 1. Scope and guiding principle

`SKILL.md` is the most portable unit across the four platforms. A plugin is a host-specific distribution package that can bundle skills with agents, hooks, MCP servers, and other integrations.

Do not assume that one plugin directory or install command works everywhere:

- Keep the skill workflow portable.
- Keep manifests, discovery paths, invocation syntax, and lifecycle commands in platform adapters.
- Use only documented host extensions. Do not put host-specific frontmatter in the portable core unless the other targets tolerate it.
- Re-verify commands before release or CI adoption.

This guide covers agent plugins, not editor extensions, GitHub Apps, browser extensions, or model-provider API plugins.

## 2. Choose the smallest extension type that fits

| Need | Preferred mechanism |
| --- | --- |
| Always-on repository conventions | Repository instructions, such as `AGENTS.md`, `CLAUDE.md`, or Copilot custom instructions |
| A reusable workflow loaded only when relevant | Skill |
| A specialist persona or isolated context with a constrained toolset | Custom agent or subagent |
| Live data or controlled actions in an external system | MCP server |
| Deterministic policy at lifecycle or tool boundaries | Hook, where supported |
| A versioned, installable bundle of related capabilities | Plugin |

Start with one standalone skill while the workflow is changing. Create a plugin when the capability needs distribution, versioning, multiple related components, or external integrations.

## 3. Portable skill contract

### 3.1 Recommended structure

```text
skill-name/
├── SKILL.md             # Required entry point
├── references/          # Optional policies, schemas, and detailed guidance
├── scripts/             # Optional deterministic utilities
└── assets/              # Optional templates and files used in outputs
```

Use `name` and `description` as the portable frontmatter baseline:

```markdown
---
name: pull-request-review
description: Review a pull request for correctness, security, and missing tests. Use for PR review or pre-merge risk assessment; do not use for general code explanation.
---

# Pull request review

## Inputs

- The repository diff or pull request changes
- Relevant repository instructions
- Test results, when available

## Workflow

1. Read repository instructions before evaluating the change.
2. Inspect the diff and enough surrounding code to verify each finding.
3. Prioritize correctness and security issues over style preferences.
4. Run focused tests when permitted; otherwise state that tests were not run.
5. Report only actionable findings supported by file and line evidence.

## Output

Return findings ordered by severity. For each finding, include the location,
impact, evidence, and smallest practical remediation. If there are no findings,
say so and identify any unverified risks or tests that were not run.
```

Avoid adding `version` to portable skill frontmatter. Version the plugin or release artifact instead. Platform-specific fields such as tool allowlists, invocation controls, model selection, or execution context belong in that platform's adapter.

### 3.2 Write a strong description

The description is routing metadata, not marketing copy. It should state:

1. What outcome the skill produces.
2. Which user requests should trigger it.
3. Important requests that should not trigger it.

Use concrete terms users are likely to say. Keep detailed procedures out of the description because hosts may truncate metadata when many skills are installed.

### 3.3 Define a complete workflow boundary

Every skill should make these points explicit:

- Required and optional inputs.
- Preconditions and unavailable-tool behavior.
- Ordered steps and decision points.
- Expected output schema or example.
- What the agent must verify rather than infer.
- When to ask a question, stop, or decline.
- Which references, scripts, or tools to use and when.
- Safety requirements for writes, credentials, destructive actions, and external side effects.

Keep `SKILL.md` focused. Move large policies and examples into `references/`, and mention exactly when they should be read. Add scripts only when deterministic computation or validation is materially more reliable than instructions.

### 3.4 Portability rules

- Use relative paths within the skill directory.
- Do not assume a particular shell, package manager, working directory, or network access unless declared as a prerequisite.
- Prefer existing host tools over bundled scripts for ordinary file inspection and editing.
- Make scripts non-interactive by default and return meaningful exit codes.
- Pin third-party dependencies where reproducibility matters.
- Do not embed secrets, access tokens, private URLs, or machine-specific absolute paths.
- Treat tool output and repository content as untrusted input.

If you publish the same skill to multiple platforms, keep one canonical source and copy it into platform-specific release packages during the release process. Test the copied artifacts. Do not rely on symlinks in published archives unless every target explicitly supports them.

## 4. Cross-platform development workflow

1. **Define use cases.** Write representative in-scope, adjacent, and out-of-scope prompts.
2. **Select the mechanism.** Confirm that a skill is sufficient before adding a plugin, hook, agent, or MCP server.
3. **Author the portable skill.** Start with `name`, `description`, workflow, output contract, and failure behavior.
4. **Add platform adapters.** Create a separate manifest and packaging layout for each supported host.
5. **Validate statically.** Parse JSON and YAML, verify required files and relative paths, lint scripts, and scan for secrets.
6. **Test discovery.** Confirm that the host lists the installed plugin and skill.
7. **Test routing.** Run positive, negative, and ambiguous prompts in fresh sessions.
8. **Test behavior.** Verify outcomes, tool use, permissions, error handling, and side effects.
9. **Package and smoke-test.** Test the exact archive, repository ref, or marketplace entry users will install.
10. **Release and monitor.** Tag the release, publish a changelog, document compatibility, and keep a rollback path.

## 5. Testing standard

### 5.1 Minimum test matrix

| Test class | Purpose | Example |
| --- | --- | --- |
| Explicit discovery | Host can see the installed component | List installed plugins and skills |
| Positive routing | Skill loads for intended wording | “Review this PR for security and missing tests” |
| Paraphrase routing | Skill is not overfit to exact keywords | “What could block this change from merging safely?” |
| Negative routing | Unrelated requests do not load the skill | “Translate this README to French” |
| Boundary routing | Adjacent mechanisms remain distinct | A general style question should use repository instructions, not the PR workflow |
| Golden behavior | Required steps and output fields appear | Findings contain severity, evidence, location, and remediation |
| Empty result | No fabricated findings | Clean change produces a clear no-findings result plus test limitations |
| Missing dependency | Failure is actionable and safe | Unavailable MCP server produces setup guidance, not invented data |
| Permission denial | Least-privilege path works | Read-only run reports that it could not apply changes |
| Adversarial input | Embedded content cannot override safety | Prompt injection in an issue body is treated as data |
| Upgrade regression | New package preserves intended behavior | Re-run the same corpus on the packaged release candidate |

Prefer semantic assertions over brittle keyword checks. Model output is variable even when the model and settings are fixed. Assert required structure, evidence, tool-call constraints, and observable side effects; allow harmless wording differences.

### 5.2 Record evidence

For every supported platform, record:

- Host and CLI version.
- Model when selectable.
- Plugin or skill version and source ref.
- Test prompt.
- Whether the skill was selected.
- Tools and permissions used.
- Result and failure reason.

Run routing tests in fresh sessions so prior conversation context does not hide discovery or trigger problems.

## 6. Security baseline

Plugins and skills are executable supply-chain inputs. Review them as code.

- Inspect `SKILL.md`, scripts, hooks, MCP configuration, and transitive dependencies before installation.
- Grant the least filesystem, shell, network, and external-service permissions needed.
- Keep authentication and authorization enforcement in the MCP server, not in natural-language instructions.
- Validate all tool inputs server-side and require confirmation for consequential writes.
- Never log credentials or unnecessary personal data.
- Pin released dependencies and remote sources to tags or immutable commits when the host permits it.
- Publish checksums or signed releases when distributing archives outside a managed marketplace.
- Document every external endpoint, executable, secret, and data class the plugin can access.
- Separate untrusted repository or issue content from trusted instructions.

## 7. GitHub Copilot — primary platform guideline

GitHub Copilot supports skills across Copilot CLI, the Copilot coding agent, and agent mode in Visual Studio Code. Copilot CLI plugins can bundle skills, custom agents, hooks, MCP servers, and LSP configuration.

### 7.1 Choose the Copilot customization surface

| Requirement | Copilot mechanism |
| --- | --- |
| Conventions that apply to most repository work | `.github/copilot-instructions.md` or path-specific custom instructions |
| On-demand reusable procedure | Agent skill |
| Specialist role with its own prompt and tools | Custom agent (`*.agent.md`) |
| Event-driven enforcement | Hook |
| External tools and data | MCP server |
| Installable bundle for a team or multiple repositories | Copilot plugin |

Do not create a plugin for one experimental repository skill unless packaging or distribution is already required.

### 7.2 Copilot plugin structure

```text
my-dev-tools/
├── plugin.json                 # Required at the plugin root
├── README.md
├── LICENSE
├── agents/                     # Optional
│   └── reviewer.agent.md
├── skills/                     # Optional
│   └── pull-request-review/
│       ├── SKILL.md
│       └── references/
├── hooks.json                  # Optional
├── .mcp.json                   # Optional
└── lsp.json                    # Optional
```

A minimal skills-only manifest is:

```json
{
  "name": "my-dev-tools",
  "description": "Reusable pull request review workflows",
  "version": "1.0.0",
  "license": "MIT",
  "skills": "skills/"
}
```

Only `name` is required by the current Copilot CLI plugin schema. Use kebab case and keep it within 64 characters. Conventional component folders are discovered by default, so explicit component path fields are optional; include them when clarity or a non-default path justifies it.

Consult the [Copilot CLI plugin reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference) before adding manifest fields. Do not assume another host's manifest fields have the same type or meaning.

### 7.3 Standalone Copilot skills

Use one of Copilot's documented project locations:

```text
.github/skills/<skill-name>/SKILL.md
.claude/skills/<skill-name>/SKILL.md
.agents/skills/<skill-name>/SKILL.md
```

Use one of the personal locations for skills shared across local projects:

```text
~/.copilot/skills/<skill-name>/SKILL.md
~/.agents/skills/<skill-name>/SKILL.md
```

Prefer `.github/skills/` for a Copilot-first repository. Prefer `.agents/skills/` when the same standalone skill must be discovered by multiple compatible hosts.

GitHub CLI also provides `gh skill` commands in public preview. Preview untrusted skills before installing them:

```bash
gh skill search code-review
gh skill preview OWNER/REPOSITORY SKILL
gh skill install OWNER/REPOSITORY SKILL
gh skill publish --dry-run
```

Because this interface is preview, pin compatible GitHub CLI versions in automation and recheck `gh skill --help` when upgrading.

### 7.4 Local plugin development loop

Install and inspect the local package:

```bash
copilot plugin install ./my-dev-tools
copilot plugin list
```

In a Copilot CLI session, verify the components:

```text
/plugin list
/agent
/skills list
```

Copilot caches installed plugin components. Reinstall the local path after changes:

```bash
copilot plugin install ./my-dev-tools
```

When testing is complete:

```bash
copilot plugin uninstall my-dev-tools
```

For a one-session development override, current Copilot CLI also supports:

```bash
copilot --plugin-dir ./my-dev-tools
```

Run `copilot --help` and `copilot plugin --help` in the version under test before placing these commands in scripts.

### 7.5 Copilot-specific routing and behavior tests

1. Start a fresh session in a trusted test repository.
2. Confirm `/skills list` shows each bundled skill.
3. Submit at least three positive prompts, including a paraphrase without the skill name.
4. Submit at least three negative prompts from adjacent and unrelated tasks.
5. Verify the agent follows repository custom instructions alongside the selected skill.
6. Verify custom agents appear under `/agent` and use only their intended tools.
7. Trigger each hook event and inspect its exit status and observable effect.
8. Verify each MCP server loads, authenticates, enforces permissions, and fails safely.
9. Reinstall the plugin and repeat a smoke test against the cached installed copy.

Name collisions matter. Project and personal agents or skills can take precedence over plugin components. Use distinctive names and inspect the effective sources when discovery does not match expectations.

### 7.6 Programmatic and CI tests

Use `copilot -p` for a single programmatic prompt. Scope permissions narrowly with `--allow-tool` and `--deny-tool` where possible. Full-permission flags such as `--yolo` or `--allow-all` should be limited to isolated runners and well-understood tasks.

Example read-oriented smoke test:

```bash
copilot \
  --plugin-dir ./my-dev-tools \
  --prompt "Use the pull request review workflow on the current diff. Do not modify files." \
  --output-format json \
  --allow-tool read \
  > copilot-events.jsonl
```

CI should fail on observable contract violations, not on a model merely using different prose. A test harness can check that:

- the plugin and skill were discovered;
- the run completed successfully;
- no denied write or network action occurred;
- required output fields are present;
- cited files and lines exist;
- the result is valid against an expected JSON schema when structured output is used.

For GitHub Actions, follow GitHub's current [Copilot CLI Actions guidance](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli-in-actions), grant only required workflow permissions, and avoid exposing long-lived credentials to repository-controlled code.

### 7.7 Copilot distribution

Copilot CLI can install plugins from a local path, GitHub repository, Git URL, repository subdirectory, or registered marketplace. For a marketplace release:

```bash
copilot plugin marketplace add OWNER/REPOSITORY
copilot plugin marketplace browse MARKETPLACE-NAME
copilot plugin install PLUGIN-NAME@MARKETPLACE-NAME
```

Before publishing:

- Test the exact repository ref or marketplace entry.
- Include README, license, changelog, prerequisites, and uninstall instructions.
- Document supported Copilot surfaces; a CLI plugin capability may not behave identically in cloud agent or IDE contexts.
- Confirm enterprise policies do not block the plugin, MCP servers, or required tools.
- Pin release versions and preserve a previous known-good version for rollback.

Primary references:

- [Creating a plugin for GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-creating)
- [Copilot CLI plugin reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference)
- [Adding agent skills for GitHub Copilot](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills)
- [Copilot CLI programmatic reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference)

## 8. OpenAI Codex

Codex uses skills for reusable workflows and plugins for installable bundles shared with supported ChatGPT surfaces.

### 8.1 Codex plugin structure

```text
my-dev-tools/
├── .codex-plugin/
│   └── plugin.json            # Required
├── skills/
│   └── pull-request-review/
│       └── SKILL.md
├── hooks/                     # Optional
│   └── hooks.json
├── assets/                    # Optional
├── .mcp.json                  # Optional bundled MCP server config
└── .app.json                  # Optional registered MCP connection mapping
```

Only `plugin.json` belongs inside `.codex-plugin/`. Keep components at the plugin root.

Minimal manifest:

```json
{
  "name": "my-dev-tools",
  "version": "1.0.0",
  "description": "Reusable pull request review workflows",
  "skills": "./skills/"
}
```

Keep manifest paths relative to the plugin root and start them with `./`.

### 8.2 Standalone Codex skills

For repository scope, place skills under `.agents/skills/` from the working directory up to the repository root. For personal scope, use `~/.agents/skills/`. Each skill remains a directory containing `SKILL.md`.

Invoke a skill explicitly with `$skill-name`, or let Codex select it from its description. Use `$skill-creator` to create a skill and `$plugin-creator` to scaffold or update a Codex plugin.

### 8.3 Local development and distribution

Codex plugins are installed from configured marketplaces; a raw local plugin path is not a substitute for a marketplace entry. For local development, create a personal or repository marketplace, add the plugin entry, then install and test the cached installed copy in a fresh task.

Useful CLI commands include:

```bash
codex plugin marketplace add ./local-marketplace-root
codex plugin marketplace list
codex plugin add my-dev-tools@marketplace-name
codex plugin list --json
codex plugin remove my-dev-tools@marketplace-name
```

Use `codex plugin marketplace upgrade` for Git-backed marketplace updates. When iterating on a local cached plugin, follow the current plugin-creator update and reinstall workflow rather than editing installed cache files.

Use `codex exec` for non-interactive tests:

```bash
codex exec --json \
  "Use the pull-request-review skill on the current diff. Do not modify files."
```

Set the least sandbox and approval permissions the test requires. Do not use `danger-full-access` for routine plugin verification.

Primary references:

- [Build plugins](https://developers.openai.com/plugins/build/plugins)
- [Build skills](https://developers.openai.com/plugins/build/skills)
- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)

## 9. Claude Code

Claude Code supports standalone skills and plugins containing skills, custom agents, hooks, MCP servers, LSP servers, monitors, executables, and supported default settings.

### 9.1 Claude Code plugin structure

```text
my-dev-tools/
├── .claude-plugin/
│   └── plugin.json            # Plugin identity
├── skills/
│   └── pull-request-review/
│       └── SKILL.md
├── agents/                    # Optional
├── hooks/                     # Optional
│   └── hooks.json
├── monitors/                  # Optional
│   └── monitors.json
├── bin/                       # Optional executables
├── .mcp.json                  # Optional
├── .lsp.json                  # Optional
└── settings.json             # Optional supported defaults
```

Only `plugin.json` belongs inside `.claude-plugin/`. Other components remain at the plugin root.

Minimal manifest:

```json
{
  "name": "my-dev-tools",
  "description": "Reusable pull request review workflows",
  "version": "1.0.0"
}
```

### 9.2 Standalone skills and invocation

Use `.claude/skills/<skill-name>/SKILL.md` for a project skill and `~/.claude/skills/<skill-name>/SKILL.md` for a personal skill. Claude can select a skill from its description, or users can invoke it as `/skill-name`.

Claude Code supports additional skill frontmatter, including invocation and execution controls. Keep these additions in the Claude adapter and test behavior against the minimum supported Claude Code version.

Plugin skill names are namespaced. Test them explicitly as:

```text
/plugin-name:skill-name
```

### 9.3 Development, validation, and release

Load a plugin directly during development:

```bash
claude --plugin-dir ./my-dev-tools
```

Use `/reload-plugins` after edits. Validate before submission:

```bash
claude plugin validate ./my-dev-tools
claude plugin validate --strict ./my-dev-tools
```

Use `claude -p` for non-interactive behavior tests:

```bash
claude --plugin-dir ./my-dev-tools \
  -p "Use the pull-request-review skill on the current diff. Do not modify files."
```

Distribute through a Claude Code marketplace when users need installation and updates. Test the marketplace install rather than only `--plugin-dir`, because installed components and update behavior can differ from direct development loading.

Primary references:

- [Create Claude Code plugins](https://code.claude.com/docs/en/plugins)
- [Claude Code plugin reference](https://code.claude.com/docs/en/plugins-reference)
- [Claude Code skills](https://code.claude.com/docs/en/slash-commands)

## 10. Google Antigravity

Antigravity IDE and Antigravity CLI both support skills, but discovery paths and lifecycle details can differ by surface and version. Test both surfaces when claiming both are supported.

### 10.1 Standalone skills

For current Antigravity IDE guidance:

```text
<project-root>/.agents/skills/<skill-name>/SKILL.md
~/.gemini/config/skills/<skill-name>/SKILL.md
```

Some Antigravity CLI documentation and versions use CLI-specific locations such as `.agent/skills/` or `~/.gemini/antigravity-cli/skills/`. Do not copy a path from an IDE example into CLI automation without verifying the installed CLI's documentation and discovery output.

A portable skill keeps the same core structure:

```text
my-skill/
├── SKILL.md
├── scripts/
├── references/
└── assets/
```

Start a new conversation and confirm the skill is listed, then test both automatic selection and the surface's current slash-command invocation.

### 10.2 Plugins

Antigravity plugins can bundle skills with MCP servers, rules, hooks, and other supported components. Install a trusted Git-backed plugin in Antigravity CLI with the current documented form:

```bash
agy plugin install https://github.com/OWNER/REPOSITORY
```

Then restart `agy` when required and inspect skills with:

```text
/skills
```

Antigravity's public plugin authoring specification is less stable and less fully documented than its skill workflow. Before publishing an Antigravity package:

- Inspect `agy plugin --help` for the installed version.
- Start from a current Google-maintained plugin example.
- Verify the manifest and every bundled component in both IDE and CLI targets.
- Document which target and version were tested.
- Avoid claiming cross-surface support based only on successful installation in one surface.

Primary references:

- [Authoring Google Antigravity Skills](https://codelabs.developers.google.com/getting-started-with-antigravity-skills)
- [Getting Started with Antigravity IDE](https://codelabs.developers.google.com/getting-started-agy-ide)
- [Antigravity CLI skills and plugins](https://codelabs.developers.google.com/gemini-mcp-agy)
- [Antigravity documentation](https://antigravity.google/docs/home)

## 11. Cross-platform release layout

For a repository that publishes to all four platforms, keep platform packaging explicit:

```text
plugin-project/
├── skill-src/                     # Canonical portable skills
│   └── pull-request-review/
├── packages/
│   ├── github-copilot/
│   │   ├── plugin.json
│   │   └── skills/
│   ├── codex/
│   │   ├── .codex-plugin/plugin.json
│   │   └── skills/
│   ├── claude-code/
│   │   ├── .claude-plugin/plugin.json
│   │   └── skills/
│   └── antigravity/
│       └── ...                    # Follow the verified target specification
├── tests/
│   ├── prompts/
│   ├── expected-contracts/
│   └── platform-smoke/
├── CHANGELOG.md
└── README.md
```

Generate or copy portable skills into each package, then apply host-specific metadata only in that package. A release is complete only when every advertised package passes its own discovery, routing, behavior, security, and packaged-artifact smoke tests.

## 12. Release checklist

### Portable skill

- [ ] `name` and `description` are valid, concise, and accurately routed.
- [ ] Positive, paraphrase, negative, and boundary prompts pass.
- [ ] Inputs, outputs, decision points, and failure behavior are explicit.
- [ ] References and scripts use relative paths and are actually reachable.
- [ ] No secrets, private endpoints, or machine-specific paths are present.

### Platform adapter

- [ ] Manifest and directory structure match current official documentation.
- [ ] The minimum supported host and CLI versions are documented.
- [ ] Install, list, reload or reinstall, update, and uninstall paths are tested.
- [ ] Name collisions and precedence are tested.
- [ ] Hooks, MCP servers, agents, and scripts use least privilege.
- [ ] The exact marketplace entry, repository ref, or archive passes a fresh install.

### Distribution

- [ ] README explains purpose, install, invocation, permissions, troubleshooting, and removal.
- [ ] License, changelog, version, ownership, support, and security-reporting paths are present.
- [ ] Dependencies and external services are disclosed and pinned where appropriate.
- [ ] CI assertions tolerate harmless model variation and catch unsafe side effects.
- [ ] A known-good rollback version remains available.
