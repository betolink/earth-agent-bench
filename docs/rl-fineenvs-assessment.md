# FineEnvs multi-harness RL — gap assessment (FUTURE track)

> **Status: not implemented — future / adjacent track.** This documents how far
> EAB is from the RL experiment in
> [`FineEnvs/05-multi-harness-rl`](https://github.com/adithya-s-k/FineEnvs/tree/main/05-multi-harness-rl)
> (article: <https://huggingface.co/spaces/FineEnvs/multi-harness-rl>). It is an
> assessment, not a commitment. EAB is the **environment/eval** layer; FineEnvs is
> the **RL training** layer that consumes such environments.

## What the FineEnvs example is

An **RL training recipe**, not an eval harness. A small trainable model
(LFM2.5-2.6B or Qwen3.5-2B) is trained with **GRPO** where the *tool loop is run
by a real agent harness through Harbor* (OpenCode / Claude Code / Codex /
Mini-SWE-Agent). **OpenEnv** wraps Harbor and returns the agent's own **token IDs,
behavior logprobs and loss masks** (`fetch_training_trace()`), so TRL's
`AsyncGRPOTrainer` can compute gradients on the model's calls.

- Reward: `correctness × (1 + bonus)`, `bonus = 0.1 * 15 / (15 + tool_calls)`.
  Missing grade (infra failure) → excluded, never scored as wrong.
- Three modes: `whitebox` (TRL owns bash/SETA tools, `GRPOTrainer`), `opencode`
  (native OpenCode env, deprecated), `multi_harness` (Harbor runs the four
  harnesses, `AsyncGRPOTrainer`).
- Tasks from SmolDataEnvs (04): 1,000 train / 250 test, each with a question,
  data files and a deterministic grader.
- Eval: fixed pass@1 across the four harnesses (250 × 4 pairs), reporting
  **coverage alongside pass@1**.
- Infra: Python 3.12, TRL main + OpenEnv main, 2×H100/H200 (vLLM TP1/DP2 +
  trainer), Daytona sandboxes, HF Jobs/Slurm, Trackio.

It has **two halves**:

- **A. Rollout environment** — Harbor + harnesses + tasks + grader + reward.
- **B. RL training stack** — OpenEnv + token-capturing vLLM + TRL/GRPO + GPUs.

## Gap vs EAB

| FineEnvs piece | EAB status |
|---|---|
| Harbor rollouts across 4 harnesses | ✅ `pi` / `opencode` / `codex-cli` (+ restricted `claude-code`) via Harbor 0.24 |
| Tasks + deterministic graders | 🟡 18 grounded + 10 coding tasks; **no train/test split**, far too few |
| Reward = correctness × tool-efficiency bonus | 🟡 components exist (access_pattern / efficiency / validation); no scalar RL reward fn |
| Same-tasks × harnesses eval protocol | ✅ effectively what the EAB sweep already is |
| **OpenEnv** environment server wrapping Harbor | ❌ none |
| **Token capture** (token IDs / logprobs / loss masks) | ❌ none |
| **TRL** `AsyncGRPOTrainer` / `GRPOTrainer` | ❌ none |
| **vLLM** serving a *trainable* model | ❌ we serve quantized **GGUF** via llama-swap + LiteLLM (inference-only) |
| Trainable HF checkpoint (LFM2.5-2.6B / Qwen3.5-2B) | ❌ roster is GGUF; not trainable |
| 2×H100/H200 + HF Jobs/Slurm | ❌ local single GPU |
| Daytona sandboxes | 🟡 local Docker (substitutable) |
| Trackio logging, checkpointing, multi-checkpoint eval | ❌ none |

Verified: `rg` for `openenv|trl|grpo|vllm|logprob|loss_mask|training_trace` over
`src/ scripts/ docs/` returns **nothing**.

## How far

- **Rollout/eval half (A): ~60% there.** Harbor multi-harness execution, graders,
  reward signals, resume/pause, trajectory capture, index, named runs — the exact
  substrate FineEnvs uses for rollouts.
- **RL/training half (B): ~0%.** No OpenEnv, no token capture, no TRL, no vLLM,
  no trainable weights, no training GPUs.
- **Net:** we own the *environment* side, not the *training* side. Implementing the
  RL experiment means standing up a new stack and pointing our existing harness
  rollouts at a token-capturing endpoint instead of the LiteLLM gateway.

## Blockers

1. **No trainable weights.** Everything we serve is GGUF (inference-only). Training
   needs the base HF checkpoints (FineEnvs uses **LFM2.5-2.6B** — which we already
   have as GGUF — and Qwen3.5-2B), served through vLLM, not llama-swap.
2. **No training GPUs.** 2×H100/H200 (or HF Jobs). We have local inference GPUs.
3. **The core mechanism (OpenEnv + token-capturing vLLM).** The agent's LLM calls
   must route through a capturing endpoint; the LiteLLM gateway cannot produce
   training traces.
4. **Data scale.** 1,000 train / 250 test tasks with graders vs our 28 — reuse
   SmolDataEnvs (04) or expand EAB substantially.

## Effort / path

- **Smoke (2 updates, 25 tasks × 4 harnesses):** ~1–2 weeks of integration *if
  GPUs are available*. FineEnvs provides the pieces:
  - `envs/harbor/` — a standalone Space wrapping Harbor + OpenEnv + Daytona;
  - `eval/evaluate.py` — the pass@1 protocol;
  - the reward formula, directly portable.
  Work: deploy their Harbor env server, serve a trainable model on capturing vLLM,
  install TRL main/OpenEnv main, port our reward → scalar fn, run
  `train/multi_harness.py`.
- **Full experiment (1,000 tasks, 1,000 steps, per-checkpoint multi-harness eval):**
  weeks + a large GPU budget.

## How it composes with EAB

EAB's `conditions` experiment (`baseline` / `improve` / `mcp` / `skills`) is a
**knowledge-intervention** axis; FineEnvs is a **policy-training** axis. They are
complementary, not competing:

1. keep EAB as the harness-eval protocol;
2. if/when GPUs + a trainable model are available, adopt OpenEnv + the FineEnvs
   Harbor env and reuse our tasks / graders / reward as the reward function —
   training the policy, then measuring harness transfer the way they do.

## Sources

- Repo: <https://github.com/adithya-s-k/FineEnvs/tree/main/05-multi-harness-rl>
- Article: <https://huggingface.co/spaces/FineEnvs/multi-harness-rl>
- Training script: `train/multi_harness.py`; eval: `eval/evaluate.py`; env:
  `envs/harbor/`; reproduce: `REPRODUCE.md`.
