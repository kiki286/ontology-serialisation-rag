import re
import os

# ---------------------------------------------------------
# Parse gold standard markdown
# ---------------------------------------------------------
def parse_gold_markdown(md_path):
    """
    Parses the gold questions markdown file and extracts:
    - question
    - answer
    - source
    - comment
    Returns a list of dicts.
    """

    if not os.path.exists(md_path):
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()

    # Each question block starts with "## Q" or "##  Q"
    blocks = re.split(r"\n##\s*Q\d+\s*\n", text)
    parsed = []

    for block in blocks[1:]:  # block[0] is header text before Q1
        q_match = re.search(r"### Question\s*(.*?)\n### Answer", block, re.S)
        a_match = re.search(r"### Answer\s*(.*?)\n### Source", block, re.S)
        s_match = re.search(r"### Source\s*(.*?)\n### Comment", block, re.S)
        c_match = re.search(r"### Comment\s*(.*)", block, re.S)

        question = q_match.group(1).strip() if q_match else ""
        answer = a_match.group(1).strip() if a_match else ""
        source = s_match.group(1).strip() if s_match else ""
        comment = c_match.group(1).strip() if c_match else ""

        parsed.append({
            "query": question,
            "gold_answer": answer,
            "gold_source": source,
            "gold_comment": comment
        })

    return parsed