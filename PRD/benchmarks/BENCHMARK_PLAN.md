# Benchmark Plan

## Benchmark Goal
To determine the best local LLM quantization and prompt strategy for fast, accurate incident extraction.

## Candidates
- Qwen-7B (4-bit quantization)
- Qwen-14B (4-bit quantization)
- Llama 3 8B (Fallback test)

## Required Sample Inputs
- 50 mock emergency messages ranging from clear to panicked/fragmented.

## Scoring Dimensions
- **Accuracy:** Did it extract the correct severity, location, and required skills?
- **Speed:** Time to first token (TTFT) and total inference time.
- **VRAM Usage:** Maximum memory allocation on the AMD GPU.

## Selection Rule
Choose the smallest model that achieves >95% accuracy on the mock dataset to ensure the lowest latency and highest concurrency during mass incidents.
