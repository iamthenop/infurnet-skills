---
thread-id: "<workorder identifier>"
msg-type: tester-workorder
agent: "<drafting agent>"
metadata:
  pull-request: "<PR reference>"
  revision: "<commit SHA to validate>"
---

# Tester workorder — <title>

## Authorizing source

<Reference the issue, milestone, and applicable authority.>

## Objective

<Specify the claims or behaviour to validate.>

## Validation scope

### In scope

<Identify required validation targets and obligations.>

### Out of scope

<Identify exclusions.>

## Inputs

<Reference the implementation, applicable Builder reports,
specifications, test fixtures, and other required evidence.>

## Required contracts and constraints

<Identify governing contracts, established requirements,
and job-specific constraints.>

## Validation environment and surface

<Identify the required environment, permitted validation
surface, and relevant setup constraints.>

## Local experiment authorization

<Identify assignment-specific permissions or constraints
for disposable local experiments.>

## Remote communication authorization

<Identify any permitted communication on existing remote
threads, or None.>

## Completion criteria

<Specify the evidence required to establish the validation
results and account for unverified requirements.>

## Reporting additions

<Job-specific requirements beyond the Tester report contract,
or None.>

## Job-specific stop conditions

<Additional conditions, or None.>