# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **general personal life assistant (通用个人生活助手)** — a WeChat Mini Program frontend backed by a FastAPI + ReAct-agent backend. Clothing/outfit management and recommendation is the **first domain** being developed; the assistant is designed to expand to other life domains (food, travel, etc.) later. The agent core is deliberately domain-agnostic — prompts and tooling must **not** hard-bind to clothing.

The README and user-facing strings are in Chinese — prefer Chinese for user-facing text.

## Current State

The backend is scaffolded and the agent core is ported (single-process ReAct loop folded into FastAPI). Layout:

- `backend/fastapi_app/` — REST API: WeChat `code2session` login, HS256 JWT auth, clothing CRUD with per-user isolation.
- `backend/agent/` — ReAct agent core (ported from the internal `twinkle` framework, stripped to a stream-only `LoopEvent` loop): `react_loop.py` (`ReActAgent` async generator), `tools/` (framework), `llm_client.py`, `sessions/` (JSONL history), `hooks/`, `prompts.py`, `permissions/` (approval registry), `events.py` (`LoopEvent`).
- `backend/tests/` — pytest suite; run from `backend/` with `python -m pytest -q` (currently 18 passing).

Key design constraints: **no `max_steps` cost guard** (only an anti-infinite-loop backstop); destructive tool calls route through the `permissions/approval_registry` flow (future Phase 2 wiring); built-in tools (subagent/skills/cron/web_search/file/todo) are preserved for later phases.

The WeChat Mini Program frontend (`pages/`/`components/`) is not yet built; it will use `wx.request` (REST) + `wx.connectSocket` (streaming) against this backend.

## Repository Notes

This directory **is** a git repository on branch `main`. There is no remote configured — all work is local-only.
