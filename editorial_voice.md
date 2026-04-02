# ModelMiser Blog — Editorial Voice

Inherits from mm-learn's Stevens/Ganssle standard, adapted for essays.

## The Standard

Write like W. Richard Stevens explaining a design decision to a capable
colleague over coffee, with Jack Ganssle's conversational warmth. The reader
is technical, curious, and has opinions of their own.

## Voice

- **Colleague to colleague** — you both know this matters
- **Direct and confident** — say what you mean
- **Opinionated where earned** — "This is the right tradeoff because..."
- **Dry wit when natural, never forced**
- **Every sentence pulls its weight**
- **Show the reasoning, not just the conclusion** — the interesting part is *how* you got there

## What a Blog Post Is (vs. a Tutorial)

A tutorial teaches a skill. A blog post shares an insight.

The reader arrives because the *title* promised something interesting — a
novel approach, a surprising constraint, a design decision that went against
convention. They stay because the *reasoning* is sound and the *writing*
respects their time.

**Structure:** Argument, not curriculum. A blog post has a thesis ("here's
what we found"), evidence ("here's why it works"), and implications ("here's
what it means"). It does not have learning objectives, exercises, or
checkpoints. If a post needs those, it should be a tutorial instead.

**Diagrams:** Mermaid diagrams earn their place by communicating something
that prose cannot — state machines, pipeline stages, data flow. One good
diagram per post is typical. Three means you're writing a tutorial.

**Code:** Assembly, Verilog, Rust snippets appear when they *are* the
argument — "look at this instruction sequence" or "this encoding encodes the
insight." Code is evidence, not curriculum. Annotate with brief inline
comments; don't walk through line by line.

**Length:** 1500-2500 words typical. Shorter if the insight is sharp. Longer
only if the reasoning chain genuinely requires it. The "interesting problem"
sections from the devlog are 100-200 words each; a blog post expands one of
those into a full argument with context and implications.

## What to Avoid

- Fabricated experience ("I once debugged...")
- Empty praise ("This elegant approach...")
- Weasel words ("It might be worth considering...")
- Padding. Ever.
- Explaining what's obvious to the target reader
- Glossing over what isn't obvious
- "In this post, I will..." introductions
- "In conclusion, we have shown..." summaries
- Bullet-point lists where prose would flow better
- Hedging on opinions the evidence supports

## What to Include

- The problem as it actually presented itself (not cleaned up)
- The wrong turns, if they're instructive
- The moment the insight clicked
- Enough context that someone outside the project can follow
- Concrete numbers (LUTs, cycles, bytes, latencies)
- What this connects to beyond the immediate project
- An honest assessment of what's still unknown

## The Devlog-to-Blog Pipeline

Each blog post originates from one or more DEVLOG "interesting problem"
sections. The devlog captures the raw reasoning; the blog post shapes it
into an argument a stranger can follow. The transformation:

- **Devlog:** "The spec-review caught X. The fix was Y. The lesson is Z."
- **Blog:** "Here's a class of bug that spec reviews catch and humans miss.
  Here's how auto-diverging branches create a specific instance. Here's what
  the fix tells us about CSR write semantics in general."

The blog adds context (what is SIMT, why does this matter) and removes
session artifacts (round numbers, commit references, skill names).
