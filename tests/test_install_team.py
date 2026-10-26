import contextlib
import importlib.util
import io
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("install_team", ROOT / "tools/install_team.py")
install_team = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(install_team)


class InstallTeamTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="agentboard-team-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "source"
        self.destination = Path(temporary.name) / "codex-home"
        self.skill_source = self.root / "skills" / "game-team"
        self.skill_target = Path("skills/game-team")
        self.expected = {}
        for relative in install_team.REQUIRED_SKILL_FILES:
            content = b"A portable reference.\r\n"
            if relative == Path("SKILL.md"):
                content = b"---\nname: game-team\ndescription: Coordinate the game team.\n---\n\n# Team\n"
            elif relative == Path("agents/openai.yaml"):
                content = b'interface:\n  display_name: "Game team"\n'
            self.write_source(Path("skills/game-team") / relative, content)
            self.expected[self.skill_target / relative] = content
        extra = Path("references/nested/portable.txt")
        self.write_source(Path("skills/game-team") / extra, b"additional resource\n")
        self.expected[self.skill_target / extra] = b"additional resource\n"
        for name in install_team.ROLES:
            content = (
                f'name = "{name}"\nmodel = "gpt-6.1-sol"\n'
                'description = "A team role"\ndeveloper_instructions = "Follow the assigned scope."\n'
            ).encode("utf-8")
            role_directory = Path("agents")
            if name in install_team.REVIEW_ROLES:
                role_directory /= "independent-reviewers"
            self.write_source(role_directory / f"{name}.toml", content)
            self.expected[Path("agents") / f"{name}.toml"] = content
            self.expected[self.skill_target / "roles" / f"{name}.toml"] = content
            if name in install_team.REVIEW_ROLES:
                self.expected[self.skill_target / "references/independent-reviewers" / f"{name}.toml"] = content
        for source, target in install_team.REFERENCE_FILES:
            content = f"# {source.stem}\nA required portable document.\n".encode()
            if source.name == "COMPLETION_REVIEW.md":
                content += b"[Research](independent-reviewers/RESEARCH.md) [Entry](independent-reviewers/README.md)\n"
            elif source.name == "README.md":
                content += "\n".join(f"[{name}]({name}.toml)" for name in install_team.REVIEW_ROLES).encode()
            self.write_source(source, content)
            self.expected[self.skill_target / target] = content
        helper = b'def evaluate_packet(packet):\n    return {"quality_gate": "invalid"}\n'
        self.write_source(Path("tools/review_gate.py"), helper)
        self.expected[self.skill_target / "scripts/review_gate.py"] = helper
        self.expected[Path("agents") / install_team.PANEL / "review_gate.py"] = helper
        root_patch = patch.object(install_team, "ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def write_source(self, relative, content):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target

    def run_installer(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = install_team.main(list(args))
        return result, output.getvalue(), errors.getvalue()

    def install(self):
        return self.run_installer("--destination", str(self.destination))

    def snapshot(self):
        if not self.destination.exists():
            return None
        return {path.relative_to(self.destination): path.read_bytes()
                for path in self.destination.rglob("*") if path.is_file()}

    def test_installs_complete_bundle_and_all_identical_agent_pairs(self):
        result, _, errors = self.install()
        self.assertEqual(result, 0, errors)
        self.assertEqual(len(install_team.ROLES), 11)
        self.assertTrue({"game-systems-designer", "game-balance-designer"}.issubset(install_team.CORE_ROLES))
        self.assertTrue(set(install_team.DISABLED_ROLES).isdisjoint(install_team.ROLES))
        self.assertEqual(self.snapshot(), self.expected)
        for name in install_team.ROLES:
            self.assertEqual(
                (self.destination / "agents" / f"{name}.toml").read_bytes(),
                (self.destination / self.skill_target / "roles" / f"{name}.toml").read_bytes(),
            )

    def test_review_reference_links_resolve_inside_installed_bundle(self):
        self.assertEqual(self.install()[0], 0)
        references = self.destination / self.skill_target / "references"
        for document in (references / "COMPLETION_REVIEW.md", references / "independent-reviewers/README.md"):
            links = re.findall(r"\[[^\]]*\]\(([^)]+)\)", document.read_text(encoding="utf-8"))
            self.assertTrue(links)
            for relative in links:
                with self.subTest(document=document.name, relative=relative):
                    linked_file = document.parent / relative
                    self.assertTrue(linked_file.is_file())
                    self.assertTrue(linked_file.resolve().is_relative_to((self.destination / self.skill_target).resolve()))

    def test_check_does_not_create_destination_or_modify_existing_files(self):
        result, output, errors = self.run_installer("--check", "--destination", str(self.destination))
        self.assertEqual(result, 0, errors)
        self.assertEqual(output.count("valid:"), len(self.expected))
        self.assertFalse(self.destination.exists())
        self.install()
        before = self.snapshot()
        result, _, errors = self.run_installer("--check", "--destination", str(self.destination))
        self.assertEqual(result, 0, errors)
        self.assertEqual(self.snapshot(), before)

    def test_repeat_install_skips_files_and_preserves_unmanaged_files_and_mtimes(self):
        self.install()
        for relative in (Path("config.toml"), Path("agents/unrelated.toml"), self.skill_target / "old-resource.md"):
            path = self.destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"do not replace or delete")
        before = self.snapshot()
        mtimes = {path: path.stat().st_mtime_ns for path in self.destination.rglob("*") if path.is_file()}
        result, output, errors = self.install()
        self.assertEqual(result, 0, errors)
        self.assertEqual(output.count("unchanged:"), len(self.expected))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual({path: path.stat().st_mtime_ns for path in mtimes}, mtimes)
        self.assertFalse(list(self.destination.rglob("*.bak*")))

    def test_updates_keep_unique_backups_in_each_target_directory(self):
        self.install()
        relatives = (
            Path("agents/game-producer.toml"), self.skill_target / "roles/game-producer.toml",
            self.skill_target / "SKILL.md", self.skill_target / "scripts/review_gate.py",
        )
        for relative in relatives:
            (self.destination / relative).write_bytes(b"old version one")
        self.assertEqual(self.install()[0], 0)
        for relative in relatives:
            target = self.destination / relative
            self.assertEqual(target.with_name(target.name + ".bak").read_bytes(), b"old version one")
            target.write_bytes(b"old version two")
        self.assertEqual(self.install()[0], 0)
        for relative in relatives:
            target = self.destination / relative
            self.assertEqual(target.read_bytes(), self.expected[relative])
            self.assertEqual(target.with_name(target.name + ".bak").read_bytes(), b"old version one")
            self.assertEqual(target.with_name(target.name + ".bak.1").read_bytes(), b"old version two")

    def test_invalid_role_fails_before_creating_or_modifying_destination(self):
        source = self.root / "agents/independent-reviewers" / f"{install_team.ROLES[-1]}.toml"
        original = source.read_bytes()
        invalid_sources = (
            b"name = [", original.replace(b'gpt-6.1-sol', b'wrong-model'),
            original.replace(install_team.ROLES[-1].encode(), b"wrong-name"),
            original.replace(b'"A team role"', b'" "'),
            original.replace(b'"Follow the assigned scope."', b'false'),
        )
        for invalid in invalid_sources:
            with self.subTest(invalid=invalid):
                source.write_bytes(invalid)
                result, _, errors = self.install()
                self.assertEqual(result, 1)
                self.assertTrue(errors)
                self.assertFalse(self.destination.exists())
        source.write_bytes(original)
        self.assertEqual(self.install()[0], 0)
        before = self.snapshot()
        source.write_bytes(b"name = [")
        self.assertEqual(self.install()[0], 1)
        self.assertEqual(self.snapshot(), before)

    def test_invalid_python_fails_before_any_writes_and_is_not_executed(self):
        helper = self.root / "tools/review_gate.py"
        original = helper.read_bytes()
        helper.write_bytes(b"def broken(:\n")
        self.assertEqual(self.install()[0], 1)
        self.assertFalse(self.destination.exists())
        helper.write_bytes(original)
        self.assertEqual(self.install()[0], 0)
        before = self.snapshot()
        source_script = self.write_source(Path("skills/game-team/scripts/extra.py"), b"def broken(:\n")
        self.assertEqual(self.install()[0], 1)
        self.assertEqual(self.snapshot(), before)
        source_script.unlink()
        helper.write_bytes(b'raise RuntimeError("installer must not execute source")\n')
        self.assertEqual(self.install()[0], 0)

    def test_non_utf8_text_is_rejected_before_creating_or_modifying_destination(self):
        invalid_text = "仅用于验证编码".encode("gbk")
        cases = (
            (self.skill_source / "agents/openai.yaml", b"interface:\n  display_name: " + invalid_text),
            (self.root / "agents/independent-reviewers/RESEARCH.md", b"# " + invalid_text),
            (self.root / "agents/game-producer.toml", b"# " + invalid_text),
            (self.root / "tools/review_gate.py", b"# coding: gbk\n# " + invalid_text + b"\n"),
        )
        for source, content in cases:
            original = source.read_bytes()
            with self.subTest(source=source):
                source.write_bytes(content)
                result, _, errors = self.install()
                self.assertEqual(result, 1)
                self.assertIn("UTF-8", errors)
                self.assertFalse(self.destination.exists())
            source.write_bytes(original)
        self.assertEqual(self.install()[0], 0)
        before = self.snapshot()
        for source, content in cases:
            original = source.read_bytes()
            with self.subTest(existing_destination=True, source=source):
                source.write_bytes(content)
                result, _, errors = self.install()
                self.assertEqual(result, 1)
                self.assertIn("UTF-8", errors)
                self.assertEqual(self.snapshot(), before)
            source.write_bytes(original)

    def test_packaging_skips_hidden_metadata_backups_caches_and_editor_files(self):
        artifacts = (
            Path(".git/config"), Path(".private.md"), Path("references/.cache/secret.yaml"),
            Path("scripts/__pycache__/helper.cpython-314.pyc"), Path("references/notes.md.bak"),
            Path("agents/openai.yaml.bak.2"), Path("SKILL.md~"), Path("references/#notes.md#"),
            Path("~$design.md"), Path("references/temporary.yaml.tmp"), Path("references/session.swp"),
        )
        for relative in artifacts:
            self.write_source(Path("skills/game-team") / relative, b"\xff\xfe excluded local data")
        result, _, errors = self.install()
        self.assertEqual(result, 0, errors)
        self.assertEqual(self.snapshot(), self.expected)

    def test_yaml_must_contain_utf8_text_but_needs_no_yaml_parser(self):
        yaml = self.skill_source / "agents/openai.yaml"
        for content in (b" \r\n\t", b"\xef\xbb\xbf\r\n"):
            with self.subTest(content=content):
                yaml.write_bytes(content)
                self.assertEqual(self.install()[0], 1)
                self.assertFalse(self.destination.exists())
        content = 'interface:\n  display_name: "小游戏团队"\n'.encode("utf-8")
        yaml.write_bytes(content)
        result, _, errors = self.install()
        self.assertEqual(result, 0, errors)
        self.assertEqual((self.destination / self.skill_target / "agents/openai.yaml").read_bytes(), content)

    def test_missing_required_inputs_fail_before_any_writes(self):
        required = [self.skill_source / path for path in install_team.REQUIRED_SKILL_FILES]
        required += [self.root / source for source, _ in install_team.REFERENCE_FILES]
        required += [self.root / "tools/review_gate.py"]
        required += [self.root / "agents" / f"{role}.toml" for role in install_team.CORE_ROLES]
        for source in required:
            original = source.read_bytes()
            with self.subTest(source=source):
                source.unlink()
                result, _, errors = self.install()
                self.assertEqual(result, 1)
                self.assertTrue(errors)
                self.assertFalse(self.destination.exists())
            source.write_bytes(original)
        self.assertEqual(self.install()[0], 0)
        before = self.snapshot()
        required[-1].unlink()
        self.assertEqual(self.install()[0], 1)
        self.assertEqual(self.snapshot(), before)

    def test_skill_frontmatter_validation_rejects_invalid_metadata_before_writes(self):
        source = self.skill_source / "SKILL.md"
        for content in (
            b"# no frontmatter\n", b"---\nname: wrong-name\ndescription: Valid\n---\n",
            b"---\nname: game-team\n---\n", b"---\nname: game-team\ndescription: false\n---\n",
            b'---\nname: game-team\ndescription: "  "\n---\n',
            b"---\nname: game-team\nname: game-team\ndescription: Valid\n---\n",
        ):
            with self.subTest(content=content):
                source.write_bytes(content)
                self.assertEqual(self.install()[0], 1)
                self.assertFalse(self.destination.exists())
        source.write_bytes(b'---\nname: "game-team"\ndescription: >-\n  Portable team\n  instructions.\n---\n')
        result, _, errors = self.install()
        self.assertEqual(result, 0, errors)

    def test_default_destination_uses_codex_home_root(self):
        codex_home = self.destination.parent / "isolated-home"
        with patch.dict("os.environ", {"CODEX_HOME": str(codex_home)}):
            result, _, errors = self.run_installer()
        self.assertEqual(result, 0, errors)
        self.destination = codex_home
        self.assertEqual(self.snapshot(), self.expected)

    def test_default_destination_falls_back_to_user_dot_codex(self):
        home = self.destination.parent / "isolated-user"
        with patch.dict("os.environ", {"CODEX_HOME": ""}), patch.object(install_team.Path, "home", return_value=home):
            result, _, errors = self.run_installer()
        self.assertEqual(result, 0, errors)
        self.destination = home / ".codex"
        self.assertEqual(self.snapshot(), self.expected)

    def test_disables_native_and_portable_reviewers_and_preserves_archives(self):
        directories = (Path("agents"), self.skill_target / "roles", self.skill_target / "references/independent-reviewers")
        for directory in directories:
            (self.destination / directory).mkdir(parents=True, exist_ok=True)
            for name in install_team.DISABLED_ROLES:
                target = self.destination / directory / f"{name}.toml"
                target.write_bytes(b"old reviewer")
                target.with_name(target.name + ".disabled").write_bytes(b"prior archive")
        before = self.snapshot()
        self.assertEqual(self.run_installer("--check", "--destination", str(self.destination))[0], 0)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.install()[0], 0)
        for directory in directories:
            for name in install_team.DISABLED_ROLES:
                target = self.destination / directory / f"{name}.toml"
                self.assertFalse(target.exists())
                self.assertEqual(target.with_name(target.name + ".disabled").read_bytes(), b"prior archive")
                self.assertEqual(target.with_name(target.name + ".disabled.bak").read_bytes(), b"old reviewer")
        before = self.snapshot()
        self.assertEqual(self.install()[0], 0)
        self.assertEqual(self.snapshot(), before)

    def test_portable_source_cannot_reintroduce_disabled_reviewer(self):
        for name in install_team.DISABLED_ROLES:
            self.write_source(self.skill_target / "roles" / f"{name}.toml", b"disabled source")
        self.write_source(self.skill_target / "roles/archived.toml.disabled", b"archive")
        self.assertEqual(self.install()[0], 0)
        self.assertEqual(self.snapshot(), self.expected)


if __name__ == "__main__":
    unittest.main()
