#!/usr/bin/env python3
"""
Simulate nano-vLLM's LLMEngine + Scheduler + BlockManager logic on a
fixed demo scenario (two prompts sharing an 8-token prefix), emitting a
trace JSON that captures the engine's state at each interesting moment.
The trace gets injected into template.html → nano_vllm_trace.html.

The simulator MIRRORS nano-vllm/nanovllm/engine/{sequence,scheduler,
block_manager}.py (see /tmp/nano-vllm). It does NOT run the actual
model — sampled tokens are stubbed.

v0.2 additions over the bare prototype:
  - Top-level `storylines`: groups steps into named chapters for navigation
  - Top-level `pane_intros`: ELI5 explanations of each state pane
  - Per-step optional `primer`: deeper concept background, shown in
    Tutorial verbosity mode (default)
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
    """Deterministic hash matching nano-vllm's block-hash chain pattern."""
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

    def add(self, title, pc, narration, *, primer=None, highlights=None):
        sid = f"S{len(self.steps) + 1}"
        step = {
            "id": sid,
            "title": title,
            "pc": pc,
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
        "Two prompts enter the engine and queue up. The KV cache is untouched until the scheduler admits them on a future tick."
    )

    tr.add(
        title="Initial — engine idle, all 16 blocks free",
        pc={"code_pane_id": "example", "line": 24},
        narration=(
            "User runs `example.py`, calling `llm.generate([promptA, promptB], SamplingParams(max_tokens=2))`. "
            "Engine just constructed: 0 sequences, all 16 KV blocks free. "
            "Demo configuration: `block_size=4` (small for visualisation; nano-vLLM defaults to 256), "
            "`max_num_batched_tokens=16` (kept small so the two 12-token prompts can't both prefill in one batch — "
            "this is what surfaces the prefix-cache hit later)."
        ),
        primer=(
            "**What is vLLM?** An LLM inference server. Per request you send a prompt and get a completion. "
            "The challenge: each token a model attends to has a key/value tensor pair that needs to live in GPU memory; "
            "with naive contiguous allocation the server either over-allocates (wasteful) or refuses requests (stalls under load). "
            "**vLLM's idea (PagedAttention):** chop the KV cache into fixed-size *physical blocks*, like virtual memory pages. "
            "Each sequence holds a `block_table` — a list of physical block IDs — and the attention kernel reads K/V from "
            "wherever the block_table points. Non-contiguous, but the GPU doesn't care. **The bonus prize:** if two sequences "
            "share a prompt prefix, they can literally point at the same physical blocks. That's prefix caching."
        ),
        highlights=[],
    )

    seq_a = Sequence(prompt_a, max_tokens=2)
    tr.sequences_map[seq_a.seq_id] = seq_a
    tr.waiting_q.append(seq_a.seq_id)
    tr.add(
        title="add_request(promptA) — seq 0 enters waiting queue",
        pc={"code_pane_id": "engine", "line": 47},
        narration=(
            "`LLMEngine.add_request` tokenises the prompt (12 token ids) and constructs a `Sequence` "
            "with `status=WAITING`. `scheduler.add(seq)` pushes it onto the `waiting` deque. "
            "No GPU memory touched yet — the KV cache only sees a sequence after the scheduler admits it."
        ),
        primer=(
            "**Sequence — the engine's view of one request.** Fields that matter: `token_ids` (prompt + completion-so-far), "
            "`status` (WAITING → RUNNING → FINISHED), `num_cached_tokens` (how many tokens already have their KV stored in blocks), "
            "`num_scheduled_tokens` (how many tokens THIS step's forward pass will compute), and `block_table` (the list of "
            "physical block IDs holding this seq's KV — empty until the scheduler runs)."
        ),
        highlights=["sequences", "scheduler"],
    )

    seq_b = Sequence(prompt_b, max_tokens=2)
    tr.sequences_map[seq_b.seq_id] = seq_b
    tr.waiting_q.append(seq_b.seq_id)
    tr.add(
        title="add_request(promptB) — seq 1 enters waiting queue",
        pc={"code_pane_id": "engine", "line": 47},
        narration=(
            "Same path for prompt B. The two prompts share their first 8 tokens (`[101..108]`) — "
            "exactly 2 blocks — but the scheduler doesn't know about prefix sharing yet; both just sit "
            "in WAITING as plain rows on the queue."
        ),
        highlights=["sequences", "scheduler"],
    )

    # ============================================
    # ST2 — First prefill: cold cache
    # ============================================
    tr.storyline(
        "ST2", "2. First prefill — cold cache",
        "Scheduler admits seq 0, the block manager allocates 3 fresh blocks for the prompt, the model runs a prefill forward pass, and the resulting full blocks are hashed into the prefix cache."
    )

    tr.add(
        title="engine.step() #1 — enter scheduler",
        pc={"code_pane_id": "engine", "line": 56},
        narration=(
            "First `engine.step()`. The scheduler runs in two passes: **prefill** first (drain `waiting` until "
            "the token budget runs out), then **decode** only if no sequence was admitted for prefill. "
            "Budget per step is `max_num_batched_tokens=16` tokens of forward-pass work."
        ),
        primer=(
            "**engine.step() is the heartbeat.** `generate()` calls it in a tight loop until everything finishes. "
            "Each call goes through the scheduler **exactly once**, then forwards the picked sequences through the model "
            "**exactly once**. The scheduler is the policy that decides *who* runs *what* this tick: prefill (admit a new "
            "prompt, do its first big forward pass) or decode (advance each running seq by one token)."
        ),
        highlights=["scheduler"],
    )

    tr.add(
        title="Schedule seq 0: BlockManager.can_allocate(seq 0)",
        pc={"code_pane_id": "scheduler", "line": 29},
        narration=(
            "Head of `waiting`: seq 0. The scheduler asks the block manager: how many of seq 0's blocks can be reused "
            "from the prefix cache? `can_allocate` walks block-by-block, computing a CHAINED hash "
            "(each block's hash includes the previous block's hash, so a hash hit means the whole prefix matches)."
        ),
        primer=(
            "**Logical vs physical blocks.** A sequence sees its tokens grouped into `logical blocks` of `block_size` tokens each "
            "— logical block 0 holds tokens 0..3, logical block 1 holds tokens 4..7, etc. Each logical block is stored in "
            "some `physical block` in the pool, looked up via `block_table[logical_idx] = physical_id`. The scheduler decides "
            "WHICH physical blocks to give to this seq before running the forward pass."
        ),
        highlights=["scheduler", "prefix_cache"],
    )

    tr.add(
        title="can_allocate(seq 0) → num_cached_blocks = 0",
        pc={"code_pane_id": "block_manager", "line": 51},
        narration=(
            "Walk seq 0's blocks: block 0 = `[101,102,103,104]`. `hash_to_block_id` lookup → miss "
            "(prefix cache is empty — this is the first sequence ever). Loop breaks immediately. "
            "Need 3 fresh blocks; 16 free → OK. Return `0`."
        ),
        highlights=["prefix_cache", "block_pool"],
    )

    n = tr.bm.can_allocate(seq_a)
    assert n == 0
    tr.bm.allocate(seq_a, n)
    tr.add(
        title="allocate(seq 0, num_cached=0) — fresh physical blocks [0, 1, 2]",
        pc={"code_pane_id": "block_manager", "line": 67},
        narration=(
            "No cached blocks → pop 3 fresh ones from `free_block_ids`. "
            "`seq0.block_table = [0, 1, 2]`. This list IS the PagedAttention mapping: when the CUDA kernel computes "
            "attention for token `i` of seq 0, it looks up logical block `i // block_size`, fetches "
            "physical block `block_table[…]`, then reads KV slot `i % block_size` inside it."
        ),
        primer=(
            "**This is the core of PagedAttention.** Instead of giving each sequence one big contiguous KV region "
            "(which forces you to over-allocate for the worst-case sequence length), vLLM gives each seq a `block_table`: "
            "a list of physical block IDs. Logical block i maps to physical block `block_table[i]`. Two sequences can "
            "point at the SAME physical block — that's how prefix sharing works without copying. The CUDA attention "
            "kernel reads the block_table to gather K/V slots from non-contiguous memory."
        ),
        highlights=["sequences", "block_pool"],
    )

    seq_a.num_scheduled_tokens = 12
    seq_a.status = "RUNNING"
    tr.waiting_q.remove(seq_a.seq_id)
    tr.running_q.append(seq_a.seq_id)
    tr.add(
        title="seq 0 fully scheduled (12 tokens) → RUNNING",
        pc={"code_pane_id": "scheduler", "line": 38},
        narration=(
            "`num_scheduled_tokens=12` (all of the prompt). `num_batched_tokens = 12 ≤ 16` → fits. "
            "All tokens scheduled, so the seq moves WAITING → RUNNING (and from `waiting` to `running` queue)."
        ),
        highlights=["sequences", "scheduler"],
    )

    tr.add(
        title="Try seq 1: budget remaining=4, needs 12 → defer",
        pc={"code_pane_id": "scheduler", "line": 35},
        narration=(
            "Budget left: `16 − 12 = 4`. seq 1 needs 12. The chunked-prefill rule "
            "(`if remaining < num_tokens and scheduled_seqs: break`) says only the FIRST seq in a batch may be chunked; "
            "seq 0 already took that slot. So break — seq 1 waits for the next step."
        ),
        highlights=["scheduler"],
    )

    tr.add(
        title="ModelRunner.run([seq 0], prefill=True) — forward pass on 12 tokens",
        pc={"code_pane_id": "engine", "line": 58},
        narration=(
            "Model runner gathers seq 0's KV slots via its `block_table`, runs a forward pass over the full 12-token prompt, "
            "and samples the next token from the final hidden state. **Sampled token: 401** "
            "(stubbed here — in real nano-vLLM this comes from the sampling kernel)."
        ),
        highlights=[],
    )

    tr.bm.hash_blocks(seq_a)
    seq_a.num_cached_tokens += seq_a.num_scheduled_tokens
    seq_a.num_scheduled_tokens = 0
    seq_a.append_token(SAMPLED[(0, "prefill")])
    tr.add(
        title="postprocess(seq 0): hash_blocks + append token 401",
        pc={"code_pane_id": "scheduler", "line": 75},
        narration=(
            "Prefill finished → every FULL block gets hashed and indexed in `hash_to_block_id`. "
            "Hashes are chained: `h0 = hash([101..104], -1)`, `h1 = hash([105..108], h0)`, `h2 = hash([201..204], h1)`. "
            "Now the cache has 3 entries. Append the sampled token to seq 0 — the 13th token will spill out of the "
            "current block (12 = 3 × block_size); a new block will be allocated by `may_append` on the next decode step."
        ),
        primer=(
            "**The prefix cache lives in `hash_to_block_id`.** When a block is fully filled, it's hashed and the mapping "
            "`hash → block_id` is recorded. Hashes CHAIN: block i's hash depends on (a) block i's tokens and (b) "
            "block i-1's hash. So a hash hit on block N tells you the entire prefix of N+1 blocks matches what's already "
            "in some physical block — pull it instead of recomputing."
        ),
        highlights=["block_pool", "prefix_cache", "sequences"],
    )

    # ============================================
    # ST3 — Second prefill: prefix-cache hit
    # ============================================
    tr.storyline(
        "ST3", "3. Second prefill — prefix-cache hit",
        "Scheduler admits seq 1. The block manager finds 2 of its blocks already in the prefix cache → only 1 new block is allocated; the prefill forward pass shrinks from 12 tokens to 4."
    )

    tr.add(
        title="engine.step() #2 — schedule seq 1 with cache hit",
        pc={"code_pane_id": "engine", "line": 56},
        narration=(
            "Another step. Prefill phase: walk `waiting` again. Only seq 1 is there. "
            "This time the prefix cache is populated — watch what happens."
        ),
        highlights=["scheduler"],
    )

    tr.add(
        title="can_allocate(seq 1) — prefix cache walk",
        pc={"code_pane_id": "block_manager", "line": 51},
        narration=(
            "Walk seq 1's blocks: block(0) = `[101..104]`, hash matches → **cache hit on block 0!** "
            "block(1) = `[105..108]`, chained hash matches → **cache hit on block 1!** "
            "Loop ends (only iterates `range(num_blocks − 1)`, i.e. up to 2, so it never checks the last block). "
            "`num_cached_blocks = 2`; `num_new_blocks` decremented twice because both cached blocks are currently in "
            "`used_block_ids` (still held by seq 0) → only 1 new block to allocate."
        ),
        primer=(
            "**Why prefix sharing matters in production:** the same prompt prefix appears in many real workloads — "
            "system prompts shared across users (\"You are a helpful assistant…\"), few-shot examples shared across "
            "queries, conversation history shared across follow-ups. With a populated prefix cache, the second-and-later "
            "sequences only need forward passes for the *divergent suffix*. Savings scale linearly with how long the "
            "shared prefix is — for a long system prompt, that's huge."
        ),
        highlights=["prefix_cache", "block_pool"],
    )

    n = tr.bm.can_allocate(seq_b)
    assert n == 2, f"expected 2 cached for seq 1, got {n}"
    tr.bm.allocate(seq_b, n)
    tr.add(
        title="allocate(seq 1, num_cached=2) — share blocks 0,1; fresh block 3",
        pc={"code_pane_id": "block_manager", "line": 67},
        narration=(
            "For each of the 2 cached blocks: since `block_id ∈ used_block_ids`, just bump `ref_count` "
            "(block 0: 1 → 2, block 1: 1 → 2). For the 3rd block (the divergent suffix `[301..304]`): "
            "allocate a fresh block 3. `seq1.block_table = [0, 1, 3]`. `seq1.num_cached_tokens = 8`."
        ),
        highlights=["block_pool", "sequences"],
    )

    seq_b.num_scheduled_tokens = seq_b.num_tokens - seq_b.num_cached_tokens
    seq_b.status = "RUNNING"
    tr.waiting_q.remove(seq_b.seq_id)
    tr.running_q.append(seq_b.seq_id)
    tr.add(
        title="seq 1 scheduled (only 4 uncached tokens) → RUNNING",
        pc={"code_pane_id": "scheduler", "line": 33},
        narration=(
            "`num_scheduled_tokens = 12 − 8 = 4`. The forward pass only needs to compute KV for the 4 new tokens — "
            "the cached 8 tokens already have their K and V in physical blocks 0,1. Status → RUNNING."
        ),
        highlights=["sequences", "scheduler"],
    )

    tr.add(
        title="ModelRunner.run([seq 1], prefill=True) — chunked prefill on 4 tokens",
        pc={"code_pane_id": "engine", "line": 58},
        narration=(
            "Forward pass with only 4 new tokens. The attention kernel queries the cached KV in blocks 0,1 too, "
            "via seq 1's `block_table = [0,1,3]`. Output: one sampled token. **Sampled: 501.**"
        ),
        highlights=[],
    )

    tr.bm.hash_blocks(seq_b)
    seq_b.num_cached_tokens += seq_b.num_scheduled_tokens
    seq_b.num_scheduled_tokens = 0
    seq_b.append_token(SAMPLED[(1, "prefill")])
    tr.add(
        title="postprocess(seq 1): hash block 3 + append token 501",
        pc={"code_pane_id": "scheduler", "line": 75},
        narration=(
            "Block 3 (= `[301..304]`) is now full → hash it (chained from block 1's hash) and add to the prefix cache. "
            "Future sequences starting `[101..108, 301..304]` will reuse all 3 blocks. Append 501."
        ),
        highlights=["block_pool", "prefix_cache", "sequences"],
    )

    # ============================================
    # ST4 — Decode: continuous batching
    # ============================================
    tr.storyline(
        "ST4", "4. Decode — continuous batching",
        "Both sequences are running. Each engine step appends one token per seq via a single fused forward pass — that's continuous batching. Each seq still attends to its OWN history via its OWN block_table."
    )

    tr.add(
        title="engine.step() #3 — decode phase",
        pc={"code_pane_id": "engine", "line": 56},
        narration=(
            "No more waiting; the prefill loop is empty so the scheduler falls through to the **decode** loop: "
            "pop each running seq, ensure room for one more token via `may_append`, then forward-pass them all together "
            "in a single batched kernel call."
        ),
        primer=(
            "**Decode = per-token loop.** Once a sequence has been prefilled, each subsequent forward pass generates ONE "
            "new token. The trick is that the scheduler batches the decode passes of ALL currently-running sequences "
            "into ONE fused kernel call. Sequence A and Sequence B may be at different lengths, prompting different "
            "attention queries, but they share the forward pass — that's continuous batching. The kernel handles "
            "different per-seq lengths via the `block_table` lookups."
        ),
        highlights=["scheduler"],
    )

    tr.bm.may_append(seq_a)
    seq_a.num_scheduled_tokens = 1
    seq_a.is_prefill = False
    tr.add(
        title="may_append(seq 0) — len=13, allocate block 4",
        pc={"code_pane_id": "block_manager", "line": 112},
        narration=(
            "`len(seq 0) = 13` (12 prompt + 1 sampled). `13 mod block_size = 1` → the new token lands in a new logical block. "
            "Allocate fresh physical block 4. `seq0.block_table = [0, 1, 2, 4]`. "
            "Flip `is_prefill = False` — from now on, seq 0 produces one token per step."
        ),
        highlights=["sequences", "block_pool"],
    )

    tr.bm.may_append(seq_b)
    seq_b.num_scheduled_tokens = 1
    seq_b.is_prefill = False
    tr.add(
        title="may_append(seq 1) — len=13, allocate block 5",
        pc={"code_pane_id": "block_manager", "line": 112},
        narration=(
            "Same for seq 1: allocate fresh block 5. `seq1.block_table = [0, 1, 3, 5]`. "
            "Blocks 0 and 1 are still shared between seq 0 and seq 1 (`ref_count = 2`); "
            "blocks 2, 3, 4, 5 each have `ref_count = 1`."
        ),
        highlights=["sequences", "block_pool"],
    )

    tr.add(
        title="ModelRunner.run([seq 0, seq 1], prefill=False) — batched decode",
        pc={"code_pane_id": "engine", "line": 58},
        narration=(
            "**Continuous batching:** one forward pass produces one token per running sequence. "
            "Each sequence still attends to its OWN history via its OWN `block_table`, but the compute is fused into a "
            "single GPU kernel call. **Sampled: seq 0 → 402, seq 1 → 502.**"
        ),
        highlights=[],
    )

    # ============================================
    # ST5 — Teardown: refs unwind
    # ============================================
    tr.storyline(
        "ST5", "5. Teardown — refs unwind",
        "Both sequences reach max_tokens=2 and FINISH. Their blocks deallocate in reverse order. Shared blocks survive one decref; the second frees them. Hash entries STAY in the prefix cache for future hits."
    )

    for seq, tok in [(seq_a, SAMPLED[(0, "decode1")]), (seq_b, SAMPLED[(1, "decode1")])]:
        seq.num_cached_tokens += seq.num_scheduled_tokens
        seq.num_scheduled_tokens = 0
        seq.append_token(tok)
        seq.status = "FINISHED"
        tr.bm.deallocate(seq)
        tr.running_q.remove(seq.seq_id)

    tr.add(
        title="postprocess + deallocate — both sequences FINISHED",
        pc={"code_pane_id": "scheduler", "line": 81},
        narration=(
            "Each seq appends its sampled token. `num_completion_tokens = 2 = max_tokens` → FINISHED. "
            "`deallocate` walks `block_table` in reverse, decrementing `ref_count`. Block 0 was shared (ref=2) — "
            "drops to 1 when seq 0 is deallocated (seq 1 still uses it), then 0 when seq 1 is deallocated, then it's "
            "pushed onto `free_block_ids`. **Crucially: the hash entries in the prefix cache STAY.** The blocks "
            "themselves go back to free, but their hashes still point at them — so the very next sequence with a "
            "matching prefix gets a cache hit without re-prefilling."
        ),
        primer=(
            "**Reference counting: how shared blocks are freed safely.** Each physical block has a `ref_count` — the "
            "number of sequences currently using it. `allocate` increments, `deallocate` decrements. A block returns "
            "to the free pool ONLY when its ref_count hits 0. That's why a shared block survives the first sequence "
            "finishing if another still references it. Even after a block is freed, its content (the cached KV) and "
            "its hash mapping are still readable until something else claims and resets it — so prefix cache hits can "
            "still revive it for free."
        ),
        highlights=["sequences", "block_pool", "prefix_cache"],
    )

    tr.add(
        title="generate() returns — both completions ready",
        pc={"code_pane_id": "engine", "line": 86},
        narration=(
            "`is_finished()` is True (waiting + running both empty). `generate()` collects the completion token_ids "
            "per seq_id, runs them through `tokenizer.decode`, and returns the text. Done."
        ),
        highlights=[],
    )

    # ---------- Pane intros (ELI5 explainers) ----------
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
            )
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
                "Colours: **pale** = free, **blue** = used by one seq, **purple** = shared (ref ≥ 2), **dashed** = cached-but-free "
                "(hash is still in the prefix cache so it can be reclaimed by a matching prefix)."
            )
        },
        "scheduler": {
            "title": "Scheduler queues",
            "body": (
                "**The scheduler is the policy** picking which sequences run each tick. Two FIFOs:\n"
                "• `waiting` — added via `add_request`, not yet started.\n"
                "• `running` — already prefilled, now generating one token per step.\n\n"
                "Each engine step does a **prefill pass first** (drain waiting until the per-step token budget runs out), "
                "and only if no seq was admitted for prefill does it fall through to a **decode pass** (one new token per "
                "running seq, all in one fused kernel call)."
            )
        },
        "prefix_cache": {
            "title": "Prefix cache (hash → block_id)",
            "body": (
                "**The map that makes prefix sharing work.** When a block is fully filled (4 tokens here), its content "
                "is hashed and the mapping `hash → block_id` is recorded.\n\n"
                "Hashes are **chained**: block i's hash depends on (a) block i's tokens and (b) block i-1's hash. So a hash "
                "hit means the entire prefix matches — pull the existing block, don't recompute.\n\n"
                "Hash entries persist even after blocks are deallocated: the next sequence with a matching prefix can revive "
                "the cached KV for free."
            )
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
