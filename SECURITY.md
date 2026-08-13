# Security policy

## Supported version

The current `main` branch is the supported 0.6 developer-preview line. It is
supported for trusted development, conformance, and local experiments. No
claim is made that the project is ready for unsupervised high-risk,
multi-tenant, adversarial, or production execution. See `READINESS.md`.

## Reporting a vulnerability

Please use GitHub's private **Security → Report a vulnerability** workflow for
this repository. Do not place exploit details, credentials, private data, or
active-system information in a public issue.

Include:

- the affected version or commit;
- the node, driver, schema, viewer, or policy surface involved;
- reproduction steps using non-sensitive fixtures;
- the expected and observed authority, permission, or effect boundary;
- potential impact and any known mitigation.

## Security model

Node manifests declare permissions, effects, dependencies, runtime, and
resource requirements. Those declarations support policy decisions but do not
replace sandboxing, authentication, authorization, secret management,
independent verification, or operator review.

Generated nodes and new versions should begin quarantined. They must not be
admitted solely because they compile or receive a high optimizer score.
Candidate code must never write its evaluator. Candidate-visible "hidden"
tests are not hidden, and read-only mounting prevents modification rather than
inspection. Use separate trust domains when evaluator confidentiality matters.

`solutiongraph.executor.PythonRuntime` imports and invokes code in the current
Python process. Its policy checks prevent undeclared plans from starting but do
not contain malicious or compromised code. Use it only for trusted local
fixtures.

`solutiongraph.subprocess_runtime.SubprocessPythonRuntime` uses a fresh child,
a strict JSON/bytes wire format, a wall-clock timeout, a reduced environment,
and optional POSIX CPU/address-space limits. It records its adapter and
isolation identity in receipts and permits `allow_in_process_python=False`.
This is process lifecycle isolation, not an enforcement boundary for
filesystem, network, devices, secrets, system calls, or the current user's
operating-system authority.

A production harness must register an enforcing container, microVM, Wasm,
remote-job, or equivalent adapter; isolate filesystem, network, devices,
secrets, and resources outside the node; and set `allow_in_process_python=False`.

A subprocess or plain container is useful for lifecycle and dependency
isolation but is not, by itself, an adversarial security boundary.
`EvaluationBoundary` requires microVM or remote isolation for candidates
explicitly classified as untrusted; the harness must actually enforce the
declared stronger boundary.

Artifact and receipt content may contain sensitive task data. The bundled file
store provides content identity and atomic writes, not encryption, tenancy,
access control, retention enforcement, malware scanning, or secure deletion.
The JSONL receipt journal adds fsync-backed append, duplicate protection, and a
tamper-evident hash chain. A user with write access can still replace or delete
the entire file; use an authenticated append-only service or WORM storage when
that threat matters.
