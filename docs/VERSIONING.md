# Versioning Policy

This project uses semantic versioning in `MAJOR.MINOR.PATCH` form.

- Major update: increase the first number by 1, for large or breaking updates.
- Feature update: increase the second number by 1, for added functionality.
- Patch update: increase the third number by 1, for bug fixes and small maintenance changes.

Examples:

- `1.0.0` to `2.0.0`: large update
- `1.0.0` to `1.1.0`: new feature
- `1.0.0` to `1.0.1`: bug fix

For every version:

1. Update `VERSION`.
2. Update `CHANGELOG.md`.
3. Add a release note file under `releases/vX.Y.Z.md`.
4. Create a matching GitHub release with the release note content.
