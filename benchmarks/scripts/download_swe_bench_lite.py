from datasets import load_dataset
import json

ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")

with open("swe_bench_vllm.jsonl", "w") as f:
  for row in ds:
      prompt = f"Repo: {row['repo']}\n\nProblem:\n{row['problem_statement']}\n\nCode Context:\n{row['hints_text']}\n\nPlease generate the patch to fix this issue:\n"
      f.write(json.dumps({"prompt":prompt}) + "\n")
