# ADR-001 — Inference Engine

**Status:** Accepted  
**Date:** 2026-03-13

## Decision

Use Ollama running llama3.1:70b on the Mac Studio M3 as the local inference engine.

## Reasoning

- Runs entirely offline on the home network
- 96GB unified memory supports the 70b model comfortably
- Ollama provides a simple REST API that Flask can call directly
- No cloud costs or data leaving the network

## Alternatives considered

- Raspberry Pi 5 with a smaller model — rejected, too slow (3–5 tokens/second)
- Cloud API (OpenAI, Anthropic) — rejected, defeats the local-first goal

## Consequences

All features must be designed around local inference latency. Complex multi-step reasoning tasks will be slower than cloud alternatives.
