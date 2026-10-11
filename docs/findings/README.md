# Findings

Analysis writeups produced from the frozen run outputs in
`src/rag/experiment/results/`. Each file states its date, its exact inputs, and its
API cost (analysis is offline; zero-spend unless stated). Start with
`60task-analysis.md`.

| File | Question it answers |
|---|---|
| `60task-analysis.md` | **The main analysis.** What did the full 60-item x 7-format x 2-condition x 4-arm run show for RQ1 (retrieval) and RQ2 (answer quality)? |
| `oracle-undetermined-degeneracy.md` | Why do the GPT arms answer `undetermined` so often under the oracle condition - is it non-entailment or non-retrieval? (Determination: all four degeneracy hypotheses rejected) |
| `functional-property-stratum.md` | Is the functional-property stratum viable - can its items be entailment-checked against the canonical Turtle? (Verdict: viable) |
| `pre-run-checklist.md` | Did the B1-B8 pre-run gates pass before the full 60-item run was launched (go/no-go record)? |
| `oracle-undetermined-degeneracy/` | Evidence directory for the degeneracy determination: the probe CSVs and dumps its writeup cites. Do not edit. |
