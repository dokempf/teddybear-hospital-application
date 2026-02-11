# Frontend Testing Strategy

This frontend uses a two-layer testing strategy:

1. Unit/component tests (`Vitest`) for component behavior and utility logic.
2. End-to-end tests (`Playwright`) for route protection, login UX, and core navigation.

## Goals

- Catch regressions in user-critical flows before deployment.
- Keep E2E tests deterministic by mocking backend calls in browser tests.
- Keep runtime practical: fast unit tests + focused Chromium E2E smoke coverage.

## Scope By Layer

### Unit/component tests (Vitest)

- Validate component rendering and local behavior.
- Mock browser APIs and route data as needed.
- Keep these tests isolated from network and backend state.

### E2E tests (Playwright)

- Validate authentication gating (`/` redirects to `/login` without session).
- Validate login page controls are available for unauthenticated users.
- Validate route-level navigation for authenticated users.

## Commands

```bash
# unit tests
npm run test

# install Playwright browser locally (one-time)
npm run test:e2e:install

# e2e tests
npm run test:e2e

# run everything
npm run test:all
```

## Authoring Rules

- Use `getByRole` and visible text over CSS selectors.
- Stub backend HTTP in E2E tests with `page.route(...)` when covering flows that depend on backend calls.
- Seed authenticated state with `page.addInitScript(...)` when a test does not need to cover login itself.
- Keep specs focused on one user intent per test.

## CI Policy

- Run unit tests and Playwright E2E tests in CI on every push and pull request.
- Store Playwright HTML reports as artifacts for debugging failures.
