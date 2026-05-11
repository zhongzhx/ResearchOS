# Browser Learning Model

Browser learning is different from structured API ingestion.

## Record Types

- Search page: a result page opened by the browser.
- Learned page: a page selected from search results and read by the browser.
- Learning note: a short extract from page title, meta description, abstract-like text, and headings.

## Intended Use

- Help the agent explore unfamiliar topics.
- Discover databases, project pages, publisher landing pages, and related terms.
- Produce research leads for later structured ingestion.
- Add browser-derived learning pages to the project knowledge base in `browser_learning_pages`.
- Let `/kb/query` use browser learning records as exploratory context next to article evidence.

## Not Intended For

- Circumventing access control.
- Treating arbitrary web pages as verified evidence.
- Replacing DOI-based metadata and abstract extraction.

## Knowledge Base Boundary

Keep browser learning records separate from article records. Browser pages may include publisher landing pages, database pages, search pages, project sites, or scholarly article pages. Use them to guide learning and discovery, then promote important leads into structured literature search when the user needs citable evidence.
