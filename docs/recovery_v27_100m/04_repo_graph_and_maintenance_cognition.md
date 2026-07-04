# Repo Graph And Maintenance Cognition Spine

The control spine was mostly solved before the repo graph branch.

The missing part was maintenance cognition:

```text
repo state understanding
symbol binding
edit localization
patch algebra
verifier-repair loop
```

## Repo State Graph

The model needs a `repo_state_graph_v1` substrate.

Objects:

```text
files
symbols
definitions
call_edges
import_edges
test_edges
config_files
entrypoints
allowed_external_repos
```

Graph anti-cheat rules:

```text
node IDs must be opaque
graph IDs must not encode labels
objective metadata stays outside model input
edge endpoints must resolve
authority remains closed
raw source/body/decoder/patch rows remain zero unless authorized
```

## Symbol Binding

Target transition:

```text
repo_state_graph_v1 packet
+ visible symbol/import/callsite/test/failure evidence
-> binding decision
```

Initial labels:

```text
BIND_CALL_TO_SYMBOL
BIND_IMPORT_TO_MODULE
BIND_TEST_TO_SYMBOL
BIND_FAILURE_TO_SYMBOL
RETRIEVE_MORE
ABSTAIN_UNBOUND
```

Shortcut gates:

```text
query_node_id alone must not solve target_node_id
node degree / edge type count alone must not solve binding_action
target node IDs must exist or be null
endpoint failures == 0
label leak rows == 0
split overlap == 0
```

## Edit Localization

Maintainers must know where to edit.

Transition:

```text
intent + repo graph + failure/evidence
-> target file
-> target symbol
-> target edit region
-> test target
```

Fields:

```text
target_file_policy
target_symbol_policy
edit_region_policy
test_target_policy
```

## Patch Operator Algebra

Do not jump directly to raw code.

Predict edit operators first:

```text
INSERT_FUNCTION
REPLACE_EXPR
WRAP_CALL
ADD_IMPORT
CHANGE_CONDITION
ADD_TEST_CASE
UPDATE_CONFIG_FIELD
CREATE_FILE
```

Transition:

```text
intent/repo/evidence -> edit_operator + arguments
```

Then bounded decoder renders arguments/text.

## Verifier Repair

Verification should be learned as a transition, not just an external gate.

Fields:

```text
verification_command
expected_pass_condition
failure_type
repair_operator
rollback_or_continue
```

Episode schema:

```json
{
  "observe": "...",
  "orient": "...",
  "act": "...",
  "verify": "...",
  "failure": "...",
  "repair": "...",
  "final_state": "..."
}
```

## Software Maintainer Capability Ladder

The model understands maintenance when it can reliably predict:

```text
intent -> build strategy
repo graph -> relevant files/symbols
symbol use -> definition/import/test relation
failure log -> root cause class
root cause -> edit operator
edit operator -> bounded patch arguments
patch -> verifier expectation
verifier failure -> repair/abstain
```

The bounded decoder should only render after these state decisions are reliable.

