from kit.tests.test_guard import GuardCase


ROLES = ("builder", "reviewer", "test-writer", "pass")


class TestGitMergeReadOnly(GuardCase):
    def test_reviewer_can_find_the_merge_base(self):
        for command in ("git merge-base HEAD origin/loop/main",
                        "git -C . merge-base origin/loop/main HEAD"):
            with self.subTest(command=command):
                self.allowed(self.bash(command, role="reviewer"))

    def test_merge_base_substitution_and_ancestry_are_allowed_in_every_role(self):
        for role in ROLES:
            for command in (
                "git diff $(git merge-base HEAD origin/loop/main)",
                'git diff "$(git merge-base origin/loop/main HEAD)"',
                "git merge-base --is-ancestor a b",
                "git merge-base --is-ancestor b a",
            ):
                with self.subTest(role=role, command=command):
                    self.allowed(self.bash(command, role=role))

    def test_merge_tree_is_allowed_and_role_restrictions_remain(self):
        for role in ROLES:
            for command in (
                "git merge", "git merge --no-ff x",
                "git merge origin/loop/main", "git push",
                "git push origin feature", "git checkout",
                "git checkout feature", "gh", "gh pr list",
                "git switch feature", "git restore src/app.py",
                "git apply patch.diff", "git branch -f feature HEAD",
                "git branch --force feature HEAD",
            ):
                with self.subTest(role=role, command=command):
                    self.refused(self.bash(command, role=role), "rule: role-git\n")
            for command in ("git merge-tree a b", "git -C . merge-tree b a"):
                with self.subTest(role=role, command=command):
                    self.allowed(self.bash(command, role=role))
