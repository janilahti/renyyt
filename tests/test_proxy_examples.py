"""Keep the explicit proxy allowlists in sync with published server routes."""

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProxyRouteChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        caddy = (ROOT / "deploy/caddy/Caddyfile.example").read_text()
        nginx = (ROOT / "deploy/nginx/renyyt.conf.example").read_text()
        cls.patterns = {
            "caddy": re.compile(re.search(r'path_regexp renyytRoutes "([^"]+)"', caddy).group(1)),
            "nginx": re.compile(re.search(r'if \(\$uri !~ "([^"]+)"\)', nginx).group(1)),
        }
        cls.server = ast.parse((ROOT / "src/renyyt/server.py").read_text())

    def matches(self, proxy, path):
        return bool(self.patterns[proxy].fullmatch(("/renyyt" if proxy == "nginx" else "") + path))

    def test_all_explicit_server_routes_remain_reachable(self):
        routes = set()
        for node in ast.walk(self.server):
            if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "path":
                for comparator in node.comparators:
                    values = comparator.elts if isinstance(comparator, (ast.Tuple, ast.List, ast.Set)) else [comparator]
                    routes.update(value.value for value in values
                                  if isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value.startswith("/"))
        self.assertGreaterEqual(len(routes), 20)
        for proxy in self.patterns:
            for route in routes:
                with self.subTest(proxy=proxy, route=route):
                    self.assertTrue(self.matches(proxy, route))

    def test_all_language_guides_and_public_brand_files_remain_reachable(self):
        languages = next(ast.literal_eval(node.value) for node in ast.walk(self.server)
                         if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "README_LANGUAGES"
                                                                for target in node.targets))
        routes = ["/README.%s.md" % language for language in languages]
        routes += ["/brand/" + item.name for item in (ROOT / "web/assets/brand").iterdir() if item.is_file()]
        routes += ["/assets/%s.0123456789ab.%s" % (name, extension)
                   for name, extension in [("app", "js"), ("helpers", "js"), ("i18n", "js"), ("styles", "css")]]
        for proxy in self.patterns:
            for route in routes:
                with self.subTest(proxy=proxy, route=route):
                    self.assertTrue(self.matches(proxy, route))

    def test_probe_names_and_unknown_route_variants_are_rejected(self):
        probes = ["/google-credentials.json", "/google-key.json", "/.config/gcloud/application_default_credentials.json",
                  "/application_default_credentials.json", "/key.json", "/keyfile.json", "/firebase-adminsdk.json",
                  "/firebase-key.json", "/.env", "/.git/config", "/wp-login.php", "/api/v1/unknown",
                  "/api/v1/features/extra", "/assets/private.js", "/asset-manifest.json", "/README.unknown.md",
                  "/brand/secret.json", "/brand/site.webmanifest.bak", "/.well-known/appspecific/com.chrome.devtools.json"]
        for proxy in self.patterns:
            for path in probes:
                with self.subTest(proxy=proxy, path=path):
                    self.assertFalse(self.matches(proxy, path))
