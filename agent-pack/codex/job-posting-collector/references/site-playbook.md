# Site Playbook

## Preferred discovery strategy

1. Public API
2. Sitemap with detail URLs
3. Static search/list HTML
4. Browser-rendered extraction
5. External search fallback

## Storage rules

- Save raw HTML/XML/JSON snapshots for listing and detail fetches.
- Save normalized records with:
  - site key and site name
  - canonical URL
  - company, title, location, employment, experience, education
  - summary and full detail text
  - AI-enriched fields
  - snapshot hashes
- Preserve per-run artifacts separately from the latest DB state.

## Deduplication rules

- Primary key: normalized URL
- Update `last_seen_at` and `seen_count` on re-discovery
- Re-fetch details based on staleness, not every run

## Coverage labeling

- `stable`: direct API, sitemap, or reliable HTML path is available
- `best-effort`: access-limited, search-engine-dependent, or browser-only path

## Validation checklist

- fetch at least one listing result
- fetch at least one detail page
- confirm description length is materially useful
- confirm normalized URL is stable
- confirm raw snapshot is readable
