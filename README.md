- [Project Summary](#project-summary)
- [Deployment](#deployment)
- [Versioning](#versioning)
- [Development](#development)
  - [Configure Environment](#configure-environment)
    - [Dependencies](#dependencies)
    - [Project Settings](#project-settings)
      - [Environment Variables, Secrets, and Parameters](#environment-variables-secrets-and-parameters)
  - [Scripts](#scripts)
    - [Testing](#testing)
- [Service Documentation](#service-documentation)

# Project Summary

:warning: **DESCRIBE WHAT THE PROJECT DOES HERE**

# Deployment

This project deploys to the following environments:

- `feature` (_optional_)
  - **description**: this is a transient environment used when multiple people work
    on a project concurrently and need to test their changes in isolation.
    Unlike others, this environment is automatically destroyed after merge to the
    `development` branch.
    In regular development process (solo dev), this environment is not used.
  - **when**: on pull request from the `feature` branch to the `development` branch
- `development`
  - **description**: rapid development iteration, deploys multiple times a day
  - **when**: on push to the `development` branch
- `staging`
  - **when**: on push to the `staging` branch
  - **prerequisites**: the `development` environment must be deployed and the project
    must be ready for UAT
- `production`
  - **when**: new release is created on the `main` branch
  - **prerequisites**: project must be fully tested by the development team and client
    in the staging environment, all parties must be ready for the project going live
    in production

> :warning: Secrets used in this project are stored in AWS Secrets Manager.
> Make sure to update them for each deployment environment so that functions
> have access to correct parameters and secrets. Secrets are created automatically only
> **after deployment**.

Before deploying the project for the first time, you need to bootstrap the AWS CDK in
the AWS account you are deploying to. First, create the following IAM resources:

- `salesforce-integration-cdk-bootstrap-boundary-policy` policy with contents of
  `cdk-bootstrap-boundary-policy.json`. This policy will be used to limit what
  permissions will be available to CDK when deploying the project.
- `salesforce-integration-cdk-deployment-policy` policy with contents of
  `cdk-deployment-policy.json`. This policy allows the deployment user (GitHub Actions)
  to assume roles created when bootstrapping the CDK.

Then, as administrator (you can do this in the cloud shell), run the following command against your AWS account:

```sh
cdk bootstrap aws://123456789012/us-west-2 \
  --custom-permissions-boundary salesforce-integration-cdk-bootstrap-boundary-policy \
  --qualifier 61c44a6a3 \
  --toolkit-stack-name salesforce-integration-61c44a6a3-cdk-toolkit
```

> :warning: The `bootstrap` command should be executed in a different directory other
> than the root of the project. This is because the AWS CDK, when executed from project
> root, tries to synthesize the current project and it fails because we haven't
> built it yet. AWS CDK doesn't allow to bootstrap environment without synthesizing
> a project in the current directory which is a weird "feature" :clown_face:.

In AWS create an IAM Identity Provider for GitHub Actions if it does not exist yet:

- Choose `OpenID Connect`
- For provider URL use `https://token.actions.githubusercontent.com`
- For audience use `sts.amazonaws.com`

Create role`salesforce-integration-deployment-role` with the
`salesforce-integration-cdk-deployment-policy` policy attached. This role will be
used by CI (GitHub Actions) to deploy the project to AWS. Create role as `Web identity`
and select identify provider and audience created earlier. When prompted, provide
GitHub organization and repository.

Add the following variables to your repository (use environment variables if you use
different AWS accounts for development and production):

- `AWS_REGION` - set it to `us-west-2`
- `AWS_ACCOUNT_ID` - set it to `123456789012`

# Versioning

This project uses the Semantic Versioning system to keep track of its versions. A new
version is created when a new release is created on the `main` branch. In GitHub terms
a release is a tag on a branch. Files for each distinct version can be downloaded
from the relases section of the GitHub repository. Specific version can be triggered
to be deployed to the production environment by manually launching the
`deploy-production` workflow on GitHub Actions for the corresponding release tag.

When incrementing version, update the version in the following files:

- `pyproject.toml`
- `integration/config/project_settings.py`

# Development

Development process: `feature` (_optional_) > `development` > `staging` > `main`

Name the `feature` branch as `<your-name>/<feature-name>`, e.g. `george/ftp-reader`.
Open a Pull Request from `feature` to `development`, have it reviewed and approved,
then squash and merge. This should result in the service being deployed
to the `development` environment.

Once the service is ready for UAT (pre-production testing by client), open a PR to
`staging`, and merge it. This will trigger deployment to the `staging` environment.
Once UAT is over, open a PR from `staging` to `main`, get it reviewed/approved,
and merge. Once ready for production deployment, create a new release
(use GitHub UI for that, this creates a new tag) and publish it.
The service should be automatically deployed to the `production` environment.

## Configure Environment

If you are using VSCode and have Docker installed, you can use the provided
`devcontainer.json` file to create a development environment with all dependencies
installed and configured. To do that, open the project in VSCode and run the
"Reopen in Container" command from the Command Palette (`Ctrl+Shift+P`).
The `Dev Containers` extension must be installed in VSCode for this to work.

### Dependencies

Install project and its dependencies:

```sh
poetry install
```

> This project uses [poetry](https://python-poetry.org/) to manage python dependencies.
> By default, `poetry` creates virtual environment when you run the command above.
> To run python commands such as `python <script.py>` you need to run
> `poetry run python <script.py>`.

Optionally, install pre-commit hooks to make sure all changes are quality-controlled
before committing:

```sh
poetry run pre-commit install
```

Whenever you commit make sure to do it via the terminal to have `pre-commit` run
properly. Commits done through desktop clients (VSCode, GitHub Desktop, etc.)
may fail.

### Project Settings

Project settings are managed via the `integration/config/project_settings.py`
module. Settings are loaded from sources such as environment variables, `.env` files
(only use this when developing locally), AWS Secrets Manager, AWS Parameter Store, etc.
and are available as attributes of the `settings` object
(singleton instantiated on import):

```python
from integration.config import settings

print(settings.ENVIRONMENT)
```

When developing locally, it is often convenient to use `.env` files instead of
environment variablse to provide settings to the integration. To do that, you can create
`.env` files in the following directories (you can create both, files are parsed
in the order listed):

- project root (where `pyproject.toml` is located)
- `integration/config` (where `project_settings.py` is located)

`.env` file format:

```env
ENVIRONMENT="development"
AWS_REGION="us-west-2"
SENTRY_DSN=""
```

If you have AWS CLI installed and configured, other settings will be loaded from
AWS Secrets Manager and AWS Parameter Store automatically during runtime.

#### Environment Variables, Secrets, and Parameters

Environment in execution environment:

- `ENVIRONMENT` - one of `testing`, `development`, `staging`, `production`
- `AWS_REGION` - AWS region where the project is deployed (e.g. `us-west-2`)
- `AWS_RESOURCE_SUFFIX` - suffix to be added to all AWS resources created by this
  project (typically, same as `ENVIRONMENT`)

Secrets stored in AWS Secrets Manager:

- TODO

Parameters stored in AWS Parameter Store:

- TODO

## Scripts

> :warning: Make sure your python environment is activated when you run the following
> in your terminal

### Testing

```sh
scripts/test.sh
```

# Service Documentation
