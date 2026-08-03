# Atlas AI Reliability Report

**Date:** 2026-07-29  
**Suite:** `tests/test_runtime.py`, `test_provider.py`, `test_streaming.py`, `test_long_prompt.py`, `test_cancellation.py`, `test_thread_cleanup.py`, `test_shutdown.py`  
**Helper:** `tests/reliability_support.py`  
**Result:** **PASS** — 22 tests, 0 failures, 0 errors, 0 skips  
**Runtime:** ~35s (live Ollama `qwen3:8b` at `http://127.0.0.1:11434`)

## How to run

```bash
python -m unittest tests.test_runtime tests.test_provider tests.test_streaming \
  tests.test_long_prompt tests.test_cancellation tests.test_thread_cleanup \
  tests.test_shutdown -v
```

Live tests call `RuntimeManager.ensure_running("ollama")` and skip the class if Ollama cannot be started. A healthy local Ollama with at least one installed model is required for a full gate.

## Coverage matrix

| Requirement | Test(s) | Status |
|---|---|---|
| Runtime autostart | `test_runtime.RuntimeAutostartTests` | PASS |
| Runtime autostop / ownership | `test_shutdown.ShutdownLiveTests`, `ShutdownUnitTests` | PASS |
| Streaming responses | `test_streaming` (unit merge + live progress) | PASS |
| Large prompts (>25k chars) | `test_long_prompt.test_prompt_over_25k_chars` | PASS |
| Large completions | `test_long_prompt.test_large_completion` | PASS |
| Cancellation during generation | `test_cancellation.test_cancel_during_generation` | PASS |
| Worker cleanup | `test_thread_cleanup` | PASS |
| No leaked QThreads | `test_sequential_workers_no_accumulation` | PASS |
| Multiple sequential AI requests | `test_provider.test_multiple_sequential_requests` | PASS |
| Recovery after provider failure | `test_provider.test_recovery_after_provider_failure` | PASS |
| Generate after cancel | `test_cancellation.test_generate_after_cancel_still_works` | PASS |

## Findings

### Passed behaviors

1. **`RuntimeManager.ensure_running("ollama")`** brings the runtime to `RUNNING` and is idempotent (ownership flag stable across calls).
2. **`AIService.check_provider` / `generate(role=…)`** use the production stack (RuntimeManager → orchestrator → Ollama streaming provider).
3. **Streaming** emits progress (`Ensuring…` / `Streaming started…` / tokens) and completes with non-empty text. NDJSON chunk merge is covered by unit tests.
4. **>25k-character prompts** complete successfully with a short `max_tokens` reply.
5. **Long completions** (`max_tokens=1024`) return substantial text (≥400 chars).
6. **Cancel** works when invoked after the stream is active (`Streaming started` / first token). Cancelled runs return `success=False` with a cancel error; a follow-up generate succeeds.
7. **CreativeBriefWorker + unparented `QThread`** finishes cleanly, emits `cancelled` when cancel is requested before a failure, and does not accumulate running threads across sequential jobs. Tests pump the Qt event loop so queued `quit` slots run.
8. **Shutdown** stops only Atlas-owned runtimes; external Ollama is left alone (`started_by_atlas=False` → stop skipped).

### Notes / caveats for future AI work

1. **Cancel timing:** Cancelling during early `AIService` progress (`Ensuring AI runtime…`) is ineffective because `OllamaProvider.generate()` calls `clear_cancel()` at entry. UI cancel during an active stream is the supported path (verified by this suite).
2. **Missing-model failures** currently retry chat + generate (several attempts) before returning failure; recovery afterward still works, but failure is slower than necessary.
3. **Autostop** only applies when Atlas started Ollama in-session. If Ollama was already running externally, shutdown correctly skips it — autostop cannot be proven against a foreign instance.
4. **QThread tests** avoid `deleteLater` during unittest teardown on Windows (can abort the interpreter). Production UI may still use `deleteLater` after `finished`; hold strong refs until `finished` as documented in the AI workflow page.

## Gate

Atlas **passes** this reliability suite on the current AI execution path. Additional AI production features should not land until this suite remains green after related changes.
