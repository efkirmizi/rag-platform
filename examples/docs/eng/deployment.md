---
space: ENG
title: Deployment process
url: https://intranet.example.com/eng/deployment
---

## Deployment windows

Production deployments run on weekdays between 10:00 and 16:00. No deployments
on Friday afternoons or before public holidays. Every rollout is staged: 5% of
traffic first, 30 minutes of observation, then full rollout.

## Rollback

Every deployment must be revertible with a single command. The on-call engineer
decides on rollback without waiting for manager approval once the error-rate
threshold is exceeded.
