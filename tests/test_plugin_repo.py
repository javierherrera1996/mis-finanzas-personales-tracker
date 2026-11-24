"""El repo sirve de marketplace de plugins de Claude: .claude-plugin/marketplace.json apunta a plugins/mis-finanzas/.
Estas pruebas fallan si alguien cambió la skill o el motor y no volvió a correr claude_ai_skills/empaquetar.py."""
import filecmp, json, os, sys, tempfile, unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "claude_ai_skills"))
import empaquetar  # noqa: E402


def archivos(d):
    return sorted(os.path.relpath(os.path.join(r, f), d) for r, _, fs in os.walk(d) for f in fs
                  if "__pycache__" not in r and not f.endswith(".pyc"))


class PluginRepo(unittest.TestCase):
    def test_marketplace_apunta_al_plugin(self):
        mk = json.load(open(os.path.join(RAIZ, ".claude-plugin", "marketplace.json")))
        self.assertTrue(mk["name"] and mk["owner"]["name"])
        [p] = mk["plugins"]
        src = os.path.normpath(os.path.join(RAIZ, p["source"]))
        pj = json.load(open(os.path.join(src, ".claude-plugin", "plugin.json")))
        self.assertEqual(p["name"], pj["name"])
        self.assertEqual(p["version"], pj["version"])
        self.assertTrue(os.path.exists(os.path.join(src, "skills", "mis-finanzas", "SKILL.md")))
        self.assertTrue(os.path.exists(os.path.join(src, "skills", "mis-finanzas", "motor", "procesar.py")))

    def test_version_de_la_skill_igual_al_plugin(self):
        pj = json.load(open(os.path.join(RAIZ, "claude_ai_skills", "plugin", ".claude-plugin", "plugin.json")))
        skill = open(os.path.join(RAIZ, "claude_ai_skills", "mis-finanzas", "SKILL.md")).read()
        self.assertIn(f"Versión {pj['version']} ", skill)

    def test_plugin_del_repo_al_dia(self):
        tmp = tempfile.mkdtemp()
        nuevo = empaquetar.armar_plugin(tmp, "mis-finanzas")
        repo = os.path.join(RAIZ, "plugins", "mis-finanzas")
        self.assertEqual(archivos(nuevo), archivos(repo), "corre: python claude_ai_skills/empaquetar.py")
        for f in archivos(nuevo):
            self.assertTrue(filecmp.cmp(os.path.join(nuevo, f), os.path.join(repo, f), shallow=False),
                            f"{f} desactualizado: corre python claude_ai_skills/empaquetar.py")


if __name__ == "__main__":
    unittest.main()
