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

    def add(self, title, pc_dict, narration, *, primer=None, highlights=None, state_diff=None):
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
        if state_diff:
            step["state_diff"] = state_diff
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
    # ST1 — Request arrives  (5 steps)
    # ============================================
    tr.storyline(
        "ST1", "1. Request arrives",
        "Two prompts enter via add_request and queue up. KV cache is untouched until the scheduler admits them."
    )

    tr.add(
        title="User code: llm.generate(prompts, max_tokens=2)",
        pc_dict=pc("user_call_generate"),
        narration=(
            "`example.py:main()` builds two prompts and calls `llm.generate(prompts, sp)`. "
            "Engine idle: 0 sequences, 16 free blocks."
        ),
        primer=(
            "**vLLM:** an LLM inference server. The challenge: each token's K/V tensors must live in GPU memory, "
            "and naively giving each request a contiguous KV region either over-allocates or refuses requests "
            "under load. **vLLM's idea:** chop the KV cache into fixed-size *physical blocks* — like virtual "
            "memory pages — and let each sequence track its blocks via a `block_table`. The whole trace shows "
            "how this plays out."
        ),
        highlights=[],
    )

    tr.add(
        title="Inside generate() — for-loop enqueues prompts",
        pc_dict=pc("generate_for_loop"),
        narration=(
            "`generate()` is a thin wrapper. Body: a `for prompt: self.add_request(...)` enqueue loop, "
            "then a `while not is_finished(): self.step()` pump."
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
            "Tokenize prompt → 12 token ids. Build `Sequence(status=WAITING)`. `scheduler.add(seq)` pushes onto "
            "the `waiting` deque. No GPU memory touched."
        ),
        state_diff="+ seq 0 (WAITING, 12 prompt tokens) · waiting: [] → [0]",
        primer=(
            "**Sequence — the engine's view of one request.** Key fields: `token_ids` (prompt + completion), "
            "`status` (WAITING/RUNNING/FINISHED), `num_cached_tokens` (tokens whose KV already lives in blocks), "
            "`num_scheduled_tokens` (tokens this step's forward pass will compute), `block_table` "
            "(list of physical block IDs — the seq's only link to KV memory)."
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
            "Same for promptB. Both prompts share their first 8 tokens; the scheduler doesn't notice yet."
        ),
        state_diff="+ seq 1 (WAITING, 12 prompt tokens) · waiting: [0] → [0, 1]",
        highlights=["sequences", "scheduler"],
    )

    tr.add(
        title="Back in generate() — enter the engine pump",
        pc_dict=pc("generate_while_loop"),
        narration=(
            "For-loop exits. `while not self.is_finished(): output, num = self.step()` begins. "
            "Step into the first `step()`."
        ),
        primer=(
            "**engine.step() is the heartbeat.** Each call: exactly one scheduler decision + exactly one "
            "forward pass. The scheduler picks between *prefill* (admit a new prompt, large forward pass) "
            "and *decode* (advance each running seq by one token). Synchronous orchestration; the GPU work "
            "lives in `ModelRunner.call(\"run\", ...)`."
        ),
        highlights=["scheduler"],
    )

    # ============================================
    # ST2 — First prefill: cold cache  (6 steps)
    # ============================================
    tr.storyline(
        "ST2", "2. First prefill — cold cache",
        "Scheduler admits seq 0, allocates 3 fresh blocks, the model runs prefill, the resulting full blocks are hashed into the prefix cache."
    )

    tr.add(
        title="step() → schedule() — try prefill on seq 0",
        pc_dict=pc("schedule_can_allocate"),
        narration=(
            "Inside `step()` at L50: `seqs, is_prefill = self.scheduler.schedule()`. "
            "Schedule's prefill loop, head of waiting = seq 0, budget = 16. "
            "Call `block_manager.can_allocate(seq)`."
        ),
        highlights=["scheduler"],
    )

    tr.add(
        title="can_allocate(seq 0) — cache miss → num_cached=0",
        pc_dict=pc("can_allocate_loop"),
        narration=(
            "Walk `range(seq.num_blocks - 1)`. i=0: hash(`[101..104]`) → miss (cache empty). Break. "
            "Need 3 fresh, 16 free → return `0`."
        ),
        primer=(
            "**Logical vs physical blocks.** A sequence groups its tokens into *logical blocks* of `block_size` "
            "tokens each. Each logical block is backed by some *physical block* in the pool, looked up via "
            "`block_table[logical_idx] = physical_id`. **The block_table IS the PagedAttention mapping** — "
            "the CUDA attention kernel reads it every forward pass to find each token's KV slot. Two sequences "
            "can point at the same physical block; that's how prefix sharing works without copying any K/V data."
        ),
        highlights=["prefix_cache", "block_pool"],
    )

    n = tr.bm.can_allocate(seq_a)
    assert n == 0
    tr.bm.allocate(seq_a, n)
    tr.add(
        title="allocate(seq 0) — pop 3 fresh blocks → [0, 1, 2]",
        pc_dict=pc("allocate_loop"),
        narration=(
            "Pop blocks 0, 1, 2 from `free_block_ids` (FIFO). `seq0.block_table = [0, 1, 2]`. "
            "`num_cached_tokens = 0` (nothing cached this round)."
        ),
        state_diff="seq 0.block_table: [] → [0, 1, 2] · free 16→13 · blocks 0,1,2 ref→1",
        highlights=["sequences", "block_pool"],
    )

    seq_a.num_scheduled_tokens = 12
    seq_a.status = "RUNNING"
    tr.waiting_q.remove(seq_a.seq_id)
    tr.running_q.append(seq_a.seq_id)
    tr.add(
        title="seq 0 → RUNNING; seq 1 deferred (budget=4 < 12)",
        pc_dict=pc("schedule_running"),
        narration=(
            "`num_scheduled_tokens = 12`, batch takes 12 of 16 budget. Status WAITING → RUNNING. "
            "Try seq 1: budget=4 < 12, chunked-prefill rule → break."
        ),
        state_diff="seq 0: WAITING → RUNNING · scheduled_tokens 0→12 · waiting [0,1]→[1] · running []→[0]",
        highlights=["sequences", "scheduler"],
    )

    tr.add(
        title="ModelRunner.run([seq 0], prefill) — sample 401",
        pc_dict=pc("step_call_modelrunner"),
        narration=(
            "Back in step() body. Forward pass on 12 prompt tokens via seq 0's `block_table`. "
            "Samples first decode token."
        ),
        state_diff="sampled token: 401",
        highlights=[],
    )

    tr.bm.hash_blocks(seq_a)
    seq_a.num_cached_tokens += seq_a.num_scheduled_tokens
    seq_a.num_scheduled_tokens = 0
    seq_a.append_token(SAMPLED[(0, "prefill")])
    tr.add(
        title="postprocess(seq 0) — hash 3 blocks, append 401",
        pc_dict=pc("postprocess_hash"),
        narration=(
            "step()'s next call: `scheduler.postprocess`. Inside: `hash_blocks(seq)` chains h0→h1→h2 and writes "
            "to `hash_to_block_id`. Then `seq.append_token(401)`."
        ),
        state_diff="+ prefix_cache {h0→0, h1→1, h2→2} · blocks 0,1,2 .hash set · seq 0 num_cached 0→12 · seq 0.tokens += [401]",
        primer=(
            "**Prefix cache via chained hashes.** When a block fills, hash its content and register `hash → block_id`. "
            "Hashes CHAIN: block i's hash includes block i-1's hash, so a hit identifies the entire prefix up to and "
            "including that block. Future seqs with matching prefixes reuse the blocks — no recomputation. "
            "Crucially, hash entries persist even after blocks deallocate, so freed blocks can be revived if their "
            "content hasn't yet been overwritten."
        ),
        highlights=["block_pool", "prefix_cache", "sequences"],
    )

    # ============================================
    # ST3 — Second prefill: prefix-cache hit  (6 steps)
    # ============================================
    tr.storyline(
        "ST3", "3. Second prefill — prefix-cache hit",
        "step() #2. seq 1 gets 2 cached blocks from seq 0; the prefill forward pass shrinks from 12 to 4 tokens."
    )

    tr.add(
        title="step() #2 → schedule(seq 1) — cache is populated now",
        pc_dict=pc("schedule_can_allocate"),
        narration=(
            "generate's while loop iterates. step() #2 → schedule() tries prefill on head of waiting = seq 1. "
            "Calls `can_allocate`."
        ),
        highlights=["scheduler"],
    )

    tr.add(
        title="can_allocate(seq 1) — chained hash matches → num_cached=2",
        pc_dict=pc("can_allocate_loop"),
        narration=(
            "i=0: hash(`[101..104]`) → hit (block 0). i=1: hash(`[105..108]`, chained) → hit (block 1). "
            "Both currently used → `num_new_blocks: 3 → 1`. Return `2`."
        ),
        primer=(
            "**Why prefix sharing wins in production:** the same prefix appears across many requests — system "
            "prompts (\"You are a helpful assistant…\"), few-shot examples, chat history. Each shared block "
            "saves one `block_size` of compute on the prefill. Long shared prefixes compound; savings scale "
            "linearly with their length."
        ),
        highlights=["prefix_cache", "block_pool"],
    )

    n = tr.bm.can_allocate(seq_b)
    assert n == 2
    tr.bm.allocate(seq_b, n)
    tr.add(
        title="allocate(seq 1, num_cached=2) — share 0, 1; fresh 3",
        pc_dict=pc("allocate_loop"),
        narration=(
            "For cached blocks: refcount++ (blocks 0, 1: 1 → 2). For the 3rd: pop fresh block 3. "
            "`seq1.block_table = [0, 1, 3]`. `num_cached_tokens = 8`."
        ),
        state_diff="seq 1.block_table: [] → [0, 1, 3] · blocks 0,1 ref 1→2 · block 3 ref→1 · free 13→12",
        highlights=["block_pool", "sequences"],
    )

    seq_b.num_scheduled_tokens = seq_b.num_tokens - seq_b.num_cached_tokens
    seq_b.status = "RUNNING"
    tr.waiting_q.remove(seq_b.seq_id)
    tr.running_q.append(seq_b.seq_id)
    tr.add(
        title="seq 1 → RUNNING — only 4 tokens to forward",
        pc_dict=pc("schedule_running"),
        narration=(
            "`num_scheduled_tokens = 12 − 8 = 4`. Only the divergent suffix needs forward pass; cached 8 already "
            "in blocks 0, 1."
        ),
        state_diff="seq 1: WAITING → RUNNING · scheduled_tokens 0→4 · waiting [1]→[] · running [0]→[0,1]",
        highlights=["sequences", "scheduler"],
    )

    tr.add(
        title="ModelRunner.run([seq 1], prefill) — chunked, 4 tokens, sample 501",
        pc_dict=pc("step_call_modelrunner"),
        narration=(
            "Back in step(). Forward pass on 4 NEW tokens; attention reads cached KV from blocks 0, 1, 3 via "
            "block_table. **4 tok-forwards instead of 12.** Sample 501."
        ),
        state_diff="sampled token: 501",
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
            "Block 3 (= `[301..304]`) is now full → hash it, add to prefix cache. `append_token(501)`."
        ),
        state_diff="+ prefix_cache {h3→3} · block 3 .hash set · seq 1 num_cached 8→12 · seq 1.tokens += [501]",
        highlights=["block_pool", "prefix_cache", "sequences"],
    )

    # ============================================
    # ST4 — Decode: continuous batching  (4 steps)
    # ============================================
    tr.storyline(
        "ST4", "4. Decode — continuous batching",
        "step() #3. Both sequences advance by one token in a single fused forward pass; each attends via its own block_table."
    )

    tr.add(
        title="step() #3 — schedule()'s decode pass",
        pc_dict=pc("schedule_decode"),
        narration=(
            "Waiting is empty → prefill loop runs zero iterations → fall through to decode. Pop each running seq, "
            "call `may_append`, then batched forward."
        ),
        primer=(
            "**Decode = per-token loop.** After prefill, each forward pass generates ONE new token per seq. "
            "The scheduler batches ALL running seqs into ONE fused kernel call — *continuous batching*. "
            "Each seq still attends to its own history via its own `block_table`; the kernel handles per-seq "
            "differences via those lookups."
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
            "`len(seq 0) = 13`, `13 mod 4 = 1` → need a new logical block. Pop block 4. "
            "`seq0.block_table = [0, 1, 2, 4]`. Flip `is_prefill = False`."
        ),
        state_diff="seq 0.block_table: [0,1,2] → [0,1,2,4] · block 4 ref→1 · free 12→11 · seq 0.is_prefill T→F",
        highlights=["sequences", "block_pool"],
    )

    tr.bm.may_append(seq_b)
    seq_b.num_scheduled_tokens = 1
    seq_b.is_prefill = False
    tr.add(
        title="may_append(seq 1) — len=13, allocate block 5",
        pc_dict=pc("may_append_check"),
        narration=(
            "Same for seq 1: pop block 5. `seq1.block_table = [0, 1, 3, 5]`."
        ),
        state_diff="seq 1.block_table: [0,1,3] → [0,1,3,5] · block 5 ref→1 · free 11→10 · seq 1.is_prefill T→F",
        highlights=["sequences", "block_pool"],
    )

    tr.add(
        title="ModelRunner.run([seq 0, seq 1], decode) — batched, sample 402 + 502",
        pc_dict=pc("step_call_modelrunner"),
        narration=(
            "One fused forward pass produces one new token per seq. Each attends via its own block_table. "
            "Sample seq 0 → 402, seq 1 → 502."
        ),
        state_diff="sampled tokens: 402, 502",
        highlights=[],
    )

    # ============================================
    # ST5 — Teardown  (2 steps)
    # ============================================
    tr.storyline(
        "ST5", "5. Teardown — refs unwind",
        "Both reach max_tokens=2, status FINISHED, blocks deallocate (ref_count drops, shared blocks survive once). Hash entries stay in the prefix cache. generate() returns."
    )

    for seq, tok in [(seq_a, SAMPLED[(0, "decode1")]), (seq_b, SAMPLED[(1, "decode1")])]:
        seq.num_cached_tokens += seq.num_scheduled_tokens
        seq.num_scheduled_tokens = 0
        seq.append_token(tok)
        seq.status = "FINISHED"
        tr.bm.deallocate(seq)
        tr.running_q.remove(seq.seq_id)

    tr.add(
        title="postprocess — both FINISH, deallocate cascades",
        pc_dict=pc("postprocess_finish"),
        narration=(
            "Append decode tokens. Both `num_completion = 2 = max_tokens` → FINISHED. "
            "`deallocate` walks block_table in reverse; `ref_count--`, freed when 0. Block 0 was shared (ref=2) → "
            "seq 0 drops it to 1, then seq 1 drops it to 0 → freed."
        ),
        state_diff="seq 0,1: RUNNING → FINISHED · blocks 0,1: ref 2→1→0 (freed) · blocks 2,3,4,5: ref 1→0 (freed) · free 10→16 · running [0,1]→[] · prefix_cache unchanged",
        primer=(
            "**Reference counting for safe sharing.** Each block tracks `ref_count` = number of seqs pointing at "
            "it. `allocate` increments, `deallocate` decrements. A block returns to the free pool only when ref=0. "
            "Shared blocks survive one finish, freed on the next. Crucially: **hash entries STAY in the prefix "
            "cache** — a freed block whose content isn't yet overwritten can still serve a cache hit."
        ),
        highlights=["sequences", "block_pool", "prefix_cache"],
    )

    tr.add(
        title="generate() returns — done",
        pc_dict=pc("generate_return"),
        narration=(
            "`is_finished()` = True. Loop exits. Collect each seq's completion `token_ids`, run through "
            "`tokenizer.decode`, return text."
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
