# Researcher Agent (Worker)

## Responsibility
Executes specific leaf-node tasks using external tools (Search, Scraper).

## Interface
- **Input:** `Task (string)`, `Context (optional)`
- **Output:** `Claim (string)`, `SourceURL (string)`, `SupportingText (string)`

## Constraints
- **Atomic Outputs:** Must return structured data, not conversational prose.
- **Drift Detection:** If the search yields information outside the current node's scope, it flags it as a `Discovery` rather than forcing it into the `Claim`.