"""Run the CodeMind agent on every question in the eval set and save the answers.

Usage (from the repo root, after `codemind build`):
    python eval/run_eval.py --tag v0-baseline
    python eval/run_eval.py --tag v1-qualified-names --db ./codemind_data

Outputs:
    eval/results/<tag>.jsonl        every answer plus the agent's tool calls
    eval/results/<tag>_grading.csv  open in Excel and fill in the score column
                                    (1 = correct, 0.5 = partly correct, 0 = wrong)
"""
import argparse
import csv
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from codemind.agent import CodeAgent
from codemind.graph_builder import GraphBuilder
from codemind.retriever import CodeRetriever

EVAL_DIR = Path(__file__).parent


def load_questions(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_one(agent, question):
    """Ask one question and record every tool call the agent makes."""
    trace = []
    original_call_tool = agent._call_tool

    def traced_call_tool(action, action_input):
        output = original_call_tool(action, action_input)
        trace.append({"action": action, "input": action_input, "output": output[:500]})
        return output

    agent._call_tool = traced_call_tool
    start = time.time()
    try:
        answer = agent.run(question)
    except Exception as e:  # keep going so one failure doesn't kill the run
        answer = f"ERROR: {type(e).__name__}: {e}"
    finally:
        agent._call_tool = original_call_tool
    return answer, trace, round(time.time() - start, 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True, help="name of this run, e.g. v0-baseline")
    parser.add_argument("--db", default="./codemind_data", help="index folder built by `codemind build`")
    parser.add_argument("--questions", default=str(EVAL_DIR / "questions.jsonl"))
    args = parser.parse_args()

    load_dotenv()
    graph = GraphBuilder()
    graph.load_graph(os.path.join(args.db, "graph.json"))
    retriever = CodeRetriever(db_path=os.path.join(args.db, "chroma"))
    agent = CodeAgent(graph, retriever)

    questions = load_questions(args.questions)
    out_dir = EVAL_DIR / "results"
    out_dir.mkdir(exist_ok=True)
    jsonl_path = out_dir / f"{args.tag}.jsonl"
    csv_path = out_dir / f"{args.tag}_grading.csv"

    records = []
    with open(jsonl_path, "w", encoding="utf-8") as jf:
        for i, q in enumerate(questions, 1):
            print(f"[{i}/{len(questions)}] {q['id']}: {q['question']}")
            answer, trace, seconds = run_one(agent, q["question"])
            record = {**q, "model": os.getenv("OPENAI_MODEL"), "answer": answer,
                      "tool_calls": trace, "seconds": seconds}
            records.append(record)
            jf.write(json.dumps(record, ensure_ascii=False) + "\n")
            jf.flush()  # progress is saved even if the run stops halfway

    # utf-8-sig so that Excel opens the file with the right encoding
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as cf:
        writer = csv.writer(cf)
        writer.writerow(["id", "type", "question", "gold", "answer", "n_tool_calls", "score"])
        for r in records:
            writer.writerow([r["id"], r["type"], r["question"], r["gold"],
                             r["answer"], len(r["tool_calls"]), ""])

    print(f"\nSaved {len(records)} answers to {jsonl_path}")
    print(f"Now grade them in {csv_path}")


if __name__ == "__main__":
    main()
