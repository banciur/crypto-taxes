# Tests Guidelines

- When it makes sense, prefer pytest fixtures over constructing reusable helpers or services directly inside tests.
- Keep fixtures in the closest `conftest.py` to where they are used.
- If a fixture becomes useful across a wider part of the test tree, move it up to a higher-level `conftest.py`.
