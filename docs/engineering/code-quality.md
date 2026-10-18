# Code quality

Follow Clean Code / SOLID (Uncle Bob) and ArjanCodes principles: high cohesion, low coupling, depend on abstractions, composition over inheritance, IO at the edges.

## Project-specific rules

- Depend on `ProjectStore`, not the filesystem, outside the local adapter.
- Agent capabilities are tools. Do not let the lead reach around them.
- Keep the MIDI model invocation behind a narrow interface.
- Frontend never accesses the filesystem or models directly.

## Testing

Unit-test pure logic and the `ProjectStore` contract. Verify the running stack by using it.
