# CLAUDE.md — Project Rules for Agent Ops Demo

## Project Context
This is a demo project for a Loom recording. All console output must look polished and professional.

## Tech Stack
- Python 3
- Use the `rich` library for ALL terminal output (tables, panels, spinners, progress bars, etc.)
- Use the Anthropic Python SDK for Claude API calls

## Code Style
- Favor readability over abstraction. Comment liberally.
- Keep files focused — one responsibility per module.
- No overly clever code. This needs to be scannable in a video demo.

## Agent Response Handling
- All agent responses must be valid JSON.
- Always strip markdown code fences before parsing JSON from LLM responses.
- Validate JSON before processing — never assume well-formed output.

## Terminal Output
- Never use bare `print()`. Always use `rich` console objects.
- Error messages should be styled in red with `[bold red]` markup.
- Success messages should use `[bold green]`.
- Use `rich.panel.Panel` for agent responses displayed to the user.

## Mistakes Log (update when corrections are made)
- (none yet)
