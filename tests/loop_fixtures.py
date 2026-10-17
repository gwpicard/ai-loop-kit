"""Shared project fixture for gate checks."""

from helpers import Project

# isort: split
import gate


class GateFixture:
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)

    def ready(self, n):
        return gate.move(self.p.gh, self.p.root, n, "ready")
