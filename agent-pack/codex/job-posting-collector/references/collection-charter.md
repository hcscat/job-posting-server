# Collection Charter

## Objective

Collect IT and software-engineering job postings from multiple job sites on user request, store raw artifacts and normalized records together, and make the results browsable from the web app.

## Identity

This is a data collection system with AI-assisted enrichment.

- The collector is the primary system.
- AI is used for extraction, classification, summarization, and operator assistance.
- The system is not a free-form autonomous browsing agent.

## Success criteria

- multi-site collection works on user-triggered runs
- daily raw archives are preserved
- normalized records are queryable in one interface
- detail-page content is captured whenever accessible

## Guardrails

- do not claim full coverage for a blocked site
- do not drop raw data once collected
- do not overwrite normalized data without preserving latest-seen tracking
- do not rely on a single search-engine-only path when a direct API or sitemap exists
