#!/usr/bin/env python3
"""
Simulate nano-vLLM's LLMEngine + Scheduler + BlockManager logic on a
fixed demo scenario (two prompts sharing an 8-token prefix), emitting a
trace JSON that captures the engine's state at each interesting moment.
Injects into template.html → nano_vllm_trace.html.

The simulator MIRRORS nano-vllm/nanovllm/engine/{sequence,scheduler,
block_manager}.py at /tmp/nano-vllm. It does NOT run the actual model.

v0.3:
  - Bridging steps showing `generate()`'s body (the for-loop that calls
    add_request, and the while-loop that calls step). Without these the
    trace jumps from `llm.generate(...)` straight into deep engine
    internals; the reader loses the call chain.
  - Symbolic PC names (PC dict) so line numbers are centralised and the
    file references can't silently drift.
  - Narrations explicitly thread the call chain ("called from generate's
    for-loop", "back to step()'s body before calling postprocess", …).

v0.2 features kept: storylines (chapters), pane intros (ELI5 explainers),
per-step primers, Tutorial/Standard verbosity toggle.
"""

import copy
import hashlib
import json
from collections import deque
from pathlib import Path

# ---------- Demo configuration ----------
BLOCK_SIZE = 4
NUM_BLOCKS = 16
MAX_NUM_SEQS = 4
MAX_NUM_BATCHED_TOKENS = 16

# ---------- Symbolic PC references ----------
# Keep these in sync with /tmp/nano-vllm sources; verified against the
# checked-out file. Centralising avoids the bug where a manual line
# number drifts out of sync.
PC = {
    "user_call_generate":      ("example", 24),       # outputs = llm.generate(prompts, sp)
    "generate_for_loop":       ("engine", 69),        # for prompt, sp in zip(...)
    "generate_call_add":       ("engine", 70),        # self.add_request(prompt, sp)
    "generate_while_loop":     ("engine", 73),        # while not self.is_finished():
    "generate_call_step":      ("engine", 75),        # output, num_tokens = self.step()
    "generate_return":         ("engine", 90),        # return outputs

    "add_request_body":        ("engine", 47),        # self.scheduler.add(seq)

    "step_call_schedule":      ("engine", 50),        # seqs, is_prefill = self.scheduler.schedule()
    "step_call_modelrunner":   ("engine", 52),        # token_ids = self.model_runner.call("run", ...)
    "step_call_postprocess":   ("engine", 53),        # self.scheduler.postprocess(...)

    "schedule_def":            ("scheduler", 25),     # def schedule(self)
    "schedule_can_allocate":   ("scheduler", 36),     # num_cached_blocks = self.block_manager.can_allocate(seq)
    "schedule_chunked_defer":  ("scheduler", 42),     # if remaining < num_tokens and scheduled_seqs: break
    "schedule_allocate":       ("scheduler", 45),     # self.block_manager.allocate(seq, num_cached_blocks)
    "schedule_running":        ("scheduler", 49),     # seq.status = SequenceStatus.RUNNING
    "schedule_decode":         ("scheduler", 67),     # seq.num_scheduled_tokens = 1 (decode branch)

    "postprocess_hash":        ("scheduler", 83),     # self.block_manager.hash_blocks(seq)
    "postprocess_append":      ("scheduler", 88),     # seq.append_token(token_id)
    "postprocess_finish":      ("scheduler", 90),     # seq.status = SequenceStatus.FINISHED

    "can_allocate_loop":       ("block_manager", 62), # for i in range(seq.num_blocks - 1)
    "allocate_loop":           ("block_manager", 78), # for i in range(num_cached_blocks)
    "may_append_check":        ("block_manager", 107),# if len(seq) % self.block_size == 1
}
def pc(name):
    f, ln = PC[name]
    return {"code_pane_id": f, "line": ln}


# ---------- Mirror of nano-vllm ----------

class Block:
    def __init__(self, block_id):
        self.block_id = block_id
        self.ref_count = 0
        self.hash = -1
        self.token_ids = []

    def reset(self):
        self.ref_count = 1
        self.hash = -1
        self.token_ids = []

    def update(self, h, token_ids):
        self.hash = h
        self.token_ids = list(token_ids)

    def to_state(self):
        return {
            "block_id": self.block_id,
            "ref_count": self.ref_count,
            "hash": None if self.hash == -1 else self.hash,
            "token_ids": list(self.token_ids),
        }


def compute_hash(token_ids, prefix=-1):
    """Deterministic chained hash matching nano-vllm's pattern."""
    parts = ["" if prefix == -1 else str(prefix), ",".join(map(str, token_ids))]
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


class Sequence:
    counter = 0

    def __init__(self, token_ids, max_tokens):
        self.seq_id = Sequence.counter
        Sequence.counter += 1
        self.status = "WAITING"
        self.token_ids = list(token_ids)
        self.num_prompt_tokens = len(token_ids)
        self.num_tokens = len(token_ids)
        self.num_cached_tokens = 0
        self.num_scheduled_tokens = 0
        self.is_prefill = True
        self.block_table = []
        self.max_tokens = max_tokens

    @property
    def num_blocks(self):
        return (self.num_tokens + BLOCK_SIZE - 1) // BLOCK_SIZE

    def block(self, i):
        return self.token_ids[i * BLOCK_SIZE : (i + 1) * BLOCK_SIZE]

    def append_token(self, tok):
        self.token_ids.append(tok)
        self.num_tokens += 1

    def to_state(self):
        return {
            "seq_id": self.seq_id,
            "status": self.status,
            "token_ids": list(self.token_ids),
            "num_prompt_tokens": self.num_prompt_tokens,
            "num_tokens": self.num_tokens,
            "num_cached_tokens": self.num_cached_tokens,
            "num_scheduled_tokens": self.num_scheduled_tokens,
            "block_table": list(self.block_table),
            "is_prefill": self.is_prefill,
            "max_tokens": self.max_tokens,
        }


class BlockManager:
    def __init__(self, num_blocks):
        self.blocks = [Block(i) for i in range(num_blocks)]
        self.hash_to_block_id = {}
        self.free_block_ids = deque(range(num_blocks))
        self.used_block_ids = set()

    def can_allocate(self, seq):
        h = -1
        num_cached = 0
        num_new = seq.num_blocks
        for i in range(seq.num_blocks - 1):
            tokens = seq.block(i)
            h = compute_hash(tokens, h)
            block_id = self.hash_to_block_id.get(h, -1)
            if block_id == -1 or self.blocks[block_id].token_ids != tokens:
                break
            num_cached += 1
            if block_id in self.used_block_ids:
                num_new -= 1
        if len(self.free_block_ids) < num_new:
            return -1
        return num_cached

    def allocate(self, seq, num_cached):
        assert not seq.block_table
        h = -1
        for i in range(num_cached):
            tokens = seq.block(i)
            h = compute_hash(tokens, h)
            block_id = self.hash_to_block_id[h]
            blk = self.blocks[block_id]
            if block_id in self.used_block_ids:
                blk.ref_count += 1
            else:
                blk.ref_count = 1
                self.free_block_ids.remove(block_id)
                self.used_block_ids.add(block_id)
            seq.block_table.append(block_id)
        for _ in range(num_cached, seq.num_blocks):
            seq.block_table.append(self._allocate_fresh())
        seq.num_cached_tokens = num_cached * BLOCK_SIZE

    def _allocate_fresh(self):
        block_id = self.free_block_ids.popleft()
        blk = self.blocks[block_id]
        assert blk.ref_count == 0
        if blk.hash != -1 and self.hash_to_block_id.get(blk.hash) == block_id:
            del self.hash_to_block_id[blk.hash]
        blk.reset()
        self.used_block_ids.add(block_id)
        return block_id

    def deallocate(self, seq):
        for block_id in reversed(seq.block_table):
            blk = self.blocks[block_id]
            blk.ref_count -= 1
            if blk.ref_count == 0:
                self.used_block_ids.remove(block_id)
                self.free_block_ids.append(block_id)
        seq.num_cached_tokens = 0
        seq.block_table = []

    def may_append(self, seq):
        if seq.num_tokens % BLOCK_SIZE == 1:
            seq.block_table.append(self._allocate_fresh())

    def hash_blocks(self, seq):
        start = seq.num_cached_tokens // BLOCK_SIZE
        end = (seq.num_cached_tokens + seq.num_scheduled_tokens) // BLOCK_SIZE
        if start == end:
            return
        h = self.blocks[seq.block_table[start - 1]].hash if start > 0 else -1
        for i in range(start, end):
            blk = self.blocks[seq.block_table[i]]
            tokens = seq.block(i)
            h = compute_hash(tokens, h)
            blk.update(h, tokens)
            self.hash_to_block_id[h] = blk.block_id

    def to_state(self):
        return {
            "blocks": [b.to_state() for b in self.blocks],
            "free": list(self.free_block_ids),
            "used": sorted(self.used_block_ids),
        }

    def prefix_cache_state(self):
        return [
            {"hash": h, "block_id": bid, "preview": list(self.blocks[bid].token_ids)}
            for h, bid in self.hash_to_block_id.items()
        ]


# ---------- Trace recorder ----------

class Trace:
    def __init__(self):
        self.steps = []
        self.sequences_map = {}
        self.waiting_q = []
        self.running_q = []
        self.bm = BlockManager(NUM_BLOCKS)
        self.storylines = []
        self._cur_st = None

    def storyline(self, st_id, title, summary):
        st = {"id": st_id, "title": title, "summary": summary, "step_ids": []}
        self.storylines.append(st)
        self._cur_st = st

    def snapshot(self):
        return {
            "sequences": [s.to_state() for s in sorted(self.sequences_map.values(), key=lambda x: x.seq_id)],
            "block_pool": self.bm.to_state(),
            "scheduler": {"waiting": list(self.waiting_q), "running": list(self.running_q)},
            "prefix_cache": self.bm.prefix_cache_state(),
        }

    def add(self, title, pc_dict, narration, *, primer=None, highlights=None):
        sid = f"S{len(self.steps) + 1}"
        step = {
            "id": sid,
            "title": title,
            "pc": pc_dict,
            "narration": narration,
            "highlights": highlights or [],
            "state": copy.deepcopy(self.snapshot()),
            "storyline_id": self._cur_st["id"] if self._cur_st else None,
        }
        if primer:
            step["primer"] = primer
        self.steps.append(step)
        if self._cur_st:
            self._cur_st["step_ids"].append(sid)


# ---------- Scenario ----------

def build_trace() -> dict:
    tr = Trace()
    SHARED = [101, 102, 103, 104, 105, 106, 107, 108]
    prompt_a = SHARED + [201, 202, 203, 204]   # 12 tokens, 3 blocks
    prompt_b = SHARED + [301, 302, 303, 304]   # 12 tokens, 3 blocks
    SAMPLED = {
        (0, "prefill"):  401, (0, "decode1"):  402,
        (1, "prefill"):  501, (1, "decode1"):  502,
    }

    # ============================================
    # ST1 — Request arrives
    # ============================================
    tr.storyline(
        "ST1", "1. Request arrives",
        "Two prompts enter the engine via add_request and queue up. The KV cache is untouched until the scheduler admits them."
    )

    tr.add(
        title="User code: llm.generate(prompts, sampling_params)",
        pc_dict=pc("user_call_generate"),
        narration=(
            "`example.py:main()` builds two prompts and a `SamplingParams(temperature=0.6, max_tokens=2)`, "
            "then calls `llm.generate(prompts, sp)`. Engine starts idle: 0 sequences, all 16 KV blocks free. "
            "**Demo config note:** `block_size=4` and `max_num_batched_tokens=16` are made small for visualisation "
            "(nano-vLLM defaults are 256 and much larger); the small batch budget forces the two prompts into "
            "separate prefill steps, which is what surfaces the prefix-cache hit later."
        ),
        primer=(
            "**What is vLLM?** An LLM inference server: you send a prompt and get a completion. "
            "The challenge is that the keys/values each token attends to (the KV cache) grow linearly with sequence "
            "length, and naively giving each request a contiguous KV region either over-allocates or stalls under load. "
            "**vLLM's idea (PagedAttention):** chop the KV cache into fixed-size *physical blocks*, like virtual memory "
            "pages. Each sequence holds a `block_table` mapping its logical blocks → physical block IDs, and the "
            "attention kernel gathers K/V via that mapping. **Bonus:** two sequences with a shared prompt prefix can "
            "literally point at the same physical blocks — that's prefix caching."
        ),
        highlights=[],
    )

    tr.add(
        title="Inside generate() — enqueue prompts via add_request",
        pc_dict=pc("generate_for_loop"),
        narration=(
            "We step INTO `generate()`. Its body has two parts. First: a `for prompt, sp in zip(prompts, sampling_params): "
            "self.add_request(prompt, sp)` loop that pushes every prompt onto the scheduler's `waiting` queue. "
            "Second: a `while not self.is_finished(): self.step()` loop that pumps the engine until done. "
            "Right now we're on the for-loop; let's step into the first `add_request` call."
        ),
        primer=(
            "**Reading roadmap.** `generate()` is a thin wrapper, not where the work happens. The interesting "
            "state changes — block allocation, prefix-cache hits, sampling — all live inside `step()`. "
            "What `generate()` provides is the **framing**: enqueue every prompt up front, then loop "
            "`step() → step() → step() …` until both queues are empty. Each `step()` is one scheduler decision plus "
            "one forward pass."
        ),
        highlights=[],
    )

    seq_a = Sequence(prompt_a, max_tokens=2)
    tr.sequences_map[seq_a.seq_id] = seq_a
    tr.waiting_q.append(seq_a.seq_id)
    tr.add(
        title="add_request(promptA) — seq 0 created, queued",
        pc_dict=pc("add_request_body"),
        narration=(
            "Inside `add_request` (called by `generate()` for promptA). Tokenises the string (here: 12 token ids), "
            "constructs a `Sequence` object (`status=WAITING`), and calls `scheduler.add(seq)` which just "
            "`waiting.append(seq)` — a plain deque push. No GPU memory touched yet; the KV cache doesn't see "
            "this sequence until the scheduler admits it on a future `step()`."
        ),
        primer=(
            "**Sequence — the engine's view of one request.** Fields that matter: `token_ids` (prompt + completion-so-far), "
            "`status` (WAITING → RUNNING → FINISHED), `num_cached_tokens` (tokens whose KV is already stored in blocks), "
            "`num_scheduled_tokens` (tokens THIS step's forward pass will compute KV for), and `block_table` (the list "
            "of physical block IDs holding this seq's KV — empty until the scheduler runs)."
        ),
        highlights=["sequences", "scheduler"],
    )

    seq_b = Sequence(prompt_b, max_tokens=2)
    tr.sequences_map[seq_b.seq_id] = seq_b
    tr.waiting_q.append(seq_b.seq_id)
    tr.add(
        title="add_request(promptB) — seq 1 created, queued",
        pc_dict=pc("add_request_body"),
        narration=(
            "Second iteration of `generate()`'s for-loop, this time for promptB. Same path: tokenise, build Sequence, "
            "push to `waiting`. The two prompts share their first 8 tokens (`[101..108]`) — exactly 2 blocks — "
            "but the scheduler doesn't notice prefix sharing yet; both just sit in WAITING as plain rows on the queue."
        ),
        highlights=["sequences", "scheduler"],
    )

    tr.add(
        title="Back in generate() — enter the engine pump (while not is_finished)",
        pc_dict=pc("generate_while_loop"),
        narration=(
            "The for-loop exits. Both sequences are queued. `generate()` now enters its main pump: "
            "`while not self.is_finished(): output, num_tokens = self.step()`. Every iteration runs `step()` once. "
            "We exit when `is_finished()` returns True — i.e. both `waiting` and `running` queues are empty. "
            "Let's step into the first `step()` call."
        ),
        primer=(
            "**engine.step() is the heartbeat.** Each call does **exactly one** scheduler decision and **exactly one** "
            "forward pass through the model. It's pure synchronous orchestration; the GPU work happens inside "
            "`ModelRunner.call(\"run\", …)` on line 52. The scheduler picks between two phases: *prefill* (admit a new "
            "prompt, do its first big forward pass) or *decode* (advance each running seq by one token)."
        ),
        highlights=["scheduler"],
    )

    # ============================================
    # ST2 — First prefill: cold cache
    # ============================================
    tr.storyline(
        "ST2", "2. First prefill — cold cache",
        "Scheduler admits seq 0, the block manager allocates 3 fresh blocks for the prompt, the model runs a prefill forward pass, and the resulting full blocks are hashed into the prefix cache."
    )

    tr.add(
        title="step() #1 — first line: scheduler.schedule()",
        pc_dict=pc("step_call_schedule"),
        narration=(
            "We're inside `step()`. First line: `seqs, is_prefill = self.scheduler.schedule()` — ask the scheduler "
            "which sequences will run this tick. Step into `schedule()`."
        ),
        highlights=["scheduler"],
    )

    tr.add(
        title="Inside scheduler.schedule() — try prefill on head of waiting",
        pc_dict=pc("schedule_can_allocate"),
        narration=(
            "`schedule()` runs in two passes: **prefill** first (drain `waiting` while there's batch budget), then "
            "**decode** only if no seq was admitted for prefill. Budget = `max_num_batched_tokens=16` tokens of "
            "forward-pass work. Head of waiting is seq 0. We're about to call `block_manager.can_allocate(seq)` to "
            "see how many of seq 0's blocks can be reused from the prefix cache."
        ),
        primer=(
            "**Logical vs physical blocks.** A sequence sees its tokens grouped into *logical blocks* of `block_size` "
            "tokens — logical block 0 holds tokens 0..3, block 1 holds 4..7, etc. Each logical block is backed by some "
            "*physical block* in the pool, looked up via `block_table[logical_idx] = physical_id`. The scheduler "
            "decides WHICH physical blocks to give to this seq before running the forward pass."
        ),
        highlights=["scheduler", "prefix_cache"],
    )

    tr.add(
        title="can_allocate(seq 0) — walk prefix, miss on block 0 → num_cached=0",
        pc_dict=pc("can_allocate_loop"),
        narration=(
            "Step into `can_allocate`. It loops `for i in range(seq.num_blocks - 1)`: i=0, take `seq.block(0) = [101..104]`, "
            "compute its chained hash, look it up in `hash_to_block_id` — MISS (prefix cache is still empty; this is "
            "the very first sequence). Break immediately. `num_cached_blocks = 0`, `num_new_blocks = 3`. "
            "`len(free_block_ids) = 16 ≥ 3` → return `0`. Control returns to `schedule()`."
        ),
        highlights=["prefix_cache", "block_pool"],
    )

    n = tr.bm.can_allocate(seq_a)
    assert n == 0
    tr.bm.allocate(seq_a, n)
    tr.add(
        title="block_manager.allocate(seq 0, num_cached=0) — pop 3 fresh blocks",
        pc_dict=pc("allocate_loop"),
        narration=(
            "Back in `schedule()`, next call: `block_manager.allocate(seq, 0)`. No cached blocks → skip the cache-reuse "
            "loop, just pop 3 fresh blocks from `free_block_ids`. **`seq0.block_table = [0, 1, 2]`**. "
            "This list IS PagedAttention's mapping: when the CUDA kernel attends for token `i` of seq 0, it looks up "
            "logical block `i // 4`, fetches `block_table[…]`, then reads KV slot `i % 4` inside that physical block."
        ),
        primer=(
            "**The core of PagedAttention.** Instead of one big contiguous KV region per sequence (forces over-allocation), "
            "vLLM gives each seq a `block_table`: a list of physical block IDs. Logical block i lives at "
            "`block_table[i]`. Two sequences can point at the SAME physical block — that's how prefix sharing works "
            "without copying any K/V data. The CUDA attention kernel reads the block_table to gather slots from "
            "non-contiguous memory."
        ),
        highlights=["sequences", "block_pool"],
    )

    seq_a.num_scheduled_tokens = 12
    seq_a.status = "RUNNING"
    tr.waiting_q.remove(seq_a.seq_id)
    tr.running_q.append(seq_a.seq_id)
    tr.add(
        title="seq 0 fully scheduled (12 tokens) → status RUNNING",
        pc_dict=pc("schedule_running"),
        narration=(
            "Back in `schedule()` after `allocate` returns. `seq.num_scheduled_tokens = 12` (the whole prompt). "
            "`num_batched_tokens` goes 0 → 12, still under the 16-token budget. All prompt tokens scheduled, so "
            "`seq.status = RUNNING`, `self.waiting.popleft()`, `self.running.append(seq)`. Loop iteration done."
        ),
        highlights=["sequences", "scheduler"],
    )

    tr.add(
        title="Try seq 1: budget remaining=4 < 12 → chunked-prefill defer",
        pc_dict=pc("schedule_chunked_defer"),
        narration=(
            "Next iteration of `schedule()`'s prefill loop: head of waiting is seq 1. Budget left: `16 − 12 = 4`; "
            "seq 1 needs 12. The rule `if remaining < num_tokens and scheduled_seqs: break` says only the FIRST seq "
            "in a batch may be chunked; seq 0 already took that slot. Break — seq 1 waits for the next step()."
        ),
        highlights=["scheduler"],
    )

    tr.add(
        title="schedule() returns ([seq 0], is_prefill=True) — back in step()",
        pc_dict=pc("step_call_modelrunner"),
        narration=(
            "`schedule()` exits its prefill loop and returns. Control back in `step()` body, next line is "
            "`token_ids = self.model_runner.call(\"run\", seqs, is_prefill)`. The model runner gathers seq 0's KV "
            "slots via its `block_table`, runs a forward pass over all 12 prompt tokens (prefill), and samples the "
            "first decode token. **Sampled: 401** (stubbed here — real nano-vLLM uses the sampling kernel)."
        ),
        highlights=[],
    )

    tr.bm.hash_blocks(seq_a)
    seq_a.num_cached_tokens += seq_a.num_scheduled_tokens
    seq_a.num_scheduled_tokens = 0
    seq_a.append_token(SAMPLED[(0, "prefill")])
    tr.add(
        title="step() calls scheduler.postprocess — hash_blocks + append token",
        pc_dict=pc("postprocess_hash"),
        narration=(
            "Next line of `step()`: `self.scheduler.postprocess(seqs, token_ids, is_prefill)`. Step into postprocess. "
            "First line of its loop body: `self.block_manager.hash_blocks(seq)`. With prefill done, every FULL block "
            "gets hashed and indexed in `hash_to_block_id`. Hashes chain: `h0 = hash([101..104], -1)`, "
            "`h1 = hash([105..108], h0)`, `h2 = hash([201..204], h1)`. Then `seq.append_token(401)` adds the sampled "
            "token; the 13th token will spill out of the current block on the next decode (12 = 3 × block_size)."
        ),
        primer=(
            "**The prefix cache lives in `hash_to_block_id`.** Each filled block's content is hashed and the mapping "
            "`hash → block_id` is recorded. Hashes CHAIN: block i's hash depends on (a) its tokens and (b) block "
            "i-1's hash. So a hash hit on block N tells you the entire prefix of N+1 blocks matches what's already in "
            "some physical block — just point at it instead of recomputing."
        ),
        highlights=["block_pool", "prefix_cache", "sequences"],
    )

    # ============================================
    # ST3 — Second prefill: prefix-cache hit
    # ============================================
    tr.storyline(
        "ST3", "3. Second prefill — prefix-cache hit",
        "step()'s next iteration of the while loop. The block manager finds 2 of seq 1's blocks already in the prefix cache → only 1 new block is allocated; the prefill forward pass shrinks from 12 tokens to 4."
    )

    tr.add(
        title="step() returns; generate()'s while loop runs another iteration → step() #2",
        pc_dict=pc("generate_call_step"),
        narration=(
            "Back in `generate()`. `step()` #1 returned. `is_finished()` is False (seq 0 still running, seq 1 still "
            "waiting), so the `while` loop calls `self.step()` again. Step into the second step() call. Prefill phase "
            "first — walk `waiting` again. Only seq 1 is there. **This time the prefix cache is populated.**"
        ),
        highlights=["scheduler"],
    )

    tr.add(
        title="can_allocate(seq 1) — chained hash matches blocks 0,1!",
        pc_dict=pc("can_allocate_loop"),
        narration=(
            "Walk seq 1's blocks: i=0, `block(0) = [101..104]`, chained hash matches → **cache hit on block 0**, "
            "`num_cached_blocks=1`. i=1, `block(1) = [105..108]`, chained hash matches → **cache hit on block 1**, "
            "`num_cached_blocks=2`. Loop range is `range(seq.num_blocks - 1) = range(2)`, so it stops here (never "
            "checks the last block, which would prevent the running seq from racing the allocator). "
            "`num_new_blocks` decremented twice because both cached blocks are currently in `used_block_ids` "
            "(still held by seq 0) → only 1 new block to allocate. Return `2`."
        ),
        primer=(
            "**Why prefix sharing matters in production:** the same prefix appears in many real workloads — "
            "system prompts shared across users (\"You are a helpful assistant…\"), few-shot examples shared across "
            "queries, conversation history shared across follow-ups. With a populated prefix cache, the second-and-later "
            "sequences only need forward passes for the *divergent suffix*. Savings scale linearly with how long the "
            "shared prefix is — for a long system prompt, that's huge."
        ),
        highlights=["prefix_cache", "block_pool"],
    )

    n = tr.bm.can_allocate(seq_b)
    assert n == 2
    tr.bm.allocate(seq_b, n)
    tr.add(
        title="allocate(seq 1, num_cached=2) — share blocks 0,1; fresh block 3",
        pc_dict=pc("allocate_loop"),
        narration=(
            "The cache-reuse half of `allocate` runs: for each of the 2 cached blocks, since `block_id ∈ used_block_ids`, "
            "just bump `ref_count` (block 0: 1 → 2, block 1: 1 → 2). For the 3rd block (the divergent suffix "
            "`[301..304]`): pop a fresh block 3 from `free_block_ids`. **`seq1.block_table = [0, 1, 3]`. "
            "`seq1.num_cached_tokens = 8`** — those 8 tokens already have their KV stored in blocks 0,1."
        ),
        highlights=["block_pool", "sequences"],
    )

    seq_b.num_scheduled_tokens = seq_b.num_tokens - seq_b.num_cached_tokens
    seq_b.status = "RUNNING"
    tr.waiting_q.remove(seq_b.seq_id)
    tr.running_q.append(seq_b.seq_id)
    tr.add(
        title="seq 1 scheduled — only 4 uncached tokens this prefill",
        pc_dict=pc("schedule_running"),
        narration=(
            "Back in `schedule()` body: `seq.num_scheduled_tokens = min(num_tokens, remaining) = min(4, 16) = 4`. "
            "Only 4 tokens need the forward pass; the cached 8 already have K and V in blocks 0,1. "
            "`seq.status = RUNNING`, move from waiting to running."
        ),
        highlights=["sequences", "scheduler"],
    )

    tr.add(
        title="ModelRunner.run([seq 1], prefill=True) — chunked prefill on 4 tokens",
        pc_dict=pc("step_call_modelrunner"),
        narration=(
            "Back in `step()` body. Forward pass with only 4 new tokens, but the attention queries can read the "
            "cached KV in blocks 0,1 via seq 1's `block_table = [0,1,3]`. **The big win of prefix caching:** "
            "4 token-forwards instead of 12. **Sampled: 501.**"
        ),
        highlights=[],
    )

    tr.bm.hash_blocks(seq_b)
    seq_b.num_cached_tokens += seq_b.num_scheduled_tokens
    seq_b.num_scheduled_tokens = 0
    seq_b.append_token(SAMPLED[(1, "prefill")])
    tr.add(
        title="postprocess(seq 1) — hash block 3, append 501",
        pc_dict=pc("postprocess_hash"),
        narration=(
            "`step()` calls `postprocess` again. Block 3 (= `[301..304]`) is now full → hash it (chained from block 1's "
            "hash) and add to the prefix cache. Future sequences starting `[101..108, 301..304]` will reuse all 3 blocks. "
            "Append 501 to seq 1."
        ),
        highlights=["block_pool", "prefix_cache", "sequences"],
    )

    # ============================================
    # ST4 — Decode: continuous batching
    # ============================================
    tr.storyline(
        "ST4", "4. Decode — continuous batching",
        "step() #3. Waiting is empty so the scheduler goes to its decode pass. Both running sequences advance by one token in a single fused forward pass."
    )

    tr.add(
        title="step() #3 — schedule()'s decode pass",
        pc_dict=pc("schedule_decode"),
        narration=(
            "Back in `generate()`, third iteration of the while loop, so a third `step()` call. Inside `schedule()`, "
            "the prefill while-loop runs zero iterations (waiting is empty); fall through to the **decode** loop. "
            "Pop each running seq, ensure room for one more token via `may_append`, then forward-pass them all "
            "together in one fused kernel call."
        ),
        primer=(
            "**Decode = per-token loop.** Once a sequence has been prefilled, each subsequent forward pass generates "
            "ONE new token. The trick is that the scheduler batches the decode passes of ALL currently-running "
            "sequences into ONE fused kernel call. Sequence A and Sequence B may be at different lengths and have "
            "different attention queries, but they share the forward pass — that's **continuous batching**. "
            "The kernel handles per-seq differences via the `block_table` lookups."
        ),
        highlights=["scheduler"],
    )

    tr.bm.may_append(seq_a)
    seq_a.num_scheduled_tokens = 1
    seq_a.is_prefill = False
    tr.add(
        title="may_append(seq 0) — len=13, allocate block 4",
        pc_dict=pc("may_append_check"),
        narration=(
            "`schedule()`'s decode loop calls `block_manager.may_append(seq)`. `len(seq 0) = 13` (12 prompt + 1 sampled). "
            "`13 mod block_size = 1` → the new token lands in a fresh logical block. Pop physical block 4 from "
            "free_block_ids. `seq0.block_table = [0, 1, 2, 4]`. Flip `is_prefill = False` — seq 0 is in decode mode now."
        ),
        highlights=["sequences", "block_pool"],
    )

    tr.bm.may_append(seq_b)
    seq_b.num_scheduled_tokens = 1
    seq_b.is_prefill = False
    tr.add(
        title="may_append(seq 1) — len=13, allocate block 5",
        pc_dict=pc("may_append_check"),
        narration=(
            "Same logic for seq 1: allocate fresh block 5. `seq1.block_table = [0, 1, 3, 5]`. "
            "Blocks 0 and 1 are still shared between seq 0 and seq 1 (`ref_count = 2`); blocks 2, 3, 4, 5 each have "
            "`ref_count = 1`."
        ),
        highlights=["sequences", "block_pool"],
    )

    tr.add(
        title="ModelRunner.run([seq 0, seq 1], prefill=False) — batched decode",
        pc_dict=pc("step_call_modelrunner"),
        narration=(
            "Back in `step()`. **Continuous batching in action:** one forward pass produces one new token per running "
            "sequence. Each seq still attends to its OWN history via its OWN `block_table`, but the compute is fused "
            "into a single GPU kernel call. **Sampled: seq 0 → 402, seq 1 → 502.**"
        ),
        highlights=[],
    )

    # ============================================
    # ST5 — Teardown: refs unwind
    # ============================================
    tr.storyline(
        "ST5", "5. Teardown — refs unwind",
        "Both sequences hit max_tokens=2 in postprocess and finish. deallocate walks block_tables in reverse, decrementing ref_counts. Shared blocks survive one decref; the second frees them. Hash entries stay in the prefix cache for future hits. generate() returns."
    )

    for seq, tok in [(seq_a, SAMPLED[(0, "decode1")]), (seq_b, SAMPLED[(1, "decode1")])]:
        seq.num_cached_tokens += seq.num_scheduled_tokens
        seq.num_scheduled_tokens = 0
        seq.append_token(tok)
        seq.status = "FINISHED"
        tr.bm.deallocate(seq)
        tr.running_q.remove(seq.seq_id)

    tr.add(
        title="postprocess — both reach max_tokens → FINISHED, deallocate",
        pc_dict=pc("postprocess_finish"),
        narration=(
            "Back in `postprocess`'s loop. Each seq appends its decode token (402 / 502). "
            "`num_completion_tokens = 2 == max_tokens` → `seq.status = FINISHED`, `block_manager.deallocate(seq)`, "
            "`self.running.remove(seq)`. **`deallocate` walks `block_table` in reverse, decrementing `ref_count`.** "
            "Block 0 was shared (ref=2) — goes to 1 when seq 0's dealloc fires (seq 1 still uses it), then to 0 when "
            "seq 1's dealloc fires, then it's pushed onto `free_block_ids`. **Crucially: hash entries in the prefix "
            "cache STAY** — the blocks go free but their hashes still point at them, so the next sequence with a "
            "matching prefix gets a cache hit without recomputation."
        ),
        primer=(
            "**Reference counting: how shared blocks are freed safely.** Each physical block has a `ref_count` — the "
            "number of sequences currently using it. `allocate` increments, `deallocate` decrements. A block returns "
            "to the free pool ONLY when ref_count hits 0. So a shared block survives the first sequence finishing if "
            "another still references it. Even after a block is freed, its content (the cached KV) and its hash "
            "mapping are still readable until something else claims and resets it — that's why prefix cache hits can "
            "still revive it for free."
        ),
        highlights=["sequences", "block_pool", "prefix_cache"],
    )

    tr.add(
        title="Back in generate() — is_finished() True → loop exits → return",
        pc_dict=pc("generate_return"),
        narration=(
            "`step()` returns. Back in `generate()`'s while loop. `is_finished()` now returns True (both queues empty). "
            "Loop exits. The tail of `generate()`: collect each seq's completion `token_ids`, run them through "
            "`tokenizer.decode`, and return a list of `{text, token_ids}` dicts. Done — the user's "
            "`llm.generate(prompts, sp)` call finally returns."
        ),
        highlights=[],
    )

    # ---------- Pane intros (ELI5 + structural detail) ----------
    pane_intros = {
        "sequences": {
            "title": "Sequences",
            "body": (
                "**Each in-flight request becomes one `Sequence`.** It carries:\n"
                "• `token_ids` — prompt followed by completion-so-far (the completion grows one token per decode step).\n"
                "• `status` — `WAITING` (just arrived), `RUNNING` (admitted by scheduler), or `FINISHED` (EOS or max_tokens hit).\n"
                "• `num_cached_tokens` — how many tokens at the start have their KV already stored in physical blocks.\n"
                "• `num_scheduled_tokens` — how many tokens *this step's* forward pass will compute KV for.\n"
                "• `block_table` — the heart of PagedAttention. A list of physical block IDs; logical block `i` lives at "
                "`block_table[i]`. The attention kernel reads block_table at every forward pass to find each token's KV slot."
            ),
            "structure": {
                "source": "nanovllm/engine/sequence.py",
                "class_def": (
                    "class Sequence:\n"
                    "    block_size = 256          # class attr — same for every seq\n"
                    "    counter = count()         # auto-increments seq_id globally\n"
                    "\n"
                    "    def __init__(self, token_ids, sampling_params):\n"
                    "        self.seq_id              = next(Sequence.counter)\n"
                    "        self.status              = SequenceStatus.WAITING\n"
                    "        self.token_ids           = copy(token_ids)\n"
                    "        self.last_token          = token_ids[-1]\n"
                    "        self.num_tokens          = len(self.token_ids)\n"
                    "        self.num_prompt_tokens   = len(token_ids)\n"
                    "        self.num_cached_tokens   = 0\n"
                    "        self.num_scheduled_tokens= 0\n"
                    "        self.is_prefill          = True\n"
                    "        self.block_table         = []\n"
                    "        self.temperature, self.max_tokens, self.ignore_eos = (\n"
                    "            sampling_params.temperature,\n"
                    "            sampling_params.max_tokens,\n"
                    "            sampling_params.ignore_eos,\n"
                    "        )"
                ),
                "fields": [
                    {"name": "seq_id", "type": "int",
                     "role": "Globally unique, auto-incremented identifier",
                     "example": "0, 1, 2…",
                     "why": "Used as a key in `Scheduler.waiting/running`, outputs dict, and live-mode followups."},
                    {"name": "status", "type": "SequenceStatus",
                     "role": "Lifecycle flag",
                     "example": "WAITING → RUNNING → FINISHED",
                     "why": "Drives which queue a seq lives in; postprocess sets FINISHED when EOS or max_tokens hit."},
                    {"name": "token_ids", "type": "list[int]",
                     "role": "Prompt tokens followed by completion tokens; grows during decode",
                     "example": "[101, 102, …, 401, 402]"},
                    {"name": "num_prompt_tokens", "type": "int",
                     "role": "Fixed at construction; `token_ids[:num_prompt_tokens]` is always the prompt slice"},
                    {"name": "num_cached_tokens", "type": "int",
                     "role": "Tokens (counted from start) whose KV already lives in physical blocks",
                     "example": "0 → 8 (on prefix cache hit) → 12 → 13 → 14",
                     "why": "The high-water mark of computed KV. Lets prefix-cache hits skip recomputation; lets chunked prefill resume."},
                    {"name": "num_scheduled_tokens", "type": "int",
                     "role": "How many tokens THIS step's forward pass will compute KV for",
                     "example": "12 (full prompt prefill) → 4 (chunked) → 1 (decode)",
                     "why": "Set by `Scheduler.schedule()` each tick; zeroed in postprocess."},
                    {"name": "is_prefill", "type": "bool",
                     "role": "True before first decode token, False after",
                     "why": "Used by `postprocess` to decide whether to skip `append_token` (chunked prefill not yet done)."},
                    {"name": "block_table", "type": "list[int]",
                     "role": "Logical → physical block mapping. Logical block `i` lives at `block_table[i]`",
                     "example": "[] → [0, 1, 2] → [0, 1, 2, 4] (decode appended block 4)",
                     "why": "The heart of PagedAttention. The CUDA attention kernel uses this every forward pass."},
                ],
                "relationships": [
                    {"to": "block_pool",   "via": "block_table[i]",       "kind": "Each entry is a `block_id` indexing `BlockManager.blocks`. Two seqs can share the same id (prefix cache)."},
                    {"to": "scheduler",    "via": "status + queue membership", "kind": "`WAITING ⇔ in scheduler.waiting`; `RUNNING ⇔ in scheduler.running`."},
                    {"to": "prefix_cache", "via": "block_table → block.hash", "kind": "When a block fills, its hash is added to `hash_to_block_id` — that's how future seqs find it."},
                ],
                "invariants": [
                    "`len(token_ids) == num_tokens`",
                    "`len(block_table) == ceil(num_tokens / block_size)` while RUNNING",
                    "`num_cached_tokens + num_scheduled_tokens ≤ num_tokens`",
                    "`status == WAITING ⇒ block_table == []`",
                    "`status == FINISHED ⇒ block_table == []` (post-deallocate)",
                ],
                "design_notes": (
                    "**Why a separate `num_cached_tokens` field?** It decouples *what's already computed* from "
                    "*how big the sequence is* — that's exactly what prefix-cache hits need (8 of 12 tokens already "
                    "have KV, only compute the last 4). It also enables chunked prefill: split a huge prompt across "
                    "multiple steps without losing track of progress.\n\n"
                    "**Why a class-level `counter`?** Sequence IDs are globally unique across all sequences ever "
                    "created in the process — never recycled. Live-mode follow-up storage and output dicts can use "
                    "`seq_id` as a stable key."
                ),
            },
        },
        "block_pool": {
            "title": "KV cache block pool",
            "body": (
                "**The pool is all GPU memory available for storing attention K/V**, sliced into fixed-size *physical blocks*. "
                "Here we use 16 blocks of `block_size=4` tokens each (real nano-vLLM defaults to 256).\n\n"
                "Each cell shows:\n"
                "• `#N` — the physical block id (never changes; this is its slot in GPU memory).\n"
                "• `rK` — current `ref_count`. How many sequences point at this block right now.\n"
                "• A peek of the token ids it holds (once filled).\n\n"
                "Colours: **pale** = free, **blue** = used by one seq, **purple** = shared (ref ≥ 2), **dashed** = "
                "cached-but-free (hash still in the prefix cache so it can be reclaimed by a matching prefix)."
            ),
            "structure": {
                "source": "nanovllm/engine/block_manager.py",
                "class_def": (
                    "class Block:\n"
                    "    def __init__(self, block_id):\n"
                    "        self.block_id   = block_id   # slot index, never changes\n"
                    "        self.ref_count  = 0          # how many seqs point here\n"
                    "        self.hash       = -1         # chained hash; -1 = unset\n"
                    "        self.token_ids  = []         # block_size tokens once filled\n"
                    "\n"
                    "class BlockManager:\n"
                    "    def __init__(self, num_blocks, block_size):\n"
                    "        self.block_size       = block_size\n"
                    "        self.blocks           = [Block(i) for i in range(num_blocks)]\n"
                    "        self.hash_to_block_id = {}                          # prefix cache\n"
                    "        self.free_block_ids   = deque(range(num_blocks))    # FIFO\n"
                    "        self.used_block_ids   = set()"
                ),
                "fields": [
                    {"name": "blocks", "type": "list[Block]",
                     "role": "Fixed-size array, index = physical block id",
                     "example": "16 Block(0)..Block(15)",
                     "why": "Block IDs are stable slot indices — `Sequence.block_table` references them by id, not by Python identity."},
                    {"name": "Block.block_id", "type": "int",
                     "role": "Slot index in `blocks[]`; identity",
                     "example": "0..15"},
                    {"name": "Block.ref_count", "type": "int",
                     "role": "How many `Sequence.block_table` entries currently point at this block",
                     "example": "0 (free) → 1 (one owner) → 2 (shared via prefix cache) → 0 (freed)",
                     "why": "Sharing means multiple decrements before a block can be freed."},
                    {"name": "Block.hash", "type": "int (xxhash) or -1",
                     "role": "Chained hash of this block's content; -1 means not hashed yet",
                     "example": "-1 → 0xabc123 (after postprocess hashes it)"},
                    {"name": "Block.token_ids", "type": "list[int]",
                     "role": "The `block_size` token ids this block holds (cached after `hash_blocks`)",
                     "why": "Stored so `can_allocate` can do a safety check `blocks[id].token_ids == seq_tokens` after a hash hit — defends against hash collisions."},
                    {"name": "hash_to_block_id", "type": "dict[int, int]",
                     "role": "Prefix cache. Maps chained-hash → block_id",
                     "example": "{0xabc…: 0, 0xdef…: 1, 0xfaa…: 2}",
                     "why": "Dict gives O(1) prefix-cache lookup."},
                    {"name": "free_block_ids", "type": "deque[int]",
                     "role": "FIFO of unused block ids",
                     "example": "deque([5, 6, 7, …, 15])",
                     "why": "FIFO not LIFO: freshly-freed blocks are NOT immediately re-claimed; they sit at the tail of the queue, giving the prefix cache a chance to revive them."},
                    {"name": "used_block_ids", "type": "set[int]",
                     "role": "Currently-referenced block ids",
                     "why": "`set` gives O(1) `block_id in used_block_ids` check (used in `can_allocate` to decide whether a cached block needs to come from free_block_ids or just refcount-bump)."},
                ],
                "relationships": [
                    {"to": "sequences",    "via": "Block.ref_count", "kind": "Σ(block.ref_count over all blocks) = Σ(len(seq.block_table) over all sequences)."},
                    {"to": "prefix_cache", "via": "hash_to_block_id", "kind": "The prefix-cache pane visualises this very dict. Block.hash is what gets indexed."},
                    {"to": "scheduler",    "via": "BlockManager owned by Scheduler", "kind": "Only the scheduler calls `allocate / deallocate / may_append / hash_blocks`."},
                ],
                "invariants": [
                    "`len(blocks) == num_blocks` (fixed at construction)",
                    "`len(free_block_ids) + len(used_block_ids) == num_blocks`",
                    "`free_block_ids ∩ used_block_ids == ∅`",
                    "`blocks[id].ref_count == 0  ⟺  id ∈ free_block_ids`",
                    "Every `block_id` in any seq's `block_table` is in `used_block_ids`",
                    "Σ(block.ref_count) == Σ(len(seq.block_table))",
                ],
                "design_notes": (
                    "**Why split into `blocks[]` + two id-collections instead of just one list?** "
                    "Different operations want different access patterns: `allocate` wants a quick free pool "
                    "(deque popleft); `can_allocate` wants fast 'is this id used?' (set); the kernel wants stable "
                    "indexing by id (list).\n\n"
                    "**Why a deque (not list) for free?** Both ends in O(1): popleft for allocation, append for "
                    "free. List would be O(n) on popleft.\n\n"
                    "**Why keep stale hash entries?** Even after a block is freed, if nothing has overwritten it, "
                    "its KV content is still valid — a future cache hit can revive it for free. Hashes only get "
                    "removed in `_allocate_fresh` when the slot is actually about to be overwritten."
                ),
            },
        },
        "scheduler": {
            "title": "Scheduler queues",
            "body": (
                "**The scheduler is the policy** picking which sequences run each tick. Two FIFOs:\n"
                "• `waiting` — added via `add_request`, not yet started.\n"
                "• `running` — already prefilled, now generating one token per step.\n\n"
                "Each engine step does a **prefill pass first** (drain waiting until the per-step token budget runs out), "
                "and only if no seq was admitted for prefill does it fall through to a **decode pass** (one new token "
                "per running seq, all in one fused kernel call)."
            ),
            "structure": {
                "source": "nanovllm/engine/scheduler.py",
                "class_def": (
                    "class Scheduler:\n"
                    "    def __init__(self, config):\n"
                    "        self.max_num_seqs           = config.max_num_seqs\n"
                    "        self.max_num_batched_tokens = config.max_num_batched_tokens\n"
                    "        self.eos                    = config.eos\n"
                    "        self.block_size             = config.kvcache_block_size\n"
                    "        self.block_manager          = BlockManager(\n"
                    "            config.num_kvcache_blocks, config.kvcache_block_size,\n"
                    "        )\n"
                    "        self.waiting: deque[Sequence] = deque()\n"
                    "        self.running: deque[Sequence] = deque()"
                ),
                "fields": [
                    {"name": "max_num_seqs", "type": "int",
                     "role": "Cap on how many sequences the scheduler can pick per batch",
                     "example": "256 (default), 4 (this demo)",
                     "why": "Prevents a single batch from blowing up kernel launch overhead."},
                    {"name": "max_num_batched_tokens", "type": "int",
                     "role": "Cap on total tokens of forward-pass work per batch",
                     "example": "32k (default), 16 (this demo)",
                     "why": "Bounds per-step latency; in production this is tuned for the GPU's compute/memory roof."},
                    {"name": "eos", "type": "int",
                     "role": "Token id that signals end-of-sequence",
                     "why": "Used in `postprocess` to decide if a seq finished (alongside `max_tokens` check)."},
                    {"name": "block_manager", "type": "BlockManager",
                     "role": "Owns the KV cache pool; scheduler is the only caller of allocate/deallocate",
                     "why": "Composition: scheduler is the policy, block_manager is the mechanism."},
                    {"name": "waiting", "type": "deque[Sequence]",
                     "role": "FIFO of sequences added via `add_request` but not yet started",
                     "example": "deque([seq0, seq1]) → deque([seq1]) → deque([])",
                     "why": "deque: O(1) `popleft` for fairness (oldest first) + `appendleft` (for preempt)."},
                    {"name": "running", "type": "deque[Sequence]",
                     "role": "Sequences that have been prefilled and are now decoding one token per step",
                     "example": "deque([]) → deque([seq0]) → deque([seq0, seq1])",
                     "why": "deque: O(1) pop/append in decode loop; also `extendleft(reversed(...))` to preserve order after batched scheduling."},
                ],
                "relationships": [
                    {"to": "sequences",  "via": "queue membership", "kind": "`seq.status` ↔ which queue it lives in: WAITING↔waiting, RUNNING↔running, FINISHED↔neither."},
                    {"to": "block_pool", "via": "self.block_manager", "kind": "Composes BlockManager. `allocate/deallocate/may_append/hash_blocks` flow through scheduler."},
                ],
                "invariants": [
                    "`seq.status == WAITING  ⟺  seq ∈ waiting`",
                    "`seq.status == RUNNING  ⟺  seq ∈ running`",
                    "`seq.status == FINISHED ⟺  seq ∉ waiting and seq ∉ running`",
                    "`is_finished()  ⟺  waiting and running are both empty`",
                ],
                "design_notes": (
                    "**Two queues, not one with a status filter** — O(1) inspection of 'any prefills to do?' "
                    "vs 'any decodes to do?'. Also lets the prefill and decode passes be cleanly separated.\n\n"
                    "**Why prefill-first, decode-fallback?** Avoids prefill starvation: if running sequences "
                    "always blocked new ones, a busy server would never admit new requests. It also means each "
                    "batch is HOMOGENEOUS — either all prefill or all decode — which matters because the GPU "
                    "kernels for the two phases are different.\n\n"
                    "**Chunked-prefill rule** (`if remaining < num_tokens and scheduled_seqs: break`): permit the "
                    "first sequence in a batch to be partial-prefilled (use whatever budget remains), but if some "
                    "other seq already took budget, don't try to partial-prefill the next one. Keeps batches clean."
                ),
            },
        },
        "prefix_cache": {
            "title": "Prefix cache (hash → block_id)",
            "body": (
                "**The map that makes prefix sharing work.** When a block is fully filled (4 tokens here), its content "
                "is hashed and the mapping `hash → block_id` is recorded.\n\n"
                "Hashes are **chained**: block i's hash depends on (a) block i's tokens and (b) block i-1's hash. So a "
                "hash hit means the entire prefix matches — pull the existing block, don't recompute.\n\n"
                "Hash entries persist even after blocks are deallocated: the next sequence with a matching prefix can "
                "revive the cached KV for free."
            ),
            "structure": {
                "source": "nanovllm/engine/block_manager.py (compute_hash, hash_blocks)",
                "class_def": (
                    "# It's just a dict on BlockManager — no dedicated class.\n"
                    "self.hash_to_block_id: dict[int, int] = {}\n"
                    "\n"
                    "@classmethod\n"
                    "def compute_hash(cls, token_ids, prefix=-1):\n"
                    "    h = xxhash.xxh64()\n"
                    "    if prefix != -1:\n"
                    "        h.update(prefix.to_bytes(8, 'little'))   # chain previous hash\n"
                    "    h.update(np.array(token_ids).tobytes())      # this block's tokens\n"
                    "    return h.intdigest()\n"
                    "\n"
                    "def hash_blocks(self, seq):\n"
                    "    start = seq.num_cached_tokens // block_size\n"
                    "    end   = (seq.num_cached_tokens + seq.num_scheduled_tokens) // block_size\n"
                    "    h = self.blocks[seq.block_table[start - 1]].hash if start > 0 else -1\n"
                    "    for i in range(start, end):                  # only FULL blocks\n"
                    "        token_ids = seq.block(i)\n"
                    "        h = self.compute_hash(token_ids, h)\n"
                    "        self.blocks[seq.block_table[i]].update(h, token_ids)\n"
                    "        self.hash_to_block_id[h] = seq.block_table[i]"
                ),
                "fields": [
                    {"name": "hash (key)", "type": "int (xxhash64)",
                     "role": "Chained hash uniquely identifying a prefix",
                     "example": "0xabc123 (= hash([101,102,103,104], -1))",
                     "why": "xxh64 is fast and collision-resistant for typical token-id payloads."},
                    {"name": "block_id (value)", "type": "int",
                     "role": "Physical block where the hashed content lives",
                     "example": "0, 1, 2, …"},
                ],
                "relationships": [
                    {"to": "block_pool", "via": "Block.hash + Block.token_ids", "kind": "Lookup returns a block_id; `can_allocate` then double-checks `blocks[id].token_ids == prefix` as a safety net against hash collisions."},
                    {"to": "sequences",  "via": "can_allocate walks seq's logical blocks", "kind": "Hash chain is computed by walking the new seq's blocks; first miss terminates the walk."},
                ],
                "invariants": [
                    "Hash chains are **prefix-only**: `hash_to_block_id[h]` is registered ONLY after a full block is finalised in postprocess.",
                    "The mapping may point at a freed (ref_count=0) block — that's intentional, so freed blocks can be revived.",
                    "When `_allocate_fresh` overwrites a block, its old hash entry is removed: `del hash_to_block_id[old_hash]`.",
                ],
                "design_notes": (
                    "**Why chain?** A single block's content can be identical across two different prefixes (e.g. "
                    "the punctuation `[' ', ' ', ' ', ' ']` block). Without chaining, a hash hit on that block "
                    "would falsely claim 'whole prefix matches'. With chaining, the hash means 'exactly this "
                    "prefix in this order' — unambiguous.\n\n"
                    "**Why dict, not LRU/etc.?** Hash entries are tiny (int → int); unbounded growth is fine. "
                    "What's actually bounded is the BLOCKS — and entries die naturally when the block they point "
                    "at gets reused (the slot's hash is deleted in `_allocate_fresh`).\n\n"
                    "**Why only full blocks?** Partial blocks are still being written to (decode tokens trickling "
                    "in); their hash isn't stable until the block fills."
                ),
            },
        },
    }

    # ---------- Code panes ----------
    code_panes = []
    nano = Path("/tmp/nano-vllm")
    for pid, rel in [
        ("engine",        "nanovllm/engine/llm_engine.py"),
        ("scheduler",     "nanovllm/engine/scheduler.py"),
        ("block_manager", "nanovllm/engine/block_manager.py"),
        ("sequence",      "nanovllm/engine/sequence.py"),
        ("example",       "example.py"),
    ]:
        lines = [
            {"line_num": i + 1, "content": line.rstrip("\n")}
            for i, line in enumerate((nano / rel).read_text().splitlines())
        ]
        code_panes.append({"id": pid, "file": rel, "language": "python", "lines": lines})

    return {
        "metadata": {
            "title": "Inside nano-vLLM — PagedAttention & prefix cache",
            "subject": "github.com/GeeeekExplorer/nano-vllm",
            "entry_point": "LLM.generate([promptA, promptB], SamplingParams(max_tokens=2))",
            "config": {
                "block_size": BLOCK_SIZE,
                "num_kvcache_blocks": NUM_BLOCKS,
                "max_num_seqs": MAX_NUM_SEQS,
                "max_num_batched_tokens": MAX_NUM_BATCHED_TOKENS,
            },
        },
        "narrative": {
            "one_liner": "Two prompts sharing an 8-token prefix demonstrate PagedAttention block management, continuous batching, and cross-request prefix caching.",
            "description": "Watch a query traverse nano-vLLM end-to-end. promptA = [101..108, 201..204], promptB = [101..108, 301..304] — the first 8 tokens are shared. promptA gets 3 fresh blocks; promptB hits the prefix cache and reuses 2 of them.",
        },
        "storylines": tr.storylines,
        "pane_intros": pane_intros,
        "code_panes": code_panes,
        "steps": tr.steps,
    }


def main():
    here = Path(__file__).parent
    template = (here / "template.html").read_text()
    trace = build_trace()
    output = template.replace("/*TRACE_DATA_PLACEHOLDER*/", json.dumps(trace, ensure_ascii=False))
    out_path = here / "nano_vllm_trace.html"
    out_path.write_text(output)
    print(f"Wrote {out_path}")
    print(f"  {len(trace['steps'])} steps across {len(trace['storylines'])} storylines")
    print(f"  {len(trace['pane_intros'])} pane intros, "
          f"{sum(1 for s in trace['steps'] if 'primer' in s)} step primers")
    print(f"  {len(output) // 1024} KB")


if __name__ == "__main__":
    main()
