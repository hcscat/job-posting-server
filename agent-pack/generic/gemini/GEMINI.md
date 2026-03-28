# Job Posting Collection Skillset For Gemini

You are working on a multi-site IT job collection system.

## Mission

Collect IT and software-engineering job postings from multiple Korean job boards on explicit user request. Save both raw artifacts and normalized records. Make the results queryable in a unified web interface.

## Operating rules

- Treat the collector as the primary system.
- Use AI for extraction, classification, summarization, and repair assistance.
- Prefer public API, then sitemap, then static HTML, then browser-rendered extraction, then search fallback.
- Keep per-site coverage honest. Mark blocked sites as best-effort.
- Preserve raw data and normalized data together.
- Use normalized URL as the main deduplication key.

## Output expectations

- site-by-site coverage notes
- raw snapshot references
- normalized posting records
- sample validation results
