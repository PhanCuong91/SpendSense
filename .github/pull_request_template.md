## Summary

<!-- What does this PR do? Why is it needed? -->

---

## Type of Change

- [ ] Bug fix
- [ ] New feature / enhancement
- [ ] Refactor (no behavior change)
- [ ] Documentation update
- [ ] CI/CD / infrastructure change
- [ ] Dependency update

---

## Changes

<!-- List the key changes made -->

-
-

---

## Testing

- [ ] Tests pass locally (`make test`)
- [ ] New tests added for new behavior
- [ ] Tested `poller_worker` locally (if modified)
- [ ] Tested `misa.runner` locally with `--dry-run` (if modified)

---

## Environment / Config Changes

- [ ] No new environment variables added
- [ ] New env vars documented in `docs/CONFIGURATION.md`
- [ ] `.env.example` updated (if applicable)

---

## CI/CD Instructions

> Apply one of the following labels to trigger the pipeline:

| Label | Action |
|-------|--------|
| `check` | Run tests only (no merge) |
| `merge` | Run tests → auto-merge → deploy to AWS |

> ⚠️ Only apply `merge` when you are confident this is ready for production.

---

## Checklist

- [ ] Code follows project style (`make lint`, `make fmt`)
- [ ] No secrets or credentials committed
- [ ] `docs/` updated if behavior changed
- [ ] PR title is clear and descriptive
