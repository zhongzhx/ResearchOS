---
name: compliant-literature-access
description: Resolve and download scholarly full text through compliant access paths for keyword queries, DOI lists, CSV bibliographies, and publisher links. Use when Codex needs to retrieve papers through current campus IP/VPN access, open access, Crossref TDM links, publisher API/TDM links, EZproxy, or locally stored institutional credentials while preserving audit logs and avoiding paywall bypass, credential leakage, or redistribution.
---

# Compliant Literature Access

## Overview

Use this skill to resolve legal full-text access for scholarly records and download only content the user can access through open access, publisher-provided TDM/API links, campus IP/VPN, or institution-owned proxy credentials. Treat it as an access and audit layer, not as a paywall bypasser.

## Guardrails

- Do not ask the user to paste passwords into chat. Use `scripts/save_credentials.py` to store credentials locally and interactively.
- Do not write passwords, session cookies, API keys, or authorization headers to configs, logs, manifests, or output reports.
- Do not automate CAPTCHA, MFA, SSO consent screens, or anti-bot workarounds. If a site requires those, stop and use the official TDM/API path or a user-controlled browser workflow.
- Do not use one user's institutional entitlement for another user or customer.
- Do not put subscription full text into shared training data, public datasets, or cross-customer caches.
- Keep license, source, access method, and timestamp in the audit log for every attempted DOI.

## Quick Start

### Simplest campus-network mode

Use this when the user's computer is already on a campus network or connected to the school VPN and the goal is simply: "try to download the article through the current network entitlement."

Keyword input:

```powershell
py .\scripts\download_by_keyword_on_campus.py --query "machine learning cancer diagnosis" --max-results 20 --output-root ".\access_runs"
```

Optional browser-use fallback:

```powershell
py .\scripts\download_by_keyword_on_campus.py --query "machine learning cancer diagnosis" --max-results 20 --output-root ".\access_runs" --browser-fallback
```

`--browser-fallback` requires the `browser-use` CLI on PATH. If only the repository has been downloaded but not installed, the run records `browser_unavailable` and continues with metadata/abstract analysis.

When the adjacent `extract-first-article-keywords` skill exists, this keyword mode automatically analyzes each article as it is processed. For every candidate/download, it extracts abstract background, methods, results, conclusion, and search-expansion terms. Disable that with `--no-article-analysis`.

DOI input:

```powershell
py .\scripts\download_on_campus.py --doi "10.xxxx/example" --output-root ".\access_runs"
```

For a CSV:

```powershell
py .\scripts\download_on_campus.py --input-csv ".\papers.csv" --doi-column DOI --output-root ".\access_runs"
```

This mode does not save credentials and does not use EZproxy. For keyword input, it first searches Crossref/OpenAlex for matching journal articles, then tries DOI/publisher landing pages and Crossref full-text/TDM links through the current network. If the school IP/VPN has access, the download may succeed; otherwise the audit log records the failure.

### Configured mode

1. Copy `references/access_config_template.json` into the user's project and edit email, EZproxy, and request settings.
2. If institutional credentials are needed, save them locally:

```powershell
py .\scripts\save_credentials.py --service my-school-ezproxy --username "<campus_user>"
```

3. Resolve and download one DOI:

```powershell
py .\scripts\resolve_fulltext_access.py --doi "10.1038/nature12373" --config .\references\access_config_template.json --output-root ".\access_runs"
```

4. Resolve and download a CSV:

```powershell
py .\scripts\resolve_fulltext_access.py --input-csv ".\papers.csv" --doi-column DOI --config ".\my_access_config.json" --output-root ".\access_runs"
```

## Access Priority

Try access paths in this order:

1. Open access links from Unpaywall or publisher metadata.
2. Crossref TDM/full-text links and license metadata.
3. Direct publisher access through the user's current campus IP or VPN.
4. EZproxy/simple proxy form login using locally stored credentials.
5. Mark as `no_legal_access` if no allowed route succeeds.

## Bundled Scripts

- `scripts/save_credentials.py`: save, list, test, or delete institution credentials from the local machine. On Windows it stores the password using current-user DPAPI encryption. It never prints the password.
- `scripts/resolve_fulltext_access.py`: resolve DOI access paths, download PDFs/HTML/XML where allowed, and write audit logs.
- `scripts/download_on_campus.py`: simplified current-network downloader for campus IP/VPN testing without credentials or config editing.
- `scripts/download_by_keyword_on_campus.py`: simplest workflow: search by keyword, build candidate DOI table, then download through current campus IP/VPN access.
- `scripts/browser_use_literature_probe.py`: optional browser-use fallback for opening landing pages and discovering PDF/full-text links when direct download fails.
- `scripts/credential_store.py`: shared credential storage helper used by the other scripts.

## Outputs

Each run folder contains:

- `downloads/`: retrieved full-text files.
- `access_log.csv`: row-per-attempt audit table.
- `access_log.jsonl`: full machine-readable audit events.
- `access_summary.md`: counts by DOI, success, format, and unresolved access.

## Configuration Notes

Read `references/access_config_template.json` before preparing a new run. Important fields:

- `email`: required for Unpaywall and useful for polite API identification.
- `access_modes`: enable or disable open access, Crossref TDM, campus IP/VPN discovery, and EZproxy.
- `ezproxy.service`: credential service name saved with `save_credentials.py`.
- `publisher_headers`: optional per-domain headers. Prefer `env:VARIABLE_NAME` values for API keys.
- `download.save_html`: allow saving full-text HTML/XML when PDF is not available.

## Known Limits

- Simple EZproxy form login is supported. SSO, OpenAthens, MFA, CAPTCHA, and JavaScript-heavy login flows are intentionally not automated.
- HTML parsing is conservative. The resolver looks for common PDF/full-text links and citation metadata but will not reverse-engineer publisher-specific protections.
- For bulk subscription mining, prefer official publisher TDM APIs and institution-approved licenses over browser-style downloading.
