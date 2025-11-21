# CI/CD Setup Guide

This guide explains the GitHub Actions CI workflow for the kg-forge project.

## Overview

The CI workflow automatically:
- Runs all unit tests on Python 3.12
- Generates code coverage reports
- Displays coverage in workflow logs
- Creates and commits a coverage badge to the repository
- Adds coverage summaries to pull requests
- Archives HTML coverage reports as artifacts

## How It Works

The workflow runs on every:
- Push to `main` or `develop` branches
- Pull request to `main` or `develop` branches

**No setup required!** The workflow works out of the box.

## Coverage Badge

The coverage badge is automatically:
1. Generated during the CI workflow
2. Saved to `.github/coverage.svg`
3. Committed back to the repository (on `main` branch only)
4. Displayed in the README

The commit message includes `[skip ci]` to prevent infinite loops.

### Updating the README Badge

Simply replace `YOUR_USERNAME/kg-forge` in the README with your actual repository path:

```markdown
[![CI](https://github.com/username/kg-forge/actions/workflows/ci.yml/badge.svg)](https://github.com/username/kg-forge/actions/workflows/ci.yml)
![Coverage](.github/coverage.svg)
```

## Coverage Reports

### Workflow Logs

Full coverage details appear in workflow logs under "Run tests with coverage":
- Overall coverage percentage  
- File-by-file breakdown
- Lines missing coverage

### Pull Request Comments

For PRs, an automatic comment shows:
- Coverage summary with metrics
- Coverage change compared to base branch
- Detailed file-by-file breakdown

### HTML Reports  

Downloadable HTML reports (30-day retention):
1. Go to Actions → Select workflow run
2. Scroll to "Artifacts"
3. Download "coverage-report"
4. Open `htmlcov/index.html` in browser

## Customization

### Coverage Thresholds

To fail the build if coverage drops below a threshold:

```yaml
pytest tests/ --cov=kg_forge --cov-fail-under=80
```

### Badge Colors

The `coverage-badge` tool automatically uses:
- 🟢 Green for coverage ≥ 80%
- 🟡 Yellow for coverage 60-79%
- 🔴 Red for coverage < 60%

## Troubleshooting

### Badge Not Showing

1. Ensure workflow has run at least once on `main`
2. Check that `.github/coverage.svg` exists in repository
3. Clear browser cache or try incognito mode
4. Verify the badge path in README matches the file location

### Badge Not Updating

1. Check workflow completed successfully on `main` branch
2. Look for the "Commit coverage badge" step in workflow logs
3. Verify `contents: write` permission is set in workflow

### Coverage Not in Logs

1. Ensure `pytest-cov` and `coverage-badge` are installed
2. Check `--cov=kg_forge` matches your package name
3. Verify tests are being collected and run

## Workflow Permissions

The workflow requires:
- `contents: write` - To commit the coverage badge
- `pull-requests: write` - To post coverage comments on PRs

These are already configured in the workflow file.

## Maintenance

- Badge updates automatically on each `main` push
- No tokens or secrets required
- No external dependencies
- Works entirely within GitHub
