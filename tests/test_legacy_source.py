import ast
import unittest

from contracting.artifacts import build_contract_artifacts
from legacy_fixtures import LEGACY_TOKEN

from xian.legacy_source import (
    LegacySourceError,
    apply_compat_rewrites,
    recover_legacy_source,
)


class RecoverLegacySourceTests(unittest.TestCase):
    def test_inverts_every_legacy_transform(self):
        source = recover_legacy_source("con_tok", LEGACY_TOKEN).source
        tree = ast.parse(source)

        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        self.assertEqual(set(functions), {"seed", "require_owner", "transfer", "mint", "peek"})
        self.assertEqual(ast.unparse(functions["seed"].decorator_list[0]), "construct")
        self.assertEqual(ast.unparse(functions["transfer"].decorator_list[0]), "export")
        self.assertEqual(functions["require_owner"].decorator_list, [])
        self.assertNotIn("__", source.replace("__name__", ""))
        self.assertNotRegex(source, r"[(, ]contract=")
        self.assertIn("balances = Hash(default_value=0)", source)
        self.assertIn(
            "other = ForeignHash(foreign_contract=token, foreign_name='balances')", source
        )
        self.assertIn("decimal('0.5')", source)

    def test_recovered_source_compiles_for_the_vm(self):
        source = recover_legacy_source("con_tok", LEGACY_TOKEN).source
        artifacts = build_contract_artifacts(
            module_name="con_tok", source=source, lint=True, vm_profile="xian_vm_v1"
        )
        self.assertTrue(artifacts["vm_ir_json"])

    def test_parameter_shadowing_a_privatized_name_is_refused(self):
        legacy = (
            "def __mean(v: list):\n    return v[0]\n\n\n"
            "@__export('con_m')\n"
            "def standardize(mean: list):\n    return isinstance(__mean, list)\n"
        )
        with self.assertRaisesRegex(LegacySourceError, "collide"):
            recover_legacy_source("con_m", legacy)

    def test_collision_resolution_keeps_legacy_binding_semantics(self):
        legacy = (
            "def __mean(v: list):\n    return v[0]\n\n\n"
            "@__export('con_m')\n"
            "def standardize(mean: list):\n    return isinstance(__mean, list)\n"
        )
        recovered = recover_legacy_source("con_m", legacy, resolve_collisions=True)
        # The reference still points at the function, not the parameter.
        self.assertIn("isinstance(mean_private, list)", recovered.source)
        self.assertIn("def mean_private(v: list)", recovered.source)
        self.assertEqual(recovered.collision_renames, {"__mean": "mean_private"})

    def test_orm_colliding_with_export_requires_an_explicit_override(self):
        legacy = (
            "__burn = Hash(default_value=False, contract='con_b', name='burn')\n\n\n"
            "@__export('con_b')\n"
            "def burn(token_id: int):\n    __burn[token_id] = True\n"
        )
        with self.assertRaisesRegex(LegacySourceError, "storage identity.*source override"):
            recover_legacy_source("con_b", legacy, resolve_collisions=True)

    def test_unexpected_decorator_is_refused(self):
        with self.assertRaisesRegex(LegacySourceError, "unexpected decorator"):
            recover_legacy_source("con_x", "@other\ndef f():\n    pass\n")

    def test_variable_collision_also_preserves_storage_identity(self):
        legacy = (
            "__owner = Variable(contract='con_v', name='owner')\n"
            "@__export('con_v')\n"
            "def change(owner: str):\n    __owner.set(owner)\n"
        )
        with self.assertRaisesRegex(LegacySourceError, "storage identity.*source override"):
            recover_legacy_source("con_v", legacy, resolve_collisions=True)

    def test_local_foreign_handle_collision_can_be_renamed_without_storage_changes(self):
        legacy = (
            "@__export('con_f')\n"
            "def read(ledger: str):\n"
            "    __ledger = ForeignHash(foreign_contract=ledger, foreign_name='balances', "
            "contract='con_f', name='ledger')\n"
            "    return __ledger['alice']\n"
        )
        recovered = recover_legacy_source("con_f", legacy, resolve_collisions=True)
        self.assertEqual(recovered.collision_renames, {"__ledger": "ledger_store"})
        self.assertIn("return ledger_store['alice']", recovered.source)
        build_contract_artifacts(
            module_name="con_f", source=recovered.source, lint=True, vm_profile="xian_vm_v1"
        )


class CompatRewriteTests(unittest.TestCase):
    def test_fstring_with_string_literal_becomes_equivalent_concat(self):
        source = (
            "data = Hash()\n\n"
            "@export\n"
            "def f(i: str):\n"
            "    assert i == 'x', f\"bad {data[i, 'contract']}.\"\n"
        )
        with self.assertRaises(Exception):
            build_contract_artifacts(
                module_name="con_f", source=source, lint=True, vm_profile="xian_vm_v1"
            )
        rewritten, applied = apply_compat_rewrites(source, allowed={"fstring_string_literals"})
        self.assertEqual(applied, {"fstring_string_literals": 1})
        self.assertIn("'bad ' + str(data[i, 'contract']) + '.'", rewritten)
        build_contract_artifacts(
            module_name="con_f", source=rewritten, lint=True, vm_profile="xian_vm_v1"
        )

    def test_fstring_with_format_spec_is_left_alone(self):
        source = "@export\ndef f(i: str):\n    return f\"{i.strip('a'):>5}\"\n"
        rewritten, applied = apply_compat_rewrites(source, allowed={"fstring_string_literals"})
        self.assertEqual(applied, {})
        self.assertEqual(rewritten, source)

    def test_unknown_rewrite_is_rejected(self):
        with self.assertRaises(LegacySourceError):
            apply_compat_rewrites("x = 1\n", allowed={"nope"})


if __name__ == "__main__":
    unittest.main()
