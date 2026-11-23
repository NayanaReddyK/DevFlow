# Workflow Intelligence Evaluation

Run:
`.\venv\Scripts\python.exe -m pytest backend\tasks\tests.py -k scenario_`

Result: 5/5 seeded scenarios passed.

| Scenario | Expected result | Outcome |
|---|---|---|
| Project has no issues | Healthy; zero tasks and bottlenecks; no recommendations | Pass |
| One task blocks six others | Bottleneck impact is 6; project Needs Attention | Pass |
| Two overdue High/Critical tasks | At Risk; evidence includes both task IDs | Pass |
| Task blocked for over five days | Stale-blocker finding; Needs Attention | Pass |
| Critical path has three tasks and target is one day away | At Risk; evidence shows path length 3 and one day remaining | Pass |

## Limits

These are five hand-authored test scenarios. They check that selected expected outcomes occur; they do not measure general detector accuracy or establish false-positive and false-negative rates. No 500-task latency measurement has been run.