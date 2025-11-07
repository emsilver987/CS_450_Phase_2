"""
Autograder API package.

This module provides a lightweight implementation of the Autograder API
described in the external specification shared with the team.  Endpoints are
backed by an in-memory store so the behaviour is deterministic and easy to
extend later with a database or queue.
"""

from .router import router  # noqa: F401

