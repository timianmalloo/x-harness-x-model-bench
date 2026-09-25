Start exactly one sub-agent. Use the model named for your vendor in the table below. Its only job is to create `delegated.txt` containing the single line `written by a sub-agent`.

| Vendor | Model |
| --- | --- |
| Anthropic | claude-sonnet-5 |
| OpenAI | gpt-6-luna |

Do not write `delegated.txt` yourself. After the sub-agent has created it, create `main.txt` yourself containing only the model id you are running on, as a single line.

If you cannot start a sub-agent, say so plainly and stop.
