# LLM Usage Plan for Phase 2

## Why we are using an LLM

ACME's Phase 2 spec requires effective use of LLMs during development and for non-implementation tasks.

We use LLMs to:

- Speed up implementation (skeleton code, refactors, test ideas).
- Improve security + reliability (ask for threat ideas, edge cases).
- Improve documentation (summaries, explanations for teammates and TAs).
- Optionally analyze package metadata/model cards to generate human-readable summaries (via Bedrock later).

## Which tools

- **ChatGPT / Claude**: design help, code review suggestions, docs.
- **GitHub Copilot**: inline code completions and PR auto-review (matches "Dependabot + CoPilot PR Auto-Review" in the spec).
- (Planned) **Amazon Bedrock**: light inference to summarize package metadata and flag potentially sensitive modules (see Design AWS homework).

We always:

- Review and edit generated code by hand.
- Never paste secrets, tokens, or private data into prompts.
- Keep LLM suggestions under version control like any other code.

## How we use LLMs to assist implementation

**Code + tests**

- Generate initial FastAPI route skeletons from the Phase 2 OpenAPI spec.
- Draft first versions of metrics / helpers in `src/acmecli/metrics/*.py`, then refactor manually.
- Brainstorm edge cases and unit tests for:
  - `/artifacts` CRUD and `/reset` endpoints.
  - New metrics like Reproducibility, Reviewedness, TreeScore.

**AWS + Terraform**

- Ask LLMs to explain AWS + Terraform errors and propose least-privilege IAM snippets, then we trim and test them ourselves.
- Use LLMs to draft CloudWatch/monitoring descriptions based on our actual architecture.

**Security + design**

- Use LLMs to:
  - Suggest STRIDE threats from our DFDs and trust boundaries.
  - Draft text for the security case and mitigation tables that we then review against lecture material.

## How we use LLMs for non-implementation tasks

- Draft and refine:
  - `README.md` explanations of runtime data flow and metrics.
  - Design HW answers (cost table, Bedrock vs SageMaker tradeoffs).
  - User-facing docs for how to ingest models, interpret scores, and reset the system.

- Summarize long logs or autograder runs into short status updates for the team.

## (Optional) In-system LLM usage

We plan a **lightweight LLM-backed helper**:

- When a new package is ingested, the validator can:
  - Send README / model card text to an LLM endpoint (Bedrock).
  - Ask for a short summary + flags (e.g., "safety concerns", "missing license info").
  - Store that as `llm_summary` in metadata and show it in the UI.

This uses the same "analyze package metadata, generate summaries/flags" idea from the Design AWS homework.

This feature is:

- **Behind a feature flag** so tests/autograder run without needing Bedrock.
- Implemented via a small client module (e.g., `src/services/llm_client.py`) that we can stub in unit tests.

## Example Prompts Used During Development

We documented some of the prompts we used to help design features:

- **`docs/llm_examples/reproducibility_metric_prompt.txt`**: Prompt used to brainstorm the Reproducibility metric design
- **`docs/llm_examples/threat_model_prompt.txt`**: Prompt used to identify STRIDE threats for security analysis

These examples show how we used LLMs (ChatGPT/Claude) during development to help design features, which we then implemented manually.

## Documentation

For detailed information about the LLM Summary Metric implementation, see:

- **`docs/LLM_SUMMARY_METRIC.md`**: Complete documentation of the LLM Summary Metric, including usage, configuration, and examples.
