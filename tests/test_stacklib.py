import base64
import json
import os
import sys
import threading
import unittest
import unittest.mock
import urllib.parse
from dataclasses import fields
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import stacklib


def sample_profile():
    return {
        "id": 1,
        "name": "Any",
        "upgradeAllowed": False,
        "cutoff": 19,
        "items": [
            {"quality": {"id": 1, "name": "SDTV", "resolution": 480}, "allowed": True},
            {"quality": {"id": 8, "name": "WEBDL-1080p", "resolution": 1080}, "allowed": False},
            {"quality": {"id": 7, "name": "Bluray-1080p", "resolution": 1080}, "allowed": True},
            {"quality": {"id": 19, "name": "Bluray-2160p", "resolution": 2160}, "allowed": True},
            {
                "id": 1002,
                "name": "WEB 2160p",
                "allowed": True,
                "items": [
                    {"quality": {"id": 18, "name": "WEBDL-2160p", "resolution": 2160}, "allowed": True}
                ],
            },
        ],
    }


class AppState:
    def __init__(self):
        self.wizard = False
        self.libraries = []
        self.qbit_prefs = {}
        self.categories = []
        self.password = "test-password"
        self.host = {
            "username": "",
            "password": "",
            "authenticationMethod": "none",
            "authenticationRequired": "disabled",
            "port": 8989,
            "instanceName": "app",
        }
        self.roots = []
        self.naming = {"renameEpisodes": False, "renameMovies": False, "replaceIllegalCharacters": False}
        self.media = {"copyUsingHardlinks": False}
        self.profile = sample_profile()
        self.clients = []
        self.applications = []
        self.proxies = []
        self.seerr_initialized = False
        self.seerr_setup = None
        self.seerr_services = {"sonarr": [], "radarr": []}
        self.seerr_main = {"applicationTitle": "Seerr", "applicationUrl": "", "mediaServerType": 0, "apiKey": "seerr"}
        self.seerr_external = ""
        self.library_syncs = 0
        self.calls = []


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    @property
    def app(self) -> AppState:
        return self.server.app

    @property
    def role(self) -> str:
        return self.server.role

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PUT(self):
        self._handle("PUT")

    def _handle(self, method):
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b""
        body = self._parse_body(raw)
        self.app.calls.append((self.role, method, path))
        key = self.headers.get("X-Api-Key")
        if path.startswith("/api/") and self.role in {"sonarr", "radarr", "prowlarr"}:
            expected = {"sonarr": "sonarr-key", "radarr": "radarr-key", "prowlarr": "prowlarr-key"}[self.role]
            if key != expected:
                self._send(401, {"error": "unauthorized"})
                return
        status, payload, kind = self._route(method, path, query, body)
        if kind == "empty":
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if kind == "text":
            data = payload.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _parse_body(self, raw: bytes):
        if not raw:
            return {}
        ctype = self.headers.get("Content-Type", "")
        if "json" in ctype:
            return json.loads(raw.decode("utf-8"))
        if "form" in ctype:
            parsed = urllib.parse.parse_qs(raw.decode("utf-8"), keep_blank_values=True)
            return {key: values[0] if len(values) == 1 else values for key, values in parsed.items()}
        return raw.decode("utf-8", errors="replace")

    def _route(self, method, path, query, body):
        role = self.role
        app = self.app
        if role == "jellyfin":
            return self._jellyfin(method, path, query, body)
        if role == "qbit":
            return self._qbit(method, path, body)
        if role in {"sonarr", "radarr"}:
            return self._servarr(method, path, body)
        if role == "prowlarr":
            return self._prowlarr(method, path, body)
        if role == "seerr":
            return self._seerr(method, path, query, body)
        return 404, {"error": "no role"}, "json"

    def _jellyfin(self, method, path, query, body):
        app = self.app
        if path == "/System/Info/Public":
            return 200, {"StartupWizardCompleted": app.wizard}, "json"
        if path == "/Startup/User" and method == "POST":
            app.user = body
            return 204, None, "empty"
        if path in {"/Startup/Configuration", "/Startup/RemoteAccess"} and method == "POST":
            return 204, None, "empty"
        if path == "/Startup/Complete" and method == "POST":
            app.wizard = True
            return 204, None, "empty"
        if path == "/Users/AuthenticateByName" and method == "POST":
            if body.get("Pw") != app.password or body.get("Username") != "admin":
                return 401, {"error": "bad login"}, "json"
            return 200, {"AccessToken": "token-1", "User": {"Name": "admin"}}, "json"
        if path == "/Library/VirtualFolders" and method == "GET":
            return 200, [{"Name": item["name"]} for item in app.libraries], "json"
        if path == "/Library/VirtualFolders" and method == "POST":
            app.libraries.append({"name": query["name"][0], "type": query["collectionType"][0], "path": query["paths"][0]})
            return 204, None, "empty"
        return 404, {"error": path}, "json"

    def _qbit(self, method, path, body):
        app = self.app
        if path == "/api/v2/app/version":
            return 200, "v5.0.0", "text"
        if path == "/api/v2/auth/login" and method == "POST":
            if body.get("username") == "admin" and body.get("password") == app.password:
                return 200, "Ok.", "text"
            return 200, "Fails.", "text"
        if path == "/api/v2/app/setPreferences" and method == "POST":
            app.qbit_prefs = json.loads(body["json"])
            return 200, "", "text"
        if path == "/api/v2/torrents/createCategory" and method == "POST":
            if body.get("category") in app.categories:
                return 409, "exists", "text"
            app.categories.append(body.get("category"))
            return 200, "Ok.", "text"
        return 404, "missing", "text"

    def _servarr(self, method, path, body):
        app = self.app
        if path == "/ping":
            return 200, "OK", "text"
        if path.endswith("/config/host") and method == "GET":
            return 200, app.host, "json"
        if path.endswith("/config/host") and method == "PUT":
            app.host = body
            return 202, app.host, "json"
        if path.endswith("/rootfolder") and method == "GET":
            return 200, [{"path": item} for item in app.roots], "json"
        if path.endswith("/rootfolder") and method == "POST":
            app.roots.append(body["path"])
            return 201, body, "json"
        if path.endswith("/config/naming") and method == "GET":
            return 200, app.naming, "json"
        if path.endswith("/config/naming") and method == "PUT":
            app.naming = body
            return 202, app.naming, "json"
        if path.endswith("/config/mediamanagement") and method == "GET":
            return 200, app.media, "json"
        if path.endswith("/config/mediamanagement") and method == "PUT":
            app.media = body
            return 202, app.media, "json"
        if path.endswith("/qualityprofile") and method == "GET":
            return 200, [app.profile], "json"
        if "/qualityprofile/" in path and method == "PUT":
            app.profile = body
            return 202, app.profile, "json"
        if path.endswith("/downloadclient/schema"):
            return 200, [
                {
                    "implementation": "QBittorrent",
                    "implementationName": "qBittorrent",
                    "configContract": "QBittorrentSettings",
                    "fields": [
                        {"name": "host", "value": "localhost"},
                        {"name": "port", "value": 8080},
                        {"name": "useSsl", "value": False},
                        {"name": "username", "value": ""},
                        {"name": "password", "value": ""},
                        {"name": "tvCategory", "value": "tv-sonarr"},
                        {"name": "movieCategory", "value": "radarr"},
                    ],
                }
            ], "json"
        if path.endswith("/downloadclient/test") and method == "POST":
            return 200, {}, "json"
        if path.endswith("/downloadclient") and method == "GET":
            return 200, app.clients, "json"
        if path.endswith("/downloadclient") and method == "POST":
            body = dict(body)
            body["id"] = len(app.clients) + 1
            app.clients.append(body)
            return 201, body, "json"
        if "/downloadclient/" in path and method == "PUT":
            for index, item in enumerate(app.clients):
                if item["id"] == body["id"]:
                    app.clients[index] = body
            return 202, body, "json"
        return 404, {"error": path}, "json"

    def _prowlarr(self, method, path, body):
        app = self.app
        if path == "/ping":
            return 200, "OK", "text"
        if path == "/api/v1/config/host" and method == "GET":
            return 200, app.host, "json"
        if path == "/api/v1/config/host" and method == "PUT":
            app.host = body
            return 202, app.host, "json"
        if path == "/api/v1/applications/schema":
            return 200, [
                {
                    "implementation": "Sonarr",
                    "implementationName": "Sonarr",
                    "configContract": "SonarrSettings",
                    "fields": [
                        {"name": "prowlarrUrl", "value": "http://localhost:9696"},
                        {"name": "baseUrl", "value": ""},
                        {"name": "apiKey", "value": ""},
                        {"name": "syncCategories", "value": [5000]},
                    ],
                },
                {
                    "implementation": "Radarr",
                    "implementationName": "Radarr",
                    "configContract": "RadarrSettings",
                    "fields": [
                        {"name": "prowlarrUrl", "value": "http://localhost:9696"},
                        {"name": "baseUrl", "value": ""},
                        {"name": "apiKey", "value": ""},
                        {"name": "syncCategories", "value": [2000]},
                    ],
                },
            ], "json"
        if path == "/api/v1/applications/test":
            return 200, {}, "json"
        if path == "/api/v1/applications" and method == "GET":
            return 200, app.applications, "json"
        if path == "/api/v1/applications" and method == "POST":
            body = dict(body)
            body["id"] = len(app.applications) + 1
            app.applications.append(body)
            return 201, body, "json"
        if path.startswith("/api/v1/applications/") and method == "PUT":
            return 202, body, "json"
        if path == "/api/v1/indexerProxy/schema":
            return 200, [
                {
                    "implementation": "FlareSolverr",
                    "configContract": "FlareSolverrSettings",
                    "fields": [{"name": "host", "value": ""}],
                }
            ], "json"
        if path == "/api/v1/indexerProxy" and method == "GET":
            return 200, app.proxies, "json"
        if path == "/api/v1/indexerProxy" and method == "POST":
            body = dict(body)
            body["id"] = 1
            app.proxies.append(body)
            return 201, body, "json"
        if path.startswith("/api/v1/indexerProxy/") and method == "PUT":
            return 202, body, "json"
        return 404, {"error": path}, "json"

    def _seerr(self, method, path, query, body):
        app = self.app
        if path == "/api/v1/settings/public":
            return 200, {"initialized": app.seerr_initialized}, "json"
        if path == "/api/v1/auth/jellyfin" and method == "POST":
            if body.get("username") != "admin" or body.get("password") != app.password:
                return 401, {"error": "bad login"}, "json"
            if app.seerr_initialized and body.get("hostname"):
                return 500, {"error": "Jellyfin hostname already configured"}, "json"
            if body.get("hostname"):
                app.seerr_setup = body
            app.seerr_user = body
            return 200, {"id": 1, "displayName": "admin"}, "json"
        if path == "/api/v1/settings/jellyfin" and method == "POST":
            app.seerr_external = body.get("externalHostname", "")
            return 200, body, "json"
        if path == "/api/v1/settings/jellyfin/library":
            app.library_syncs += 1
            return 200, [{"id": "movies", "name": "Movies", "enabled": "enable" in query}], "json"
        if path == "/api/v1/settings/main" and method == "GET":
            return 200, app.seerr_main, "json"
        if path == "/api/v1/settings/main" and method == "POST":
            app.seerr_main = body
            return 200, body, "json"
        if path == "/api/v1/settings/initialize" and method == "POST":
            app.seerr_initialized = True
            return 200, {"initialized": True}, "json"
        for name in ("sonarr", "radarr"):
            if path == f"/api/v1/settings/{name}/test":
                return 200, {"ok": True}, "json"
            if path == f"/api/v1/settings/{name}" and method == "GET":
                return 200, app.seerr_services[name], "json"
            if path == f"/api/v1/settings/{name}" and method == "POST":
                app.seerr_services[name].append(body)
                return 201, body, "json"
        return 404, {"error": path}, "json"

    def _send(self, status, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def serve(role: str, app: AppState):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.role = role
    server.app = app
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def field_value(payload, name):
    for field in payload["fields"]:
        if field["name"] == name:
            return field["value"]
    raise AssertionError(name)


class StacklibTests(unittest.TestCase):
    def test_password_hash_matches_qbittorrent_pbkdf2(self):
        secret = stacklib.qbittorrent_password_secret("correct horse")
        salt_b64, digest_b64 = secret.split(":")
        self.assertEqual(len(base64.b64decode(salt_b64)), 16)
        self.assertEqual(len(base64.b64decode(digest_b64)), 64)
        self.assertTrue(stacklib.verify_qbittorrent_secret(secret, "correct horse"))
        self.assertFalse(stacklib.verify_qbittorrent_secret(secret, "wrong"))

        ini = stacklib.qbittorrent_password_ini("correct horse")
        self.assertTrue(ini.startswith('"@ByteArray(') and ini.endswith(')"'))
        secret = ini[len('"@ByteArray(') : -2]
        self.assertTrue(stacklib.verify_qbittorrent_secret(secret, "correct horse"))

    def test_quality_cap_stops_at_1080p(self):
        profile = stacklib.cap_profile_at_1080(sample_profile())
        by_name = {}

        def walk(items):
            for item in items:
                if item.get("items"):
                    by_name[item["name"]] = item["allowed"]
                    walk(item["items"])
                else:
                    by_name[item["quality"]["name"]] = item["allowed"]

        walk(profile["items"])
        self.assertTrue(by_name["Bluray-1080p"])
        self.assertTrue(by_name["WEBDL-1080p"])
        self.assertFalse(by_name["Bluray-2160p"])
        self.assertFalse(by_name["WEB 2160p"])
        self.assertFalse(by_name["WEBDL-2160p"])
        self.assertTrue(profile["upgradeAllowed"])
        self.assertEqual(profile["cutoff"], 7)

    def test_compose_vpn_and_direct_modes(self):
        vpn = stacklib.render_compose(True)
        direct = stacklib.render_compose(False)
        self.assertIn("${PUID}", vpn)
        self.assertNotIn("{{", vpn)
        self.assertIn("network_mode: service:gluetun", vpn)
        self.assertIn("FIREWALL_OUTBOUND_SUBNETS", vpn)
        self.assertIn("ghcr.io/seerr-team/seerr:latest", vpn)
        self.assertIn('user: "${PUID}:${PGID}"', vpn)
        self.assertIn("container_name: gluetun", vpn)
        self.assertNotIn("{extra_block}", vpn)
        self.assertNotIn("{extra_block}", direct)
        custom = stacklib.render_compose(True, ["SERVER_COUNTRIES", "VPN_TYPE"])
        self.assertIn("SERVER_COUNTRIES=${GLUETUN_SERVER_COUNTRIES}", custom)
        self.assertNotIn("GLUETUN_VPN_TYPE", custom)
        self.assertNotIn("gluetun", direct)
        self.assertIn("${QBIT_PORT:-8080}:8080", direct)
        self.assertIn("${PROWLARR_PORT:-9696}:9696", direct)

    def test_qbittorrent_conf_seeds_account_and_vpn_bind(self):
        with TemporaryDirectory() as tmp:
            stacklib.write_qbittorrent_conf(Path(tmp), "admin", "correct horse", True)
            text = (Path(tmp) / "qbittorrent" / "qBittorrent" / "qBittorrent.conf").read_text()
            self.assertIn("WebUI\\Username=admin", text)
            self.assertIn("Session\\Interface=tun0", text)
            self.assertIn("/downloads/completed", text)
            self.assertIn("WebUI\\HostHeaderValidation=false", text)
            secret = text.split('WebUI\\Password_PBKDF2="@ByteArray(', 1)[1].split(")", 1)[0]
            self.assertTrue(stacklib.verify_qbittorrent_secret(secret, "correct horse"))
            stacklib.write_qbittorrent_conf(Path(tmp), "other", "nope", False)
            again = (Path(tmp) / "qbittorrent" / "qBittorrent" / "qBittorrent.conf").read_text()
            self.assertEqual(text, again)

    def test_missing_vpn_account_explains_the_one_command(self):
        keys = [item.name.upper() for item in fields(stacklib.Settings)]
        saved = {key: os.environ.pop(key) for key in keys if key in os.environ}
        try:
            with TemporaryDirectory() as tmp:
                with unittest.mock.patch.object(stacklib, "ENV_PATH", Path(tmp) / ".env"):
                    with self.assertRaises(stacklib.SetupError) as raised:
                        stacklib.collect_settings(assume_yes=True, no_vpn=False)
            self.assertIn("--no-vpn", str(raised.exception))
            self.assertIn("OPENVPN_USER", str(raised.exception))
        finally:
            os.environ.update(saved)

    def test_environment_overrides_env_file(self):
        keys = [item.name.upper() for item in fields(stacklib.Settings)]
        saved = {key: os.environ.pop(key) for key in keys if key in os.environ}
        os.environ["OPENVPN_USER"] = "from-env"
        os.environ["OPENVPN_PASSWORD"] = "secret"
        os.environ["ADMIN_PASSWORD"] = "admin-secret"
        try:
            with TemporaryDirectory() as tmp:
                env_path = Path(tmp) / ".env"
                env_path.write_text("OPENVPN_USER='from-file'\nUSE_VPN=1\nVPN_TYPE=openvpn\n")
                with unittest.mock.patch.object(stacklib, "ENV_PATH", env_path):
                    settings, _extras = stacklib.collect_settings(assume_yes=True, no_vpn=False)
            self.assertEqual(settings.openvpn_user, "from-env")
            self.assertEqual(settings.admin_password, "admin-secret")
            self.assertTrue(settings.vpn_enabled)
        finally:
            for key in ("OPENVPN_USER", "OPENVPN_PASSWORD", "ADMIN_PASSWORD"):
                os.environ.pop(key, None)
            os.environ.update(saved)

    def _run_configure(self, use_vpn: str):
        roles = ("jellyfin", "qbit", "sonarr", "radarr", "prowlarr", "seerr")
        states = {role: AppState() for role in roles}
        servers = [serve(role, states[role]) for role in roles]

        def stop_servers():
            for server in servers:
                server.shutdown()
                server.server_close()

        self.addCleanup(stop_servers)
        urls = {server.role: f"http://127.0.0.1:{server.server_address[1]}" for server in servers}
        with TemporaryDirectory() as tmp:
            config = Path(tmp)
            for name, key in (("sonarr", "sonarr-key"), ("radarr", "radarr-key"), ("prowlarr", "prowlarr-key")):
                folder = config / name
                folder.mkdir()
                (folder / "config.xml").write_text(f"<Config><ApiKey>{key}</ApiKey></Config>")
            settings = stacklib.Settings(admin_user="admin", admin_password="test-password", use_vpn=use_vpn)
            configurator = stacklib.StackConfigurator(settings, urls=urls, config_dir=config, log=lambda *_args: None)
            configurator.configure()
            configurator.configure()
        return states

    def test_configure_creates_accounts_and_is_safe_to_repeat(self):
        states = self._run_configure("1")
        jellyfin = states["jellyfin"]
        qbit = states["qbit"]
        sonarr_state = states["sonarr"]
        radarr_state = states["radarr"]
        prowlarr = states["prowlarr"]
        seerr = states["seerr"]

        self.assertEqual(jellyfin.user["Name"], "admin")
        self.assertEqual(jellyfin.user["Password"], "test-password")
        self.assertEqual(sorted(item["name"] for item in jellyfin.libraries), ["Movies", "TV"])
        self.assertEqual(next(item["path"] for item in jellyfin.libraries if item["name"] == "Movies"), "/media/movies")
        self.assertEqual(next(item["path"] for item in jellyfin.libraries if item["name"] == "TV"), "/media/tv")
        self.assertTrue(jellyfin.wizard)
        self.assertEqual(qbit.qbit_prefs["save_path"], "/downloads/completed")
        self.assertEqual(qbit.qbit_prefs["temp_path"], "/downloads/incomplete")
        self.assertEqual(qbit.qbit_prefs["web_ui_username"], "admin")
        self.assertEqual(qbit.qbit_prefs["current_network_interface"], "tun0")
        self.assertFalse(qbit.qbit_prefs["web_ui_host_header_validation_enabled"])
        self.assertEqual(sorted(qbit.categories), ["radarr", "tv-sonarr"])
        self.assertEqual(sonarr_state.host["username"], "admin")
        self.assertEqual(sonarr_state.host["authenticationMethod"], "forms")
        self.assertEqual(radarr_state.host["username"], "admin")
        self.assertEqual(prowlarr.host["authenticationMethod"], "forms")
        self.assertEqual(sonarr_state.roots, ["/tv"])
        self.assertEqual(radarr_state.roots, ["/movies"])
        self.assertTrue(sonarr_state.naming["renameEpisodes"])
        self.assertTrue(radarr_state.naming["renameMovies"])
        self.assertTrue(sonarr_state.media["copyUsingHardlinks"])
        self.assertTrue(radarr_state.media["copyUsingHardlinks"])
        self.assertEqual(sonarr_state.profile["cutoff"], 7)
        self.assertFalse(
            any(
                item.get("quality", {}).get("name") == "Bluray-2160p" and item.get("allowed")
                for item in sonarr_state.profile["items"]
            )
        )
        self.assertEqual(len(sonarr_state.clients), 1)
        self.assertEqual(len(radarr_state.clients), 1)
        self.assertEqual(field_value(sonarr_state.clients[0], "host"), "gluetun")
        self.assertEqual(field_value(sonarr_state.clients[0], "username"), "admin")
        self.assertEqual(field_value(sonarr_state.clients[0], "tvCategory"), "tv-sonarr")
        self.assertEqual(field_value(radarr_state.clients[0], "movieCategory"), "radarr")
        self.assertEqual(len(prowlarr.applications), 2)
        sonarr = next(item for item in prowlarr.applications if item["name"] == "Sonarr")
        radarr = next(item for item in prowlarr.applications if item["name"] == "Radarr")
        self.assertEqual(field_value(sonarr, "baseUrl"), "http://sonarr:8989")
        self.assertEqual(field_value(sonarr, "apiKey"), "sonarr-key")
        self.assertEqual(field_value(sonarr, "prowlarrUrl"), "http://gluetun:9696")
        self.assertEqual(field_value(radarr, "baseUrl"), "http://radarr:7878")
        self.assertEqual(field_value(prowlarr.proxies[0], "host"), "http://127.0.0.1:8191")
        self.assertTrue(seerr.seerr_initialized)
        self.assertEqual(seerr.seerr_setup["hostname"], "jellyfin")
        self.assertEqual(seerr.seerr_setup["serverType"], 2)
        self.assertNotIn("hostname", seerr.seerr_user)
        self.assertEqual(seerr.seerr_services["sonarr"][0]["port"], 8989)
        self.assertEqual(seerr.seerr_services["sonarr"][0]["activeDirectory"], "/tv")
        self.assertTrue(seerr.seerr_services["sonarr"][0]["enableSeasonFolders"])
        self.assertEqual(seerr.seerr_services["radarr"][0]["activeDirectory"], "/movies")
        self.assertEqual(seerr.seerr_services["radarr"][0]["minimumAvailability"], "released")
        self.assertEqual(seerr.seerr_services["radarr"][0]["apiKey"], "radarr-key")
        self.assertEqual(len(seerr.seerr_services["sonarr"]), 1)
        self.assertEqual(len(seerr.seerr_services["radarr"]), 1)

    def test_direct_mode_uses_container_hostnames(self):
        states = self._run_configure("0")
        self.assertNotIn("current_network_interface", states["qbit"].qbit_prefs)
        self.assertEqual(field_value(states["sonarr"].clients[0], "host"), "qbittorrent")
        sonarr = next(item for item in states["prowlarr"].applications if item["name"] == "Sonarr")
        self.assertEqual(field_value(sonarr, "prowlarrUrl"), "http://prowlarr:9696")
        self.assertEqual(field_value(states["prowlarr"].proxies[0], "host"), "http://flaresolverr:8191")

    def test_auth_patch_relaxes_servarr_login(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.xml"
            path.write_text(
                "<Config><ApiKey>abc</ApiKey><AuthenticationMethod>Forms</AuthenticationMethod></Config>"
            )
            stacklib.patch_servarr_auth(path)
            text = path.read_text()
            self.assertIn("abc", text)
            self.assertIn("External", text)
            self.assertIn("DisabledForLocalAddresses", text)

    def _cleared_settings_env(self):
        keys = [item.name.upper() for item in fields(stacklib.Settings)]
        saved = {key: os.environ.pop(key) for key in keys if key in os.environ}
        self.addCleanup(lambda: os.environ.update(saved))

    def test_cloudflare_without_token_explains_the_next_command(self):
        self._cleared_settings_env()
        with TemporaryDirectory() as tmp:
            with unittest.mock.patch.object(stacklib, "ENV_PATH", Path(tmp) / ".env"):
                settings, _extras = stacklib.collect_settings(assume_yes=True, no_vpn=True, remote="cloudflare")
                with self.assertRaises(stacklib.SetupError) as raised:
                    stacklib.require_cloudflare_credentials(settings)
        text = str(raised.exception)
        self.assertIn("api-tokens", text)
        self.assertIn("CLOUDFLARE_API_TOKEN", text)
        self.assertIn("Cloudflare Tunnel", text)
        self.assertIn("--remote forward", text)
        self.assertIn("--remote tailscale", text)
        self.assertIn("--no-vpn", text)

    def test_unknown_remote_mode_lists_the_three_choices(self):
        self._cleared_settings_env()
        with TemporaryDirectory() as tmp:
            with unittest.mock.patch.object(stacklib, "ENV_PATH", Path(tmp) / ".env"):
                with self.assertRaises(stacklib.SetupError) as raised:
                    stacklib.collect_settings(assume_yes=True, no_vpn=True, remote="magic")
        self.assertIn("--remote cloudflare", str(raised.exception))
        self.assertIn("--remote forward", str(raised.exception))

    def test_hostname_accepts_a_pasted_url(self):
        self._cleared_settings_env()
        os.environ["CLOUDFLARE_API_TOKEN"] = "token"
        os.environ["CLOUDFLARE_HOSTNAME"] = "https://Watch.Example.com/play"
        self.addCleanup(lambda: os.environ.pop("CLOUDFLARE_API_TOKEN", None))
        self.addCleanup(lambda: os.environ.pop("CLOUDFLARE_HOSTNAME", None))
        with TemporaryDirectory() as tmp:
            with unittest.mock.patch.object(stacklib, "ENV_PATH", Path(tmp) / ".env"):
                settings, _extras = stacklib.collect_settings(assume_yes=True, no_vpn=True, remote="cloudflare")
        self.assertEqual(settings.cloudflare_hostname, "watch.example.com")
        stacklib.require_cloudflare_credentials(settings)

    def test_compose_adds_cloudflared_only_for_a_tunnel(self):
        plain = stacklib.render_compose(False)
        tunneled = stacklib.render_compose(True, cloudflare=True)
        self.assertNotIn("cloudflared", plain)
        self.assertIn("cloudflare/cloudflared:latest", tunneled)
        self.assertIn("TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}", tunneled)
        self.assertIn("container_name: cloudflared", tunneled)

    def test_credentials_list_public_urls_and_keep_downloads_local(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "credentials.txt"
            with unittest.mock.patch.object(stacklib, "CREDENTIALS_PATH", path):
                settings = stacklib.Settings(
                    admin_user="admin",
                    admin_password="secret",
                    use_vpn="0",
                    public_jellyfin_url="https://watch.example.com",
                    public_seerr_url="https://requests.example.com",
                )
                stacklib.write_credentials(settings, {}, "Cloudflare Tunnel is attached.")
            text = path.read_text(encoding="utf-8")
            self.assertIn("https://watch.example.com", text)
            self.assertIn("https://requests.example.com", text)
            self.assertIn("stay on this computer", text)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_cloudflare_error_tells_you_which_permission_to_add(self):
        message = stacklib.cloudflare_error_message(
            403,
            {"errors": [{"message": "Authentication error"}]},
            "POST /accounts/x/cfd_tunnel",
        )
        self.assertIn("Cloudflare Tunnel", message)
        self.assertIn("DNS", message)
        self.assertIn("api-tokens", message)

    def test_missing_zone_names_the_hostname_and_the_dashboard(self):
        message = stacklib.zone_missing_message("watch.example.com")
        self.assertIn("watch.example.com", message)
        self.assertIn("dash.cloudflare.com", message)
        self.assertIn("nameservers", message)

    def test_provision_cloudflare_creates_tunnel_dns_and_is_safe_to_repeat(self):
        settings = stacklib.Settings(
            remote_access="cloudflare",
            cloudflare_api_token="token",
            cloudflare_hostname="watch.example.com",
            use_vpn="0",
        )
        fake = FakeCloudflare()
        note = stacklib.provision_cloudflare(settings, call=fake)
        stacklib.provision_cloudflare(settings, call=fake)
        posts = [call for call in fake.calls if call[0] == "POST" and call[1].endswith("/cfd_tunnel")]
        self.assertEqual(len(posts), 1)
        self.assertEqual(settings.cloudflare_tunnel_token, "connector-token")
        self.assertEqual(settings.public_jellyfin_url, "https://watch.example.com")
        self.assertEqual(settings.public_seerr_url, "https://requests.example.com")
        self.assertIn("http://jellyfin:8096", json.dumps(fake.config))
        self.assertIn("http://seerr:5055", json.dumps(fake.config))
        self.assertIn("http_status:404", json.dumps(fake.config))
        names = {record["name"] for record in fake.records}
        self.assertEqual(names, {"watch.example.com", "requests.example.com"})
        self.assertTrue(all(record["content"] == "tun-1.cfargotunnel.com" for record in fake.records))
        self.assertIn("--remote forward", note)

    def test_provision_refuses_to_replace_a_different_dns_record(self):
        settings = stacklib.Settings(
            remote_access="cloudflare",
            cloudflare_api_token="token",
            cloudflare_hostname="watch.example.com",
            cloudflare_seerr_hostname="off",
        )
        fake = FakeCloudflare()
        fake.records.append({"id": "rec-a", "type": "A", "name": "watch.example.com", "content": "192.0.2.9"})
        with self.assertRaises(stacklib.SetupError) as raised:
            stacklib.provision_cloudflare(settings, call=fake)
        self.assertIn("watch.example.com", str(raised.exception))
        self.assertIn("DNS", str(raised.exception))
        self.assertEqual(settings.cloudflare_tunnel_id, "tun-1")

    def test_missing_zone_stops_with_the_domain_instructions(self):
        settings = stacklib.Settings(
            cloudflare_api_token="token",
            cloudflare_hostname="watch.example.com",
        )
        fake = FakeCloudflare(zones={})
        with self.assertRaises(stacklib.SetupError) as raised:
            stacklib.provision_cloudflare(settings, call=fake)
        self.assertIn("watch.example.com", str(raised.exception))
        self.assertIn("Active", str(raised.exception))

    def test_several_cloudflare_accounts_ask_for_an_id(self):
        settings = stacklib.Settings(cloudflare_api_token="token", cloudflare_hostname="watch.example.com")
        fake = FakeCloudflare(accounts=[{"id": "a", "name": "Home"}, {"id": "b", "name": "Work"}])
        with self.assertRaises(stacklib.SetupError) as raised:
            stacklib.provision_cloudflare(settings, call=fake)
        text = str(raised.exception)
        self.assertIn("CLOUDFLARE_ACCOUNT_ID", text)
        self.assertIn("Home", text)
        self.assertIn("Work", text)

    def test_upnp_control_url_is_read_from_the_router_description(self):
        xml = """
        <root xmlns="urn:schemas-upnp-org:device-1-0">
          <device><serviceList><service>
            <serviceType>urn:schemas-upnp-org:service:WANIPConnection:1</serviceType>
            <controlURL>/ctl/IPConn</controlURL>
          </service></serviceList></device>
        </root>
        """
        control, service = stacklib.parse_upnp_service(xml, "http://192.168.1.1:49000/rootDesc.xml")
        self.assertEqual(control, "http://192.168.1.1:49000/ctl/IPConn")
        self.assertIn("WANIPConnection", service)

    def test_port_forward_success_publishes_the_router_address(self):
        settings = stacklib.Settings(use_vpn="0", remote_access="forward")
        seen = []

        def discover():
            return "http://192.168.1.1:49000/rootDesc.xml"

        def exchange(url, data=None, headers=None):
            if data is None:
                return 200, """
                <root><device><serviceList><service>
                  <serviceType>urn:schemas-upnp-org:service:WANIPConnection:1</serviceType>
                  <controlURL>/ctl/IPConn</controlURL>
                </service></serviceList></device></root>
                """
            seen.append(data)
            if b"GetExternalIPAddress" in data:
                return 200, "<root><NewExternalIPAddress>203.0.113.8</NewExternalIPAddress></root>"
            return 200, ""

        note = stacklib.forward_ports(
            settings,
            discover=discover,
            exchange=exchange,
            local_ip="192.168.1.20",
        )
        self.assertEqual(settings.public_jellyfin_url, "http://203.0.113.8:8096")
        self.assertEqual(settings.public_seerr_url, "http://203.0.113.8:5055")
        mapped = b"".join(seen)
        self.assertIn(b"192.168.1.20", mapped)
        self.assertIn(b"8096", mapped)
        self.assertIn(b"5055", mapped)
        self.assertIn("phone", note)

    def test_port_forward_without_upnp_prints_the_manual_steps(self):
        settings = stacklib.Settings(use_vpn="0", remote_access="forward", jellyfin_port="8096", seerr_port="5055")
        note = stacklib.forward_ports(
            settings,
            discover=lambda: None,
            exchange=lambda *args, **kwargs: (500, ""),
            local_ip="192.168.1.20",
            lookup_public_ip=lambda: "203.0.113.9",
        )
        self.assertIn("192.168.1.20", note)
        self.assertIn("8096", note)
        self.assertIn("5055", note)
        self.assertIn("http://203.0.113.9:8096", note)
        self.assertIn("ufw allow", note)
        self.assertIn("stay on this computer", note)
        self.assertEqual(settings.public_jellyfin_url, "")

    def test_carrier_nat_sends_you_to_the_tunnel(self):
        settings = stacklib.Settings(use_vpn="0", remote_access="forward")

        def exchange(url, data=None, headers=None):
            if data is None:
                return 200, """
                <root><device><serviceList><service>
                  <serviceType>urn:schemas-upnp-org:service:WANIPConnection:1</serviceType>
                  <controlURL>/ctl/IPConn</controlURL>
                </service></serviceList></device></root>
                """
            if b"GetExternalIPAddress" in data:
                return 200, "<root><NewExternalIPAddress>100.64.1.5</NewExternalIPAddress></root>"
            return 200, ""

        note = stacklib.forward_ports(
            settings,
            discover=lambda: "http://192.168.1.1/desc.xml",
            exchange=exchange,
            local_ip="192.168.1.20",
        )
        self.assertIn("--remote tailscale", note)
        self.assertNotIn("domain on Cloudflare", note)
        self.assertEqual(settings.public_jellyfin_url, "")

    def test_tailscale_running_publishes_its_address(self):
        settings = stacklib.Settings(use_vpn="0", remote_access="tailscale")
        note = stacklib.describe_tailscale(
            settings,
            {
                "BackendState": "Running",
                "Self": {
                    "DNSName": "lounge.tailnet.ts.net.",
                    "TailscaleIPs": ["100.90.1.2", "fd7a:115c:a1e0::1"],
                },
            },
        )
        self.assertEqual(settings.public_jellyfin_url, "http://100.90.1.2:8096")
        self.assertEqual(settings.public_seerr_url, "http://100.90.1.2:5055")
        self.assertIn("lounge.tailnet.ts.net", note)
        self.assertIn("same account", note)

    def test_tailscale_login_prints_the_sign_in_link(self):
        settings = stacklib.Settings(use_vpn="0", remote_access="tailscale")
        note = stacklib.describe_tailscale(
            settings,
            {"BackendState": "NeedsLogin", "AuthURL": "https://login.tailscale.com/a/abc123"},
        )
        self.assertIn("https://login.tailscale.com/a/abc123", note)
        self.assertIn("--remote tailscale", note)
        self.assertEqual(settings.public_jellyfin_url, "")

    def test_tailscale_missing_prints_the_install_step(self):
        settings = stacklib.Settings(use_vpn="0", remote_access="tailscale")
        note = stacklib.describe_tailscale(settings, None, installed=False)
        self.assertIn("tailscale.com/download", note)
        self.assertIn("sudo tailscale up", note)
        self.assertEqual(settings.public_jellyfin_url, "")

    def test_private_and_public_addresses(self):
        self.assertFalse(stacklib.is_public_ip("192.168.1.4"))
        self.assertFalse(stacklib.is_public_ip("10.1.1.1"))
        self.assertFalse(stacklib.is_public_ip("100.64.0.8"))
        self.assertTrue(stacklib.is_public_ip("203.0.113.8"))


class FakeCloudflare:
    def __init__(self, accounts=None, zones=None):
        self.accounts = accounts if accounts is not None else [{"id": "acct", "name": "Home"}]
        self.zones = {"example.com": [{"id": "zone1", "name": "example.com"}]} if zones is None else zones
        self.calls = []
        self.tunnels = []
        self.records = []
        self.config = None

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        parsed = urllib.parse.urlsplit(path)
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/accounts":
            return self.accounts
        if parsed.path == "/zones":
            return self.zones.get(query.get("name", [""])[0], [])
        if parsed.path == "/accounts/acct/cfd_tunnel" and method == "GET":
            return list(self.tunnels)
        if parsed.path == "/accounts/acct/cfd_tunnel" and method == "POST":
            tunnel = {"id": "tun-1", "name": body["name"], "token": "connector-token"}
            self.tunnels.append({"id": "tun-1", "name": body["name"]})
            return tunnel
        if parsed.path.endswith("/token"):
            return "connector-token"
        if parsed.path.endswith("/configurations"):
            self.config = body
            return {}
        if parsed.path == "/zones/zone1/dns_records" and method == "GET":
            name = query.get("name", [""])[0]
            return [item for item in self.records if item["name"] == name]
        if parsed.path == "/zones/zone1/dns_records" and method == "POST":
            item = dict(body, id=f"rec-{len(self.records) + 1}")
            self.records.append(item)
            return item
        raise AssertionError((method, path))


if __name__ == "__main__":
    unittest.main()
