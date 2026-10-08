# Synthetic Query Prompt v1

You are creating training queries for a legal search system over Kazakhstan legislation.

Given one article:

- Write one plain-language question a real user might ask.
- Write one terminology-heavy legal query.
- Use the same language as the article.
- Do not copy the article title verbatim.
- Do not include the article number unless the query is explicitly an article-reference case.
- Keep each query between 4 and 30 words.
- Return JSON lines with `text`, `lang`, `persona`, `query_type`, and `answerable=true`.

Reject queries that are too broad, mention facts not in the article, or require another act unless
the source article itself clearly points to that act.
