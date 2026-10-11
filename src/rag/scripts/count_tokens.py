#!/usr/bin/env python3

import tiktoken
import sys

def count_tokens(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    enc = tiktoken.get_encoding("cl100k_base")  # GPT-4/3.5 style tokenizer
    tokens = enc.encode(text)
    return len(tokens)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python count_tokens.py <file>")
        sys.exit(1)

    file_path = sys.argv[1]
    print(f"Tokens: {count_tokens(file_path)}")
