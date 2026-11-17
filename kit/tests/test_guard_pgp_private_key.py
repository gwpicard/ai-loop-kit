from kit.tests.test_guard import GuardCase


class TestPgpPrivateKey(GuardCase):
    def test_pgp_private_key_block_refused(self):
        header = "-----BEGIN " + "PGP PRIVATE KEY BLOCK-----"
        r = self.call("Write", {"file_path": "docs/key.asc", "content": header + "\nabc\n"})
        self.refused(r, "secret")
