# Dependencies and licenses

## Licenses

Prefer permissive licenses that do not require the project itself to be open-sourced:

- MIT
- Apache-2.0
- BSD (2-clause or 3-clause)
- ISC
- Similar permissive licenses

Avoid copyleft licenses (GPL, AGPL, LGPL, etc.) and proprietary licenses unless explicitly approved.

## Package preferences

- Prefer the standard library when it is sufficient.
- Prefer well-known, actively maintained packages with healthy communities.
- Prefer existing libraries over hand-rolled solutions when the library meets the license and maintenance criteria. Maintained libraries are more likely to receive updates and security fixes.
- Preferred libraries in this project:
  - Pydantic
  - Pydantic-settings
  - Pydantic AI (and Pydantic AI Harness where appropriate)

## Adding dependencies

Not a hard ban on new packages. Soft rule:

- Call out any new runtime or significant dev dependency in the PR.
- If it is unclear whether a package meets the license or maintenance criteria, ask before adding it.
- Do not add a dependency for a one-off need that the standard library or an existing dependency already covers.
