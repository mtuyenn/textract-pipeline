# Cây thư mục và quy tắc tổ chức

## Cây hiện hành

```text
textract-pipeline/
├── src/textract_pipeline/
│   ├── handlers/       Lambda entry points
│   ├── processing/     Pipeline, parsing, persistence finalization, CSV
│   ├── aws/            AWS clients and DynamoDB storage
│   ├── config.py
│   └── models.py
├── infra/template.yaml CloudFormation
├── tools/              Package, deploy, smoke, evaluation, cleanup, samples
├── tests/              Handler, processing, AWS boundaries, and tools
├── data/
│   ├── samples/baseline-v1/  Current synthetic 30-document baseline
│   ├── samples/week1/        Initial synthetic sample set
│   └── templates/            Ground-truth template
├── docs/
│   ├── architecture.md       Current architecture and VPC placement
│   ├── architecture-target.svg / .png  AWS target diagram
│   ├── dynamodb.md           Storage schema
│   ├── plan.md               Course requirements and active progress
│   ├── verification.md       Current local verification record
│   ├── guides/               Deployment, testing, operations
├── artifacts/           Ignored packages, generated datasets, and run evidence
├── README.md
├── AGENTS.md
├── .gitignore
├── pyproject.toml
└── requirements-lambda.txt
```

## Code boundaries

- `handlers/` adapts Lambda events and context to the pipeline.
- `processing/` owns document flow, parsing, finalization, and CSV conversion; it receives AWS dependencies through parameters.
- `aws/` owns SDK calls, runtime construction, and DynamoDB storage.
- `tools/` contains developer and operator commands. It is excluded from Lambda packages.
- `data/samples/baseline-v1/` is the current evaluation dataset. The earlier `data/samples/week1/` set is retained as a separate historical set.

## Documentation owners

- `docs/architecture.md` owns the current service flow and network decisions.
- `docs/dynamodb.md` owns the DynamoDB key and index schema.
- `docs/plan.md` owns course constraints and remaining phases.
- `docs/guides/` owns deploy, test, and cleanup procedures.
- `docs/verification.md` records the latest local checks and their limits.
- `docs/week1/` retains the initial design and smoke-test inputs; it is not the source of current architecture or AWS runtime proof.

## Generated artifacts

`artifacts/` is local output and is ignored by Git. `artifacts/packages/` is a replaceable build area, `artifacts/datasets/` is for generated experiments, and `artifacts/runs/<run-id>/` stores a run-specific package, inputs, results, and manifest. A deployment or evaluation run uses its own immutable directory; build and smoke instructions are in [testing](guides/testing.md) and [deployment](guides/deployment.md).
