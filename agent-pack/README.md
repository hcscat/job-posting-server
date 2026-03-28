# Job Posting Collection Agent Pack

This directory bundles reusable agent guidance for multi-site IT job collection. It is designed to be copied or zipped as a portable pack for Codex, Gemini, and Claude Code.

## Layout

- `codex/job-posting-collector/`
  Codex skill folder with `SKILL.md`, `agents/openai.yaml`, and reference files.
- `generic/gemini/GEMINI.md`
  Prompting guidance for Gemini-style agents.
- `generic/claude-code/CLAUDE.md`
  Prompting guidance for Claude Code style agents.
- `install-codex-skill.sh`
  Git Bash installer for the Codex skill.
- `install-codex-skill.ps1`
  PowerShell installer for the Codex skill.

## Goal

Use the same operating model across agents:

- collect IT and developer job postings across many sites
- preserve both raw data and normalized data
- keep URL-centered deduplication
- treat access-limited sites as best-effort instead of claiming full coverage
- verify each new adapter with at least one concrete sample

## Sharing

- Share the entire `agent-pack/` directory as-is.
- For Codex users, the install scripts copy the packaged skill into the local Codex skills directory.
- For Gemini or Claude Code, send the matching markdown guide as the base system or project instruction.
- Keep the pack together so the skill, references, and installers stay in sync.

## Codex

Git Bash:

```bash
./agent-pack/install-codex-skill.sh
```

PowerShell:

```powershell
.\agent-pack\install-codex-skill.ps1
```

After installation, Codex can use the `job-posting-collector` skill.

## Gemini

Use `generic/gemini/GEMINI.md` as the base instruction set for Gemini agents working on this project.

## Claude Code

Use `generic/claude-code/CLAUDE.md` as the base instruction set for Claude Code agents working on this project.

## Reference Documents

- Project identity: `docs/project-identity.ko.md`
- Codex skill: `codex/job-posting-collector/SKILL.md`
- Collection charter: `codex/job-posting-collector/references/collection-charter.md`
- Site playbook: `codex/job-posting-collector/references/site-playbook.md`
