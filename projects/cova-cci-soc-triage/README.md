# COVA CCI — LLM-Assisted SOC/SIEM Triage

Research prototype for classifying labeled security events with local Ollama Qwen3:4b. This is a research experiment, not a production SOC tool.

## Run
Install Ollama and pull `qwen3:4b`. From this project folder:

```powershell
python -m unittest discover -s tests -v
python src/evaluate_alerts.py --input data/synthetic_pilot.jsonl
```

Requires Ollama at localhost:11434. Predictions are saved to results/predictions.csv and results/metrics.json. The bundled alerts are **synthetic demonstration events** and cannot establish real-world accuracy. Labels for future benchmark events must be independently validated. The CI workflow tests parsing and evaluation only; it does not run Ollama.

See the separately provided full ZIP for the expanded 20-event pilot and GitHub Actions workflow.
