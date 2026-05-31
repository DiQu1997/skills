#!/usr/bin/env python3
"""
Simulate nano-vLLM's LLMEngine + Scheduler + BlockManager logic on a
fixed demo scenario (two prompts sharing an 8-token prefix), emitting a
trace JSON that captures the engine's state at each interesting moment.
The trace gets injected into template.html → nano_vllm_trace.html.

The simulator MIRRORS nano-vllm/nanovllm/engine/{sequence,scheduler,
block_manager}.py (see /tmp/nano-vllm). It does NOT run the actual
model — sampled tokens are stubbed.
"""

import copy
import hashlib
import json
import sys
from collections import deque
from pathlib import Path

# ---------- Demo configuration (NOT nano-vllm's defaults — see narration) ----------
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
    """Deterministic hash matching nano-vllm's block-hash chain pattern.
    nano-vllm uses xxhash; we use sha1 hex prefix here for portability —
    semantics (prefix-chained) are identical."""
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

    @property
    def num_completion_tokens(self):
        return self.num_tokens - self.num_prompt_tokens

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
            {
                "hash": h,
                "block_id": bid,
                "preview": list(self.blocks[bid].token_ids),
            }
            for h, bid in self.hash_to_block_id.items()
        ]


# ---------- Trace recorder ----------

class Trace:
    def __init__(self):
        self.steps = []
        self.sequences_map = {}      # seq_id → Sequence
        self.waiting_q = []          # ordered list of seq_ids
        self.running_q = []
        self.bm = BlockManager(NUM_BLOCKS)

    def snapshot(self):
        return {
            "sequences": [s.to_state() for s in sorted(self.sequences_map.values(), key=lambda x: x.seq_id)],
            "block_pool": self.bm.to_state(),
            "scheduler": {"waiting": list(self.waiting_q), "running": list(self.running_q)},
            "prefix_cache": self.bm.prefix_cache_state(),
        }

    def add(self, title, pc, narration, highlights=None):
        self.steps.append({
            "id": f"S{len(self.steps) + 1}",
            "title": title,
            "pc": pc,
            "narration": narration,
            "highlights": highlights or [],
            "state": copy.deepcopy(self.snapshot()),
        })


# ---------- The scenario ----------

def build_trace() -> dict:
    tr = Trace()

    # Token ids designed so prompts share an 8-token (= 2 blocks) prefix.
    SHARED = [101, 102, 103, 104, 105, 106, 107, 108]
    prompt_a = SHARED + [201, 202, 203, 204]   # 12 tokens, 3 blocks
    prompt_b = SHARED + [301, 302, 303, 304]   # 12 tokens, 3 blocks

    SAMPLED = {
        (0, "prefill"):  401,
        (0, "decode1"):  402,
        (1, "prefill"):  501,
        (1, "decode1"):  502,
    }

    # ---- Step 0: initial state ----
    tr.add(
        title="Initial — engine idle, all 16 blocks free",
        pc={"code_pane_id": "example", "line": 24},
        narration=(
            "User runs `example.py`: `llm.generate([promptA, promptB], SamplingParams(max_tokens=2))`. "
            "Engine just constructed: 0 sequences, 16 free KV blocks, "
            "block_size=4 (small for visualisation; nano-vLLM defaults to 256), "
            "max_num_batched_tokens=16 (small enough that the two 12-token prompts can't both prefill in one batch — this is what surfaces the prefix-cache hit on step 2)."
        ),
        highlights=[],
    )

    # ---- Step 1: add_request(A) ----
    seq_a = Sequence(prompt_a, max_tokens=2)
    tr.sequences_map[seq_a.seq_id] = seq_a
    tr.waiting_q.append(seq_a.seq_id)
    tr.add(
        title="add_request(promptA) — seq 0 enters waiting queue",
        pc={"code_pane_id": "engine", "line": 47},
        narration=(
            "`LLMEngine.add_request` tokenises the prompt (12 token ids) and constructs a `Sequence` "
            "with `status=WAITING`. `scheduler.add(seq)` pushes it onto `waiting`. No GPU memory touched yet — "
            "the KV cache only sees a sequence after the scheduler admits it."
        ),
        highlights=["sequences", "scheduler"],
    )

    # ---- Step 2: add_request(B) ----
    seq_b = Sequence(prompt_b, max_tokens=2)
    tr.sequences_map[seq_b.seq_id] = seq_b
    tr.waiting_q.append(seq_b.seq_id)
    tr.add(
        title="add_request(promptB) — seq 1 enters waiting queue",
        pc={"code_pane_id": "engine", "line": 47},
        narration=(
            "Same path for prompt B. The two prompts share their first 8 tokens (`[101..108]`) — "
            "exactly 2 blocks — but the scheduler doesn't know about prefix sharing yet; both sit in WAITING "
            "as plain rows on the queue."
        ),
        highlights=["sequences", "scheduler"],
    )

    # ============================================
    # ENGINE.STEP() #1
    # ============================================

    tr.add(
        title="engine.step() #1 — enter scheduler",
        pc={"code_pane_id": "engine", "line": 56},
        narration=(
            "First `engine.step()`. The scheduler runs in two passes: **prefill** first (drain `waiting` "
            "until budget runs out), then **decode** only if no sequence was admitted for prefill. "
            "Budget per step is `max_num_batched_tokens=16` tokens of forward-pass work."
        ),
        highlights=["scheduler"],
    )

    # Try seq0 — can_allocate
    tr.add(
        title="Schedule seq 0: BlockManager.can_allocate(seq 0)",
        pc={"code_pane_id": "scheduler", "line": 29},
        narration=(
            "Head of waiting: seq 0. The scheduler asks the block manager: how many of seq 0's blocks "
            "can be reused from the prefix cache? Walks block-by-block, computing a CHAINED hash "
            "(each block's hash includes the previous block's hash, so a hash hit means the whole prefix matches)."
        ),
        highlights=["scheduler", "prefix_cache"],
    )

    tr.add(
        title="can_allocate(seq 0) → num_cached_blocks = 0",
        pc={"code_pane_id": "block_manager", "line": 51},
        narration=(
            "Walk seq 0's logical blocks: block 0 = `[101,102,103,104]`. `hash_to_block_id` lookup → miss "
            "(prefix cache is empty — this is the first sequence ever). Loop breaks immediately. "
            "Need 3 fresh blocks; 16 free → OK. Return `0`."
        ),
        highlights=["prefix_cache", "block_pool"],
    )

    # allocate(seq0, 0) — fresh
    n = tr.bm.can_allocate(seq_a)
    assert n == 0
    tr.bm.allocate(seq_a, n)
    tr.add(
        title="allocate(seq 0, num_cached=0) — fresh physical blocks [0, 1, 2]",
        pc={"code_pane_id": "block_manager", "line": 67},
        narration=(
            "No cached blocks → pop 3 fresh ones from `free_block_ids`. "
            "`seq0.block_table = [0, 1, 2]`. This list IS the PagedAttention mapping: when the CUDA kernel "
            "computes attention for token i of seq 0, it looks up logical block `i // block_size`, "
            "fetches physical block_id `block_table[…]`, then reads KV slot `i % block_size` inside it. "
            "Sequence memory becomes non-contiguous on purpose — that's how vLLM gets near-100% memory utilisation."
        ),
        highlights=["sequences", "block_pool"],
    )

    # seq0 scheduled → RUNNING
    seq_a.num_scheduled_tokens = 12
    seq_a.status = "RUNNING"
    tr.waiting_q.remove(seq_a.seq_id)
    tr.running_q.append(seq_a.seq_id)
    tr.add(
        title="seq 0 fully scheduled (12 tokens) → RUNNING",
        pc={"code_pane_id": "scheduler", "line": 38},
        narration=(
            "`num_scheduled_tokens=12` (all of the prompt). `num_batched_tokens = 12 ≤ 16` → fits. "
            "All tokens scheduled, so the seq moves WAITING → RUNNING (and waiting → running queue)."
        ),
        highlights=["sequences", "scheduler"],
    )

    # Try seq1 — chunked-prefill rule
    tr.add(
        title="Try seq 1: budget remaining=4, needs 12 → defer",
        pc={"code_pane_id": "scheduler", "line": 35},
        narration=(
            "Budget left: `16 − 12 = 4`. seq 1 needs 12. The chunked-prefill rule "
            "(`if remaining < num_tokens and scheduled_seqs: break`) says only the FIRST seq in a batch may be "
            "chunked; seq 0 already took that slot. So break — seq 1 waits for the next step."
        ),
        highlights=["scheduler"],
    )

    # ModelRunner.run on seq0
    tr.add(
        title="ModelRunner.run([seq 0], prefill=True) — forward pass on 12 tokens",
        pc={"code_pane_id": "engine", "line": 58},
        narration=(
            "Model runner gathers seq 0's KV slots via its `block_table`, runs a forward pass over "
            "the full 12-token prompt, and samples the next token from the final hidden state. "
            "**Sampled token: 401** (stubbed here — in real nano-vLLM this comes from the sampling kernel)."
        ),
        highlights=[],
    )

    # postprocess seq0
    tr.bm.hash_blocks(seq_a)
    seq_a.num_cached_tokens += seq_a.num_scheduled_tokens
    seq_a.num_scheduled_tokens = 0
    seq_a.append_token(SAMPLED[(0, "prefill")])
    tr.add(
        title="postprocess(seq 0): hash_blocks + append token 401",
        pc={"code_pane_id": "scheduler", "line": 75},
        narration=(
            "Prefill finished → every FULL block gets hashed and indexed in `hash_to_block_id`. "
            "Hashes are chained: `h0 = hash([101..104], -1)`, `h1 = hash([105..108], h0)`, "
            "`h2 = hash([201..204], h1)`. Now the cache has 3 entries. Append the sampled token to seq 0 — "
            "the 13th token spills out of the current block (12 = 3 × block_size); a new block will be "
            "allocated by `may_append` on the next decode step."
        ),
        highlights=["block_pool", "prefix_cache", "sequences"],
    )

    # ============================================
    # ENGINE.STEP() #2
    # ============================================

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
            "`num_cached_blocks = 2`; `num_new_blocks` decremented twice because both cached blocks are "
            "currently in `used_block_ids` (still held by seq 0) → only 1 new block to allocate."
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
            "`num_scheduled_tokens = 12 − 8 = 4`. The forward pass only needs to compute KV for the "
            "4 new tokens — the cached 8 tokens already have their K and V in physical blocks 0,1. "
            "This is the real win of prefix caching: across requests, common prefixes (system prompts, "
            "few-shot examples, chat history) cost zero recomputation."
        ),
        highlights=["sequences", "scheduler"],
    )

    tr.add(
        title="ModelRunner.run([seq 1], prefill=True) — chunked prefill on 4 tokens",
        pc={"code_pane_id": "engine", "line": 58},
        narration=(
            "Forward pass with 4 new tokens. The attention kernel queries the cached KV in blocks 0,1 too, "
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
            "Block 3 (= `[301..304]`) is now full → hash it (chained from block 1's hash) and add to the "
            "prefix cache. Future sequences starting `[101..108, 301..304]` will reuse all 3 blocks. "
            "Append 501."
        ),
        highlights=["block_pool", "prefix_cache", "sequences"],
    )

    # ============================================
    # ENGINE.STEP() #3 — decode phase
    # ============================================

    tr.add(
        title="engine.step() #3 — decode phase",
        pc={"code_pane_id": "engine", "line": 56},
        narration=(
            "No more waiting; the prefill loop is empty so the scheduler falls through to the "
            "**decode** loop: pop each running seq, ensure room for one more token via `may_append`, "
            "then forward-pass them all together in a single batched kernel call."
        ),
        highlights=["scheduler"],
    )

    # may_append seq0
    tr.bm.may_append(seq_a)
    seq_a.num_scheduled_tokens = 1
    seq_a.is_prefill = False
    tr.add(
        title="may_append(seq 0) — len=13, allocate block 4",
        pc={"code_pane_id": "block_manager", "line": 112},
        narration=(
            "`len(seq 0) = 13` (12 prompt + 1 sampled). `13 mod block_size = 1` → the new token lands in "
            "a new logical block. Allocate fresh physical block 4. `seq0.block_table = [0, 1, 2, 4]`. "
            "Flip `is_prefill = False` — from now on, seq 0 produces one token per step."
        ),
        highlights=["sequences", "block_pool"],
    )

    # may_append seq1
    tr.bm.may_append(seq_b)
    seq_b.num_scheduled_tokens = 1
    seq_b.is_prefill = False
    tr.add(
        title="may_append(seq 1) — len=13, allocate block 5",
        pc={"code_pane_id": "block_manager", "line": 112},
        narration=(
            "Same for seq 1: allocate fresh block 5. `seq1.block_table = [0, 1, 3, 5]`. "
            "Notice blocks 0 and 1 are still shared between seq 0 and seq 1 (`ref_count = 2`); "
            "blocks 2, 3, 4, 5 each have `ref_count = 1`."
        ),
        highlights=["sequences", "block_pool"],
    )

    tr.add(
        title="ModelRunner.run([seq 0, seq 1], prefill=False) — batched decode",
        pc={"code_pane_id": "engine", "line": 58},
        narration=(
            "**Continuous batching:** one forward pass produces one token per running sequence. "
            "Each sequence still attends to its OWN history via its OWN `block_table`, but the "
            "compute is fused into a single GPU kernel call. **Sampled: seq 0 → 402, seq 1 → 502.**"
        ),
        highlights=[],
    )

    # postprocess both — both finish (max_tokens=2 reached)
    for seq, tok in [(seq_a, SAMPLED[(0, "decode1")]), (seq_b, SAMPLED[(1, "decode1")])]:
        # hash_blocks: start = 12//4 = 3, end = (12+1)//4 = 3 → no-op
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
            "`deallocate` walks `block_table` in reverse, decrementing `ref_count`. Block 0 was shared "
            "(ref=2) — drops to 1 when seq 0 is deallocated (seq 1 still uses it), then 0 when seq 1 is "
            "deallocated, then it's pushed onto `free_block_ids`. **Crucially: the hash entries in the "
            "prefix cache STAY**. The blocks themselves go back to free, but their hashes still point at "
            "them — so the very next sequence with a matching prefix gets a cache hit without re-prefilling."
        ),
        highlights=["sequences", "block_pool", "prefix_cache"],
    )

    tr.add(
        title="generate() returns — both completions ready",
        pc={"code_pane_id": "engine", "line": 86},
        narration=(
            "`is_finished()` is True (waiting + running both empty). `generate()` collects the completion "
            "token_ids per seq_id, runs them through `tokenizer.decode`, and returns the text. Done."
        ),
        highlights=[],
    )

    # ---- Build the trace object ----
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
        "code_panes": code_panes,
        "steps": tr.steps,
    }


# ---------- Inject into template ----------

def main():
    here = Path(__file__).parent
    template = (here / "template.html").read_text()
    trace = build_trace()
    output = template.replace("/*TRACE_DATA_PLACEHOLDER*/", json.dumps(trace, ensure_ascii=False))
    out_path = here / "nano_vllm_trace.html"
    out_path.write_text(output)
    print(f"Wrote {out_path}")
    print(f"  {len(trace['steps'])} steps")
    print(f"  {len(output) // 1024} KB")


if __name__ == "__main__":
    main()
