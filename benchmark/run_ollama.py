"""Send all prompts in results/prompts/ to a local Ollama model and save the answers.

    python3 benchmark/run_ollama.py [--max-tokens N] MODEL [MODEL ...]   e.g. llama3.2:3b qwen2.5:7b

--max-tokens limits the answer length (Ollama num_predict). Helps against endless loops of small
models; a truncated answer then counts as wrong.

First run: python benchmark/bench.py prompts (creates benchmark/results/prompts/).

Answers go to responses/<model>/<task>.md. Existing answers are skipped.
Standard library only, talks to http://localhost:11434.
"""
import json, pathlib, sys, time, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
URL = "http://localhost:11434/api/chat"

def ask(model: str, prompt: str, max_tokens: int | None = None) -> str:
    options = {"temperature": 0.2, "num_ctx": 8192}
    if max_tokens:
        options["num_predict"] = max_tokens
    body = json.dumps({"model": model, "stream": False, "options": options,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read())["message"]["content"]

def main() -> None:
    args = sys.argv[1:]
    max_tokens = None
    if args[:1] == ["--max-tokens"]:
        max_tokens, args = int(args[1]), args[2:]
    models = args or sys.exit(__doc__)
    prompts = sorted((HERE / "results" / "prompts").glob("*.md"))
    failed: list[str] = []
    for model in models:
        out = HERE / "responses" / model.replace(":", "_").replace("/", "_")
        out.mkdir(parents=True, exist_ok=True)
        for i, p in enumerate(prompts, 1):
            target = out / p.name
            if target.exists():
                continue
            t0 = time.time()
            try:
                answer = ask(model, p.read_text(encoding="utf-8"), max_tokens)
            except (OSError, TimeoutError) as exc:  # e.g. timeout: skip this task, carry on
                failed.append(f"{model}/{p.stem}")
                print(f"[{model}] {i}/{len(prompts)} {p.stem} FAILED: {exc}", flush=True)
                continue
            target.write_text(answer.strip() + "\n", encoding="utf-8")
            print(f"[{model}] {i}/{len(prompts)} {p.stem} ({time.time() - t0:.0f} s)", flush=True)
    if failed:
        print("No answer (running again retries them):", *failed, sep="\n  ")

if __name__ == "__main__":
    main()
