---
date: 2026-10-19
categories:
  - crossdomain
---

# Does locality do what types do? A week with Forth

Forth's compiler checks almost nothing, and Chuck Moore's answer is to keep every word tiny and every obligation local. We asked how far that reaches, with LLM readers on 160 small words shown four ways.

<!-- more -->

*Written for readers who program but don't know Forth. Every reader result below comes from an experiment whose
hypothesis and failure condition were registered before its data was collected, unless it is marked exploratory or
unregistered; the instrument and GreenArrays figures are tooling results, not registered ones. The experiments were
designed and run by an Anthropic model under the owner's direction, so the main readers were taken from other
vendors, GPT-5.6 Sol and Grok 4.7; the replication used Anthropic models (Sonnet 5.5 and Haiku 5.5), and the
explanations were graded by Opus 5.5 with Gemini 3.7 Flash as the agreement check. The registrations, materials,
reader responses and analysis code are in a repository that is not yet public; this post will link to them when it
is. Work on a stack-machine corpus that is not yet public is left out.*

## The question

Forth is a language whose compiler checks almost nothing. A word (Forth's name for a function) takes its arguments from
a stack and leaves its results there. Each word usually carries a **stack comment** saying how many it takes and leaves:
`( a b -- c )` takes two and leaves one. Nothing checks those comments before the program runs. If a word leaves one
value too many, the program computes the wrong thing, and many systems notice nothing until much later.

Chuck Moore, who invented Forth, never answered this with a type system. His answer, as this project read it from
his writings and the GreenArrays documents, is a discipline:
- keep every word tiny, a line or two;
- keep each obligation local, so a reader can see that a word is right by looking at that word alone;
- when something gets hard, shrink the problem instead of building machinery to manage it.

So the question here was concrete: **does Moore-style locality discharge the obligations a type system would?**

## The first answer is free, and narrows the question

Consider a modular checker, one that judges a definition using only that definition and its callees' declared stack
comments. It looks at exactly what locality says a reader should look at. So anything such a checker can catch is, in
principle, visible to a careful reader of the same lines. That much follows from the definitions, with no experiment.

What it leaves open are two empirical questions:
- **do readers actually catch** what a checker catches;
- **are there obligations no local view can discharge**, checked or not.

## Long Forth is not long stack code

The first plan was to ask whether defects hide better in long definitions than in short ones. It ran into the corpus
before any reader was involved. In Gforth and Open Firmware there are 4,071 definitions of 32 tokens (words and
numbers in the source) or more. Only 10 are plain run-time stack code with a usable stack comment whose callees the
project's depth checker, which reads stack comments and follows calls, can resolve. The rest:
- contain strings or compile-time machinery (code that runs while the program is being compiled);
- have no usable comment;
- or call words outside that checker's table, including standard ones like `pick` and `case`.

That registered experiment (L1) stopped at its own materials check.

## LLM readers and stack shape

The second experiment (L2) took 398 real definitions from seven public Forth systems and made three versions of each:
- one with a seeded **shape** defect, which changes how many values are on the stack (an extra `dup`, which copies the
  top value, or a missing `drop`, which discards one);
- one with a seeded **value** defect, where the count is right but a value is wrong (an operator or a literal swapped
  for another with the same stack effect);
- one left clean.

Two LLM readers, GPT-5.6 Sol and Grok 4.7, looked for the defects, each in its own sandboxed session (a **seat**).
One seat's results are the usable ones: Grok used workspace tools on most of its items, and the registered rule
excluded those responses. On the GPT seat, shape defects were found 92–99% of the time at every length, from three
tokens to two hundred. In the longest group, 38 definitions, a third of the clean ones were also flagged, so part of
that group's 92% is general suspicion. The registered question was whether shape defects are missed more often in
longer words, and the registration said that if the shortest words were already found above 95% the comparison
could not be drawn. Pooled over both seats they were found 97.5% of the time, so the verdict is **NOT DRAWN** and
the shape result is descriptive, from one LLM seat.

Value defects were missed more often, and most often in the tiniest words: 72% found in 3–5-token definitions,
against about 84% in longer ones.

## Names and the callees' code both carry it

The third experiment (L3) asked why. From L2's pool it took every definition of 3–11 tokens that calls at least one
user-defined word, 312 of them, sampled 160 by a seeded shuffle, seeded one value defect in each, and showed each one
four ways. The names (the word's own and those of every
non-standard word it calls) were either the originals or replaced with `w1`, `w2`. Each callee was shown either by
its stack comment or by its full source. In 112 of the 160 definitions
the callees are only constants and variables, so their "full source" is a one-line declaration; in 48 the callee is a
word with a body.

| value defects found | callee's stack comment | callee's source |
|---|---|---|
| names replaced | 29% | 58% |
| original names | 71% | 86% |

The two seats were within seven points of each other in every cell, and both effects are large. Restoring the names
took detection from 29% to 71% (with stack comments). Showing the callee's source instead of its comment took it
from 29% to 58% (with neutral names). The two overlap: adding both gains to 29% would give 100%, and together they
reach 86%, so 14 points of the two gains are shared. A replication with two readers from the author's own model
family (Sonnet 5.5 and Haiku 5.5), weak evidence on its own for that reason and for a rule set late (see "what went
wrong"), found both effects again, somewhat smaller. A follow-up probe of those replication readers found they could
rebuild only 3 of the 160 definitions from the name and file alone. So for them the names effect is not name-to-code
recall. L3's original readers were not probed.

Pooled, the names helped more than the callees' source. But the pool is mostly words whose callees are data, and
there "source" means a declaring line. Split by what the callee is, the picture changes (both seats within four points
of each other; 48 words is a small set, and this split was not registered):

| value defects found | callee's stack comment | callee's source |
|---|---|---|
| callee has a body (48 words), names replaced | 38% | 69% |
| callee has a body (48 words), original names | 56% | 92% |
| callees are constants and variables (112 words), names replaced | 26% | 54% |
| callees are constants and variables (112 words), original names | 77% | 84% |

Where the callees are constants and variables, the names did most of the work and the declaration added little once
the names were back; that ordering is clear. Where the callee has a body, showing the body helped more than restoring
the names (gains of about 31 and 35 points against 19 and 23), but with 48 words the difference between the two
gains is within noise: 0.55 on the log-odds scale (the scale the statistical model works on), standard error 0.38,
so the interval includes zero. So a registered follow-up took every remaining definition of up to 16 tokens that met L2's filters
and whose callee is a **colon word**, one defined with `:` and so having a body, in fifteen public corpora: 94 of
them (the 16-token cap was chosen after counting what the corpora held; 11 tokens gave 72 words, 16 gave 94). They
went to the same two readers the same four ways:

| value defects found, 94 fresh words whose callee has a body | callee's stack comment | callee's source |
|---|---|---|
| names replaced | 43% | 72% |
| original names | 70% | 90% |

There the two gains are about equal: body minus names 0.13 on the log-odds scale, standard error 0.21, interval
−0.28 to 0.54. The registered verdict is **INCONCLUSIVE**: the design could show a lead for one side, not equality,
and it showed neither, so a small lead either way is still open. Both main effects replicated on these items, the
names' somewhat smaller than in L3 (1.18 against 1.71 on that scale) and the body's about the same (1.31 against
1.15). What these words show is that the clear lead the names had where callees were data is absent once there is a
body to see; not that the body wins, and not that the names stopped helping.

Finding a defect is one use of a reader. The other is to ask it what a word does. Another registered run (L3-E)
took the same 160 words, unseeded, in the same four conditions, and asked the same two readers to explain what each
word is for; a third model graded every explanation against the original definition, its callees' source and the
lines around it in its file, and a fourth model regraded a sample of 128 (agreement 0.72 by Cohen's kappa, where 1
is perfect agreement and 0 is chance).

| explanation states the purpose correctly | callee's stack comment | callee's source |
|---|---|---|
| names replaced | 12% | 32% |
| original names | 61% | 72% |

The order is the one detection gave, and the names matter more here, partly by construction: the grader, an
Anthropic model that was not blind to the condition, reads the same name the explainer saw. In the 91 words whose
surrounding lines include a comment, which gives the grader something besides the name to judge purpose by, the
names effect is still there (14% → 66% with stack comments); in the 69 without, the name is most of what the grader
has. What detection did not show is in the errors, which are counts, not a registered test (the registered model on
false statements was not drawn: too few in the reference cell). With neutral names and stack comments the reader
mostly describes the mechanics and leaves the purpose alone; it asserts a false purpose 4% of the time (12 of 320
explanations), 1% with high confidence. Given the names or the body it commits, and is wrong 9 to 11% of the time
(28, 34 and 28 of 320), 5 to 6% with high confidence. So the aids that
make a reader more often right about a word make it more often confidently wrong about it. Confidence still carries
signal (high on 85% of correct explanations, 51% of wrong ones), which is why a tool can show it, and why it cannot
show it as a guarantee.

An earlier, exploratory number points the same way. In L2's shortest words, value defects were found 62% of the time
when the word called other user words, against 78% when it called only standard ones. A stack comment says how many
values a word takes and leaves, but nothing about what they mean. (In L3 every callee comment was either verified by
the checker against the callee's body or written by the experiment's own tooling for a constant or variable, so the
mismatches the next section counts in ordinary code do not touch these items.)

Where is the line between "inside the word" and "outside" it? A word's own name and its callees' names are part of
its text; the callees' bodies are not. Drawn there, the data say: **for these LLM readers, both aids helped and the
two overlapped; which carried more depended on the callee. When the callees were data, the names, which are in the
word's text, clearly carried more; when the callee was a word with a body, the body, which is outside the word, drew
level with them as far as 94 fresh words can tell (the two gains differed by 0.13 ± 0.21; which is larger is
open).** Neither
"meaning lives outside the word" nor "the names carry most of it" survives the split. Whether either aid was
necessary, and whether people read the same way, is untested.

## The instruments, briefly

The tooling built the materials and the GreenArrays models; the reader results do not depend on its agreement
figures, so this is short. The experiments needed a stack-depth checker that reads stack comments and an inference
that writes the comment a word's body implies; the project also built a model of what each source file defines and
loads, and a small Forth virtual machine that runs the systems' own test suites. The checker decides 11,996 of those
tests and agrees with 11,922; the 74 others trace to comment errors in a handful of test words, and where the
checker says a test's depths match, execution from a fresh system state never contradicts it. That is agreement
among instruments and suite authors, not evidence that comments in ordinary code are reliable: the suites are written
to pass, some checker rules were added after reading results, and the 730 comment/body mismatches the checker raised
on ordinary definitions (a later lexer fix removes 9) were only sampled. Inference did find one real stack slip, in an amforth driver: a store
where a fetch was meant, with a second error in the same word. The file had already left the project upstream. Two
tools came out of the same work, both private for now: a browser viewer that shows each Forth word with its callees'
source inline, infers missing stack comments and runs a project's tests; and a live editor for the GA144 port and
path models of the next section.

## Some obligations are not local at all

GreenArrays' GA144 is Moore's later chip: 144 small Forth computers on one die, each talking to its neighbours through
ports that block until the other side is ready. Its technology reference (the F18A datasheet, DB001 §3.3.1) gives a
rule for a node that waits on several ports with one read: "only one of the selected ports may be written by another
node at any given time."

That obligation does not belong to any one node's code. In GreenArrays' keyboard note (AN009), the two writers "act
totally independent from each other": one is paced by the keyboard, the other by the program consuming keystrokes. The
note says what breaking the rule does ("the behavior is undefined"), and gives the fix: "The only way to solve this is
to poll both sides continuously." The fixed design removes the cross-node obligation rather than discharging it: the
node checks which port is ready and reads one at a time, so there is no read on several ports for the rule to apply
to. That
is the discipline's own move, shrink the problem, and the note prices it: energy on polling, about half the buffer
(31 cells to 15), a reply to one neighbour that still waits for that neighbour, and a hope that a future chip would remove
the need.

A second note (AN011) gives a rule for messages routed across the grid: paths that "cross more than once" can deadlock.
Comparing that rule with an exhaustive search of how two paths can interleave shows two things.
- **For paths that meet only at single crossing points,** the rule never misses a deadlock, but it is cautious: about
  half the pairs it flags cannot actually deadlock.
- **It misses deadlocks where the paths share nodes in reversed order.** Read literally over random pairs that may
  share stretches, it misses most deadlocks (3,121 of 3,516), nearly all of them two paths sharing a stretch in
  opposite directions. That is not a crossing, but it can deadlock.

The exact condition still compares just the two paths, but it needs the order in which each path visits its nodes,
not only where they meet. One caveat on the modelled rule: it counts contacts along one path, so on about 1% of
pairs its verdict depends on which path is read first; counting along both paths removes that and still misses
3,076 of the 3,516, so the gap is the shared stretches, not the counting. These are hand models of two application
notes, with the orderings declared rather than derived; the
random-path comparison ran in software, and no GA144 code was run.

The synchronous languages offer a published version of the same trade (Halbwachs, *Synchronous Programming of
Reactive Systems*, 1993, §4.2.2 and §5.3–5.4). A clock, there, says at which instants a value
exists. Lustre requires every variable to be fully defined by its own equation, with nothing inferred from how it is
used. Its clock check is syntactic, because deciding whether two clocks are equal is impossible in general, so it
rejects some programs whose clocks could have been inferred. Signal infers clocks across the whole program, and in
return finds obligations nobody wrote down. In our reading of the book, Lustre's rule is what keeps its
checker modular.

These are two cases, not evidence that designers generally choose locality. In both, keeping checking local had an
explicit price.

## What it adds up to

Three answers, kept apart because they rest on different kinds of evidence.
- **By stipulation:** whatever a modular checker catches, a careful local reader could catch. That is a definition,
  not a finding.
- **Descriptively, for LLM readers:**
  - long definitions in these corpora are mostly not plain stack code (10 of 4,071), so the length question could
    only be asked of short ones;
  - stack shape was found at every length, though the registered test was not drawn;
  - value intent was harder, worst in the smallest words;
  - and it improved with the original names (29% → 71%), which are part of the word's text, and with the callees'
    source (29% → 58%), which is not; with both, 86%. Which helped more depended on the callee: clearly the names
    when the callees were constants and variables; when the callee was a word with a body, the two drew level (94
    fresh words, difference 0.13 ± 0.21);
  - and what the reader could tell a person followed the same order: a correct account of the word's purpose 12%
    of the time with neither aid and 72% with both, while false accounts rose from 4% to 9–11%, half of them given
    with high confidence.
- **In two hardware and language cases,** some obligations cross components and cannot be read off any one piece. The
  designs handled them by redesigning away or restricting the non-local part, and paid for it.

So for the part a type checker usually covers, locality is covered by definition, not by evidence: a careful local
reader could catch it, and whether readers do was not established (L2 was not drawn). For meaning, the evidence here
is four numbers and a split: in small Forth words whose stack effect does not depend on the data, two LLM readers
found seeded value defects in 29% of items with neutral names and callee stack comments, 71% with the original
names, 58% with the callees' source, and 86% with both; where a callee had a body, the names' clear lead over the
body was absent, and which gain is larger there is open. Whether either was necessary is untested. For obligations
that cross components, in both cases studied the obligation was handled by an ordering, a declaration, or a
redesign that removed it.

## How it was done, and what went wrong

Each experiment's hypothesis and failure condition were registered before its own data was collected. Later
registrations were written knowing earlier results, and say so. Corrections went into the registrations in marked
brackets, never by rewriting.

The mistakes were ours:
- three drafts of the first registration each had the expected outcome built in, one level deeper each time;
- in L2, one reader seat used workspace tools to search its sandbox on most of its items, so its responses were
  excluded;
- one agent tool's "read-only" mode turned out to execute shell commands, and only an OS sandbox actually enforced
  read-only;
- in the replication, the rule for dropping seats that refused too often was set after calibration had shown which
  seats would be dropped.

None of these was caught by rereading. Each was caught by a fresh reviewer, a deliberate failure test, or a second
instrument.

**Limits.**
- The readers were language models, not Forth programmers, and seeded defects (one operator or literal swapped,
  one `dup` or `drop` added or removed) are not real bugs. L2's shape result rests on one usable seat.
- The explanations were graded by a model of the author's family that saw the condition; a second model agreed
  with it on a sample of 128 (kappa 0.72), which bounds the dependence on the grader without removing it.
- The 48/112 split by callee kind was not registered; the 94-word follow-up that tested it was.
- The corpora are public. Recall was ruled out only for the replication's readers, and recognition while reading
  remains possible.
- The instruments were built here and validated against standard suites, not pre-registered; some checker rules
  were added after reading results.
- The GreenArrays results are hand models of two notes and the technology reference, and the Lustre/Signal
  contrast is our reading of one book.

A pass by human readers over a subset of the items is the one thing that would break the dependence on model readers.
It has not been done.

---

🦬☀️ *forth-floor: pre-registered experiments on locality in Forth, with a depth checker, stack-comment inference, a
small Forth VM, and GA144 port and path models. The repository is private until a related project is public; this
post will link to it then.*
