from pathlib import Path
from dotenv import load_dotenv
import os

SRC_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = SRC_DIR / ".env"

# ----------------------------------------------------------
# Load environment variables (OpenAI keys, etc)
# ----------------------------------------------------------
load_dotenv(dotenv_path=ENV_PATH)

import csv
import re
import os
import asyncio
import pandas as pd


from app.rag_chain import build_rag_chain
from eval.read_cqas import parse_gold_markdown
from eval.eval import (
    measure_answer_relevancy,
    measure_answer_accuracy,
    measure_semantic_similarity,
)


# ----------------------------------------------------------
# Paths
# ----------------------------------------------------------

RAG_DIR = Path(__file__).resolve().parent.parent
MARKDOWN_PATH = RAG_DIR / "eval" / "gold_questions_answers" / "cqas.md"
RESULTS_DIR = RAG_DIR / "eval" / "results"

def get_next_trial_dir():
    """
    Scan the results folder for trial-X directories and return
    the Path to the next available trial directory (e.g., trial-3).
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    trial_dirs = []

    for d in RESULTS_DIR.iterdir():
        if d.is_dir():
            m = re.match(r"trial-(\d+)$", d.name)
            if m:
                trial_dirs.append(int(m.group(1)))

    next_trial_num = (max(trial_dirs) + 1) if trial_dirs else 1

    next_trial_dir = RESULTS_DIR / f"trial-{next_trial_num}"
    next_trial_dir.mkdir(parents=True, exist_ok=True)

    return next_trial_dir


# --------------------------------------------------------
# Create next trial directory automatically
# --------------------------------------------------------
TRIAL_DIR = get_next_trial_dir()

RAW_RESULTS_CSV = TRIAL_DIR / "results_raw.csv"
FINAL_EVAL_CSV = TRIAL_DIR / "results_scored.csv"

print(f"Using trial directory: {TRIAL_DIR}")
print(f"RAW_RESULTS_CSV:      {RAW_RESULTS_CSV}")
print(f"FINAL_EVAL_CSV:       {FINAL_EVAL_CSV}")





# ----------------------------------------------------------
# PART 1 — Run RAG pipeline + produce raw CSV
# ----------------------------------------------------------
def run_rag_tests():
    print("\n==========================")
    print(" Running RAG Evaluations")
    print("==========================\n")

    gold_tests = parse_gold_markdown(MARKDOWN_PATH)

    results = []

    for item in gold_tests:
        query = item["query"]
        print(f"→ Processing: {query}")

        try:
            # Build a fresh chain per query so conversation memory is not reused
            qa_chain = build_rag_chain()
            result = qa_chain.invoke({"question": query})

            answer = result.get("answer", "")
            context = result.get("context", "")

            results.append({
                "query": query,
                "actual_answer": answer,
                "actual_context": context,
                "gold_answer": item["gold_answer"],
                "gold_source": item["gold_source"],
                "gold_comment": item["gold_comment"],
            })

        except Exception as e:
            print("ERROR:", e)
            results.append({
                "query": query,
                "actual_answer": f"ERROR: {e}",
                "actual_context": "",
                "gold_answer": item["gold_answer"],
                "gold_source": item["gold_source"],
                "gold_comment": item["gold_comment"],
            })

    # Write raw CSV (before scoring)
    RAW_RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)

    with open(RAW_RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "query",
            "actual_answer",
            "actual_context",
            "gold_answer",
            "gold_source",
            "gold_comment",
        ])
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✔ Raw results written to: {RAW_RESULTS_CSV}")


# ----------------------------------------------------------
# PART 2 — Score answers (relevancy, accuracy, similarity)
# ----------------------------------------------------------
async def run_scoring():
    print("\n==========================")
    print(" Scoring RAG Outputs")
    print("==========================\n")

    df = pd.read_csv(RAW_RESULTS_CSV)

    rows = []

    for idx, row in df.iterrows():
        query = row["query"]
        response = row["actual_answer"]
        reference = row["gold_answer"]

        print(f"\n--- Row {idx} ---")
        print(f"Query: {query}")
        print(f"Response: {response}")
        print(f"Reference: {reference}")

        # LLM-based scoring functions
        relevancy = await measure_answer_relevancy(query, response)
        accuracy = await measure_answer_accuracy(query, response, reference)
        similarity = await measure_semantic_similarity(reference, response)

        print("Relevancy:", relevancy.value)
        print("Accuracy:", accuracy.value)
        print("Semantic Similarity:", similarity.value)

        rows.append({
            "query": query,
            "actual_answer": response,
            "gold_answer": reference,
            "answer_relevancy": relevancy.value,
            "answer_accuracy": accuracy.value,
            "semantic_similarity": similarity.value,
        })

    result_df = pd.DataFrame(rows)

    FINAL_EVAL_CSV.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(FINAL_EVAL_CSV, index=False)

    print(f"\n✔ Final scored results written to: {FINAL_EVAL_CSV}")

    # ----------------------------------------------------------
    # PART 3 — Print summary stats
    # ----------------------------------------------------------
    print("\n==========================")
    print(" Metrics Summary")
    print("==========================\n")

    metrics = [
        "answer_relevancy",
        "answer_accuracy",
        "semantic_similarity",
    ]

    for metric in metrics:
        series = result_df[metric].astype(float)

        print(f"{metric}:")
        print(f"  mean:   {series.mean():.4f}")
        print(f"  median: {series.median():.4f}")
        print(f"  std:    {series.std():.4f}")
        print(f"  min:    {series.min():.4f}")
        print(f"  max:    {series.max():.4f}")
        print("")



# ----------------------------------------------------------
# MAIN ENTRY POINT
# ----------------------------------------------------------
if __name__ == "__main__":
    run_rag_tests()                # Part 1
    #asyncio.run(run_scoring())     # Part 2
