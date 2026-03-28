---
name: "job-posting-collector"
description: "Use when collecting IT or software-engineering job postings across Korean job boards and professional networks, storing both raw and normalized data, extending site-specific collectors, or validating detail-page extraction and deduplication."
---

# Job Posting Collector

Use this skill when the task is about multi-site IT job collection, raw snapshot storage, normalized data generation, or unified browsing of collected postings.

## Workflow

1. Read `references/collection-charter.md` to align with the project identity and guardrails.
2. Read `references/site-playbook.md` before changing any site adapter.
3. Treat the web app as a review surface. Trigger collection from Codex or another AI agent, not from the web UI.
4. When the user asks for broad coverage, split site validation or sampling by subagent so each site can be checked independently.
5. Prefer this discovery order per site:
   - public API
   - sitemap
   - static HTML
   - browser-rendered extraction
   - external search fallback
6. Store both raw and normalized data.
7. Keep deduplication URL-centered, but preserve site-specific metadata and snapshot hashes.
8. When a site is access-limited, label it best-effort instead of pretending coverage is complete.
9. Verify the saved data from the unified jobs view after collection, including inline detail rendering and raw snapshot access.

## Required outputs

- raw snapshot references
- normalized posting records
- clear coverage notes per site
- verification result with at least one concrete sample per new adapter

## References

- Mission and architecture: `references/collection-charter.md`
- Site collection rules: `references/site-playbook.md`
