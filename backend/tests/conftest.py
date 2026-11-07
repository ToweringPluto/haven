"""Test-wide setup. Runs before any test module imports ``haven``."""

import os

# Never let a developer's backend/.env (real Auth0, database or API settings) change how
# the tests behave: CI has no such file, so local runs must not see one either.
os.environ["HAVEN_ENV_FILE"] = os.devnull
