"""Run Ollama classification against labeled JSONL and save scorecard."""
import argparse
import csv
import json
from pathlib import Path
from triage import classify

def metrics(rows):
    tp = sum(r["expected"] == "malicious" and r["predicted"] == "malicious" for r in rows)
    tn = sum(r["expected"] == "benign" and r["predicted"] == "benign" for r in rows)
    fp = sum(r["expected"] == "benign" and r["predicted"] == "malicious" for r in rows)
    fn = sum(r["expected"] == "malicious" and r["predicted"] == "benign" for r in rows)
    div = lambda a, b: round(a / b, 4) if b else 0.0
    precision, recall = div(tp, tp + fp), div(tp, tp + fn)
    return {"n": len(rows), "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "accuracy": div(tp + tn, len(rows)), "precision": precision,
            "recall": recall, "f1": div(2 * precision * recall, precision + recall)}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="data/synthetic_pilot.jsonl")
    p.add_argument("--output", default="results/predictions.csv")
    p.add_argument("--model", default="qwen3:4b")
    args = p.parse_args()
    rows = []
    for line in Path(args.input).read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        event = json.loads(line)
        if "id" not in event or event.get("label") not in ("malicious", "benign"):
            raise ValueError("Every alert needs an id and valid label")
        pred, latency = classify({k: v for k, v in event.items() if k != "label"}, model=args.model)
        rows.append({"id": event["id"], "expected": event["label"],
                     "predicted": pred["classification"], "confidence": pred["confidence"],
                     "attack_type": pred["attack_type"], "explanation": pred["explanation"],
                     "latency_seconds": latency})
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "expected", "predicted", "confidence",
                           "attack_type", "explanation", "latency_seconds"])
        writer.writeheader()
        writer.writerows(rows)
    summary = metrics(rows)
    (out.parent / "metrics.json").write_text(json.dumps({"model": args.model, "metrics": summary}, indent=2))
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
