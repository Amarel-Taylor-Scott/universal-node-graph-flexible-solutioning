# Security policy

## Supported version

The current `main` branch is the supported proof-of-concept version. No claim
is made that the project is ready for unsupervised high-risk or production
execution.

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
