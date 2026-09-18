"""Metadata, documentation, and contract tests for n8n-workflow-manager."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestMetadataAndDocumentation(unittest.TestCase):
    """Contract tests for Pfad B discoverability and repository governance."""

    def setUp(self):
        self.pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.init_text = (ROOT / "n8nManager" / "__init__.py").read_text(encoding="utf-8")
        self.readme_en = (ROOT / "README.md").read_text(encoding="utf-8")
        self.readme_de = (ROOT / "README_de.md").read_text(encoding="utf-8")
        self.security_text = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        self.changelog_text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.llms_text = (ROOT / "llms.txt").read_text(encoding="utf-8")
        self.gitignore_text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.ci_workflow_text = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        self.marketing_log_text = (ROOT / "MARKETING-LOG.txt").read_text(encoding="utf-8")

    def test_version_parity(self):
        """Verify 0.2.6 version parity across pyproject.toml, __init__.py, changelog and llms.txt."""
        self.assertIn('version = "0.2.6"', self.pyproject_text)
        self.assertIn('__version__ = "0.2.6"', self.init_text)
        self.assertIn("## 0.2.6 — 2026-09-10", self.changelog_text)
        self.assertIn("Version: 0.2.6", self.llms_text)

    def test_readme_navigation_anchor_parity(self):
        """Verify 17 navigation anchor links exist in both READMEs and point to existing HTML anchor tags."""
        for readme, lang in [(self.readme_en, "EN"), (self.readme_de, "DE")]:
            nav_match = re.search(r"## Navigation\s*\n\n((?:- \[.*?\]\(#.*?\)\n)+)", readme)
            self.assertIsNotNone(nav_match, f"Navigation section missing in {lang} README")
            nav_links = re.findall(r"- \[(.*?)\]\(#(.*?)\)", nav_match.group(1))
            self.assertEqual(len(nav_links), 17, f"Expected 17 navigation links in {lang} README, found {len(nav_links)}")
            for label, anchor in nav_links:
                self.assertTrue(
                    f'<a id="{anchor}"></a>' in readme or f"#{anchor}" in readme.lower(),
                    f"Anchor target {anchor} missing in {lang} README for link {label}",
                )

    def test_readme_badges_completeness(self):
        """Verify standard Shields.io badges in both README files."""
        for readme, lang in [(self.readme_en, "EN"), (self.readme_de, "DE")]:
            self.assertIn("img.shields.io/badge/python-3.10+", readme, f"Python badge missing in {lang}")
            self.assertIn("img.shields.io/badge/version-0.2.6", readme, f"Version badge missing in {lang}")
            self.assertIn("img.shields.io/badge/License-MIT", readme, f"License badge missing in {lang}")
            self.assertIn("img.shields.io/badge/FastAPI-0.115+", readme, f"FastAPI badge missing in {lang}")
            self.assertIn("img.shields.io/badge/Ecosystem-ellmos--ai", readme, f"Ecosystem badge missing in {lang}")
            self.assertIn("img.shields.io/badge/Umbrella-open--bricks", readme, f"Umbrella badge missing in {lang}")
            self.assertIn("img.shields.io/badge/LLM--Ready-llms.txt", readme, f"LLM-Ready badge missing in {lang}")

    def test_readme_dual_mermaid_diagrams(self):
        """Verify both architecture and sequence diagrams exist in both READMEs."""
        for readme, lang in [(self.readme_en, "EN"), (self.readme_de, "DE")]:
            self.assertIn("```mermaid\ngraph TD", readme, f"Architecture diagram missing in {lang}")
            self.assertIn("```mermaid\nsequenceDiagram\n    autonumber", readme, f"Sequence diagram missing in {lang}")
            self.assertIn("FastAPI", readme)
            self.assertIn("SQLite", readme)

    def test_readme_governance_invariants_table(self):
        """Verify 10 Governance and Runtime Invariants are documented in both READMEs."""
        for readme, lang in [(self.readme_en, "EN"), (self.readme_de, "DE")]:
            for i in range(1, 11):
                self.assertRegex(
                    readme,
                    rf"\|\s*{i}\s*\|",
                    f"Invariant #{i} missing from table in {lang} README",
                )

    def test_readme_ecosystem_matrix(self):
        """Verify sibling ecosystem tools matrix in both README files."""
        for readme, lang in [(self.readme_en, "EN"), (self.readme_de, "DE")]:
            self.assertIn("ellmos-ai/n8n-manager-mcp", readme, f"MCP pairing missing in {lang}")
            self.assertIn("ellmos-ai/ellmos-stack", readme, f"Stack pairing missing in {lang}")
            self.assertIn("open-bricks/open-bricks", readme, f"Umbrella pairing missing in {lang}")

    def test_security_policy_contract(self):
        """Verify bilingual SECURITY.md contains SLAs, supported versions, and official contacts."""
        self.assertIn("0.2.x", self.security_text)
        self.assertIn("48 hours", self.security_text)
        self.assertIn("5 business days", self.security_text)
        self.assertIn("security@open-bricks.org", self.security_text)
        self.assertIn("security@ellmos.ai", self.security_text)
        self.assertIn("48 Stunden", self.security_text)
        self.assertIn("5 Werktagen", self.security_text)

    def test_ci_workflow_concurrency(self):
        """Verify CI workflow has concurrency cancel-in-progress enabled."""
        self.assertIn("concurrency:", self.ci_workflow_text)
        self.assertIn("cancel-in-progress: true", self.ci_workflow_text)

    def test_ci_workflow_compileall_gate_and_matrix(self):
        """Verify bytecode compilation gate and Python 3.13 in CI test matrix."""
        self.assertIn("Bytecode compilation gate", self.ci_workflow_text)
        self.assertIn("python -m compileall -q n8nManager tests", self.ci_workflow_text)
        self.assertIn("python -m pytest -ra -v", self.ci_workflow_text)
        self.assertIn('"3.13"', self.ci_workflow_text)

    def test_pep621_packaging_compliance(self):
        """Verify PEP 621 metadata, OS classifiers, and pytest configuration in pyproject.toml."""
        self.assertIn('Changelog = "https://github.com/ellmos-ai/n8n-workflow-manager/blob/main/CHANGELOG.md"', self.pyproject_text)
        self.assertIn('"Third-Party Licenses"', self.pyproject_text)
        self.assertIn('"Operating System :: Microsoft :: Windows"', self.pyproject_text)
        self.assertIn('"Operating System :: POSIX :: Linux"', self.pyproject_text)
        self.assertIn('"Operating System :: MacOS"', self.pyproject_text)
        self.assertIn('addopts = "-ra -v"', self.pyproject_text)

    def test_gitignore_hardening(self):
        """Verify .gitignore excludes sync conflicts, locks, and caches."""
        self.assertIn("*.sync-conflict-*", self.gitignore_text)
        self.assertIn("LOCK.*", self.gitignore_text)
        self.assertIn("LOCK\n", self.gitignore_text)
        self.assertIn("LOCK*.txt", self.gitignore_text)
        self.assertIn("LOCK.permissions.json", self.gitignore_text)
        self.assertIn("*-ASUS-GEI.*", self.gitignore_text)
        self.assertIn("*-WORKSTATION-LG.*", self.gitignore_text)
        self.assertIn(".pytest_cache/", self.gitignore_text)
        self.assertIn(".mypy_cache/", self.gitignore_text)

    def test_marketing_log_and_llms_txt_freshness(self):
        """Verify MARKETING-LOG.txt and llms.txt are complete and up to date."""
        self.assertIn("Pfad B", self.marketing_log_text)
        self.assertIn("PyPI Distribution", self.marketing_log_text)
        self.assertIn("2026-09-18", self.marketing_log_text)
        self.assertIn("2026-09-18", self.llms_text)
        self.assertIn("210+ Pytest", self.llms_text)

    def test_readme_visual_screenshots_and_use_case_table(self):
        """Verify screenshots exist on disk and are embedded in both README files alongside use-case quick start."""
        for path in [
            ROOT / "docs" / "screenshots" / "dashboard.png",
            ROOT / "docs" / "screenshots" / "workflow-viewer.png",
            ROOT / "README" / "screenshots" / "dashboard.png",
            ROOT / "README" / "screenshots" / "workflow-viewer.png",
        ]:
            self.assertTrue(path.exists(), f"Screenshot file missing: {path}")

        for readme, lang in [(self.readme_en, "EN"), (self.readme_de, "DE")]:
            self.assertIn("docs/screenshots/dashboard.png", readme, f"Dashboard screenshot missing in {lang}")
            self.assertIn("docs/screenshots/workflow-viewer.png", readme, f"Workflow viewer screenshot missing in {lang}")
            self.assertIn("Quick Start by Use Case" if lang == "EN" else "Schnellstart nach Anwendungsfall", readme)

    def test_readme_personas_and_comparison_matrix(self):
        """Verify target audience personas, SEO, and comparison matrix in both README files."""
        for readme, lang in [(self.readme_en, "EN"), (self.readme_de, "DE")]:
            for persona in ["[PERSONA-01]", "[PERSONA-02]", "[PERSONA-03]", "[PERSONA-04]"]:
                self.assertIn(persona, readme, f"Persona {persona} missing in {lang} README")
            self.assertIn("127.0.0.1", readme)
            self.assertIn("RunAsInvoker", readme)

        self.assertIn("§ 521 BGB Gefälligkeitsrecht", self.readme_de)

    def test_pyproject_keywords_enrichment(self):
        """Verify pyproject.toml includes high-intent SEO discoverability keywords."""
        self.assertIn('"mcp-companion"', self.pyproject_text)
        self.assertIn('"sqlite-audit"', self.pyproject_text)
        self.assertIn('"workflow-rollback"', self.pyproject_text)

    def test_changelog_recent_pfad_a_entry(self):
        """Verify CHANGELOG.md contains the 0.2.6 Pfad A hardening release entry."""
        self.assertIn("## 0.2.6 — 2026-09-10", self.changelog_text)
        self.assertIn("CI Matrix & Bytecode Gate Hardening (Pfad A)", self.changelog_text)
        self.assertIn("PEP 621 Packaging Metadata Standardization", self.changelog_text)
        self.assertIn("Multi-Host Sync & Coordination Lock Hygiene", self.changelog_text)

    def test_project_scripts_and_dependencies(self):
        """Verify project CLI script entry point and core dependencies."""
        self.assertIn('n8n-manager = "n8nManager.n8n_manager:main"', self.pyproject_text)
        self.assertIn('"fastapi>=0.115,<1"', self.pyproject_text)
        self.assertIn('"pydantic>=2.8,<3"', self.pyproject_text)


if __name__ == "__main__":
    unittest.main()
