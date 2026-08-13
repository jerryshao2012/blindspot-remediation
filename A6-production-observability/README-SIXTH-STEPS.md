# Component 6 — Production Operational Observability

## 1. Why this component exists

Components 1–5 answer:

> Can we safely automate engineering work?

Component 6 answers:

> What does the resulting software actually do after deployment?

Those questions must remain separate.

---

# 2. The measurement stack

Our measurement architecture is now:

```text
LAYER 1
══════════════════════════

EVALUATION

Did the change satisfy the engineering requirements?

Examples:

tests
mutation analysis
static analysis
semantic evidence
release gate
pipeline benchmark


             │
             ▼


LAYER 2
══════════════════════════

OPERATIONAL MEASUREMENT

What happened when the released software actually ran?

Examples:

availability
error rate
latency
timeouts
dependency failures
retries
resource consumption
process completion


             │
             ▼


LAYER 3
══════════════════════════

BUSINESS MEASUREMENT

What happened to the business process?

Examples:

mortgage processing time
straight-through-processing rate
manual intervention
customer abandonment
operating cost
revenue
loss
This remains a useful conceptual model.
However, there is an important refinement.
There should not be an implied causal equality:
Eval improvement
      =
Operational improvement
      =
Business improvement
Instead:
Eval evidence
      │
      ▼
Deployment
      │
      ▼
Operational observations
      │
      ▼
Process observations
      │
      ▼
Business outcomes
Each arrow requires evidence.
