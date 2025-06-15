#!/bin/bash

set -ex

poetry config virtualenvs.in-project true
poetry install
poetry run pre-commit install
printf "\nalias ll='ls -lahSr --color=auto'\n" >> ~/.bashrc
poetry run ruff check --select I,F401 --fix --exit-zero
poetry run ruff format
