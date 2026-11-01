"""Run inside the Langflow container; all cases call the real Ollama judge."""
import json
import time
from pathlib import Path
from guarded_ollama import GuardedOllama


def main():
    root = Path(__file__).resolve().parent
    cases = json.loads((root / 'test_cases.json').read_text(encoding='utf-8-sig'))
    results = []
    for stage, rows in cases.items():
        for index, row in enumerate(rows):
            guard = GuardedOllama()
            guard._guard_usage = {'input_tokens': 0, 'output_tokens': 0}
            started = time.monotonic()
            try:
                actual = guard.judge(stage, guard.normalize(row['text']), row.get('answer'))
            except Exception as exc:
                actual = {'decision': 'error', 'reason': type(exc).__name__}
            result = {'stage': stage, 'index': index, **row, 'actual': actual,
                      'pass': actual == {'decision': row['decision'], 'reason': row['reason']},
                      'seconds': round(time.monotonic() - started, 2)}
            results.append(result)
            (root / 'judge-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
            print(json.dumps(result, ensure_ascii=False), flush=True)
    passed = sum(r['pass'] for r in results)
    print(f'Passed {passed}/{len(results)}', flush=True)
    return 0 if passed == len(results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
