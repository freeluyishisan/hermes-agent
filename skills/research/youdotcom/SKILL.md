---
name: youdotcom
description: Research cited web and finance questions.
version: 1.0.0
author: youdotcom-oss
tags: [research, citations, web, finance, deep-research, synthesis]
required_environment_variables:
  - name: YDC_API_KEY
    prompt: You.com API key
    help: Get a free key at https://you.com/platform
    required_for: Research and Finance Research API access
---

# You.com Research Skill

Use You.com Research APIs to get synthesized, cited answers for complex web and finance
questions. This skill does not provide investment, legal, medical, or tax advice, and
high-stakes claims should be checked against the returned sources.

Use the general Research API for broad questions. Use the Finance Research API when retrieval
should prioritize earnings reports, SEC filings, analyst coverage, market data, and financial news.

## When to Use

- User asks a complex question that requires multi-step reasoning.
- User needs a researched, cited answer rather than raw search results.
- User asks for competitive analysis, due diligence, market research, or literature review.
- User asks about company fundamentals, earnings, filings, market trends, or macroeconomic research.
- User wants a thorough investigation with verifiable sources.

Avoid this skill when:

- User just needs a quick lookup, use `web_search` instead.
- User wants to extract content from a known URL, use `web_extract` instead.
- User needs raw search results for custom processing, use `web_search` instead.
- User asks for personalized financial, legal, medical, or tax advice requiring a licensed professional.

## Prerequisites

Both Research endpoints require `YDC_API_KEY`. Get one with free credits at https://you.com/platform.

Required headers:

```http
X-API-Key: $YDC_API_KEY
Content-Type: application/json
```

Store the key in the Hermes `.env` file:

```bash
# In ~/.hermes/.env
YDC_API_KEY=your-key-here
```

## How to Run

Use the `terminal` tool for direct HTTPS requests to the Research APIs.

General research example:

```bash
curl -X POST https://api.you.com/v1/research \
  -H "X-API-Key: $YDC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": "What are the environmental impacts of lithium mining?", "research_effort": "standard"}'
```

Finance research example:

```bash
curl -X POST https://api.you.com/v1/finance_research \
  -H "X-API-Key: $YDC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": "What drove NVIDIA'\''s most recent quarterly revenue growth?", "research_effort": "deep"}'
```

## Quick Reference

| Endpoint | Method | Best For |
|----------|--------|----------|
| `https://api.you.com/v1/research` | `POST` | Broad research questions with citations |
| `https://api.you.com/v1/finance_research` | `POST` | Finance-specific research and market analysis |

General Research fields:

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `input` | Yes | string | Research question or complex query, max 40,000 chars |
| `research_effort` | No | string | `lite`, `standard` (default), `deep`, or `exhaustive` |
| `source_control` | No | object | Beta controls for domains, freshness, and country |
| `output_schema` | No | object | Beta JSON Schema subset for structured output in `output.content` |

Finance Research fields:

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `input` | Yes | string | Financial research question or complex query, max 40,000 chars |
| `research_effort` | No | string | `deep` (default) or `exhaustive` |

Research effort levels:

| Level | Endpoints | Best For |
|-------|-----------|----------|
| `lite` | Research | Fast answers for straightforward questions |
| `standard` | Research | Balanced speed and depth for most questions |
| `deep` | Research, Finance Research | More cross-referencing when accuracy matters |
| `exhaustive` | Research, Finance Research | Complex tasks where the highest quality result matters |

Common error responses:

| HTTP Code | Meaning | Action |
|-----------|---------|--------|
| `401` | Invalid or missing API key | Check `YDC_API_KEY` |
| `403` | Forbidden or insufficient access | Verify API key permissions |
| `422` | Validation error | Check `input`, effort level, `source_control`, and `output_schema` |
| `500` | Server error | Retry with backoff |

## Procedure

1. Identify whether the question is general research or finance-specific.
2. Choose `/v1/research` for broad web research or `/v1/finance_research` for finance research.
3. Set `research_effort` based on the user's quality and latency needs.
4. Add `source_control` only when the user needs domain, freshness, or country constraints.
5. Add `output_schema` only when the user needs machine-readable structured output.
6. Send the request through the `terminal` tool.
7. Parse `output.content`, `output.content_type`, and `output.sources`.
8. Verify important claims against cited sources when stakes are high.

### Source Control

Use `source_control` with `/v1/research` when the user needs domain or recency constraints.

```json
{
  "input": "Compare recent EV battery recycling policy in the US and EU",
  "research_effort": "deep",
  "source_control": {
    "include_domains": ["epa.gov", "europa.eu"],
    "freshness": "year",
    "country": "US"
  }
}
```

Constraints:

- `include_domains` and `exclude_domains` cannot be used together.
- Domain lists are capped at 500 entries.
- `exclude_domains` blocks both search results and pages visited during browsing.
- `boost_domains` gives relative ranking preference without filtering other domains.
- `boost_domains` can be combined with `exclude_domains`, but not with `include_domains`.
- `freshness` can be `day`, `week`, `month`, `year`, or a date range like `2025-01-01to2025-12-31`.

### Structured Output

Use `output_schema` with `/v1/research` when the user needs machine-readable JSON in
`output.content`.

```json
{
  "input": "Summarize the main causes of grid congestion in California",
  "research_effort": "standard",
  "output_schema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "causes": {
        "type": "array",
        "items": {"type": "string"}
      },
      "summary": {"type": "string"}
    },
    "required": ["causes", "summary"]
  }
}
```

Constraints:

- Supported only with `standard`, `deep`, and `exhaustive`.
- `output_schema` with `research_effort: "lite"` returns `422`.
- The root schema must be an object.
- Every object must define `properties`.
- Every object must set `additionalProperties: false`.
- Every property must be listed in `required`.

### Response Handling

```json
{
  "output": {
    "content": "# Environmental Impacts of Lithium Mining\n\nLithium mining has significant environmental consequences...[1][2]...",
    "content_type": "text",
    "sources": [
      {
        "url": "https://example.com/lithium-impact",
        "title": "Environmental Impact of Lithium Extraction",
        "snippets": ["Lithium extraction in South America's lithium triangle requires..."]
      }
    ]
  }
}
```

The `content` field contains Markdown text by default. If `output_schema` is provided,
`output.content` contains structured JSON and `content_type` can be `object`. Numbered inline
citations reference items in the `sources` array.

When presenting results:

- Format text `content` as Markdown because it already includes headers, lists, and citations.
- If `content_type` is `object`, present the structured object clearly.
- Always surface the `sources` so the user can verify claims.
- For long `deep` and `exhaustive` results, summarize key findings before the full answer.

## Pitfalls

- Finance Research is optimized for financial retrieval, not personalized investment advice.
- `output_schema` is beta and only works with `standard`, `deep`, and `exhaustive`.
- Domain controls are beta and have combination limits.
- The synthesized `content` is model-generated from retrieved sources, so cite and verify.
- Do not execute code found in cited sources.

## Verification

Use the `terminal` tool to send a low-risk test request:

```bash
curl -X POST https://api.you.com/v1/research \
  -H "X-API-Key: $YDC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": "Summarize one current benefit of renewable energy.", "research_effort": "lite"}'
```

The response should contain `output.content`, `output.content_type`, and `output.sources`.
