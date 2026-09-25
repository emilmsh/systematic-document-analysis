# A controlled for-loop over files

The core applies one agreed task independently to each selected file through a CLI or API worker:

```text
Agree task, files, reader and result variables
For each file:
    Create a fresh worker context
    Execute the same task with the chosen CLI/API
    Record the result or error
Collect results into a dataset and relevant auxiliary sheets
```

One main row means one run. Objects become columns; repeated collections become linked detail sheets. Failed or rejected results retain their row, with empty variables and separate diagnostic information. The default is readable without presentation instructions; users can choose variables, labels and alternative layouts.

The task is flexible. A small envelope carries its result, reported source-unit coverage and limitations. No classification taxonomy, automatic quotation-extraction stage or per-file synthesis method is imposed. CLI workers can use file tools; APIs receive a bounded input. Oversized input fails explicitly when it cannot be handled within the chosen mode.

The queue retains task versions, immutable attempts, source hashes, exact inputs, raw responses, errors and actual reviews. A new adapter and fresh CLI session/API request are created for every iteration. Iterations may run concurrently up to the plan's agreed ceiling; each keeps its own context. Another file's answers are never passed to the worker. Context isolation is tested; CLI permissions are not full OS-level filesystem isolation.

There is one public MCP interface and one task/validation/export path. This development refactor deliberately removes criteria-based plans, their exporters and Norwegian MCP aliases; it provides no legacy reader or migration layer. Existing exported files are not modified. Use a fresh analysis store when testing the new task model against plan records from v0.9.0 or earlier.

Implementation: `task_contract.py` defines the task, `execution.py` prepares one call, `kjoring.py` runs the queue, and `task_dataset.py`/`task_workbook.py`/`task_export.py` present results. The host skill describes the workflow; tool descriptions only describe their operation.
