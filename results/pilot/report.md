# Report: pilot

| Model | Passed | Time s | Input+output tokens | Runs w/ malformed calls | Rejected-by-policy runs | Timeouts/errors |
|---|---|---|---|---|---|---|
| qwen25coder | 0/5 | 12 (11-27) | 1,548 (1,392-1,746) | 4/5 | 0/5 | 0 |
| qwen3 | 0/4 | 155 (125-261) | 12,426 (4,380-21,812) | 1/4 | 2/4 | 0 |

| Task | qwen25coder | qwen3 |
|---|---|---|
| appcontext-lifetime | 0/1 | 0/0 |
| blueprint-empty-name | 0/1 | 0/1 |
| ipv6-partition | 0/1 | 0/1 |
| nested-blueprint-subdomain | 0/1 | 0/1 |
| server-name-routing | 0/1 | 0/1 |
