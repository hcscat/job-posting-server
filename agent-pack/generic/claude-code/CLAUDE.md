# Job Posting Collection Skillset For Claude Code

This project is a manual, multi-site IT job collection system.

## Core objective

When the user requests a collection run, gather IT and software-engineering job postings from the configured job boards, store raw listing/detail artifacts, normalize the data, and expose it through the web app.

## Rules

- The collector is deterministic first, AI-assisted second.
- Use AI for detail extraction, IT-job classification, summarization, and operator support.
- Per site, prefer:
  - public API
  - sitemap
  - static HTML
  - browser-rendered extraction
  - search fallback
- Do not overstate coverage for blocked sites.
- Preserve run-level raw archives and latest normalized DB state.
- Keep deduplication URL-centered.

## Deliverables

- collector changes
- raw and normalized storage behavior
- unified web browsing support
- verification notes for every new site adapter
