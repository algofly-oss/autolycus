"""Persistent cookie and durable session regressions; no external services."""
import datetime
import os
import sys
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from starlette.requests import Request
from starlette.responses import Response
from shared.modules.auth_session import SESSION_SECONDS, resolve_session, set_session_cookie


class SessionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.redis = Mock()
        self.redis.pipeline.return_value.execute.return_value = [None, -2, None]
        self.db = SimpleNamespace(user_sessions=SimpleNamespace(find_one=AsyncMock(return_value=None), update_one=AsyncMock()),
                                  users=SimpleNamespace(find_one=AsyncMock(return_value={"_id": "exists"})))
        self.factory = patch.dict(sys.modules, {"shared.factory": SimpleNamespace(db=self.db, redis=self.redis)})
        self.factory.start()
        self.addCleanup(self.factory.stop)

    async def test_active_cache_avoids_database_reads(self):
        self.redis.pipeline.return_value.execute.return_value = [b"user", SESSION_SECONDS - 10, b"1"]
        self.assertEqual(await resolve_session("token"), (b"user", True))
        self.db.user_sessions.find_one.assert_not_awaited()
        self.redis.expire.assert_called_once_with("token", SESSION_SECONDS)

    async def test_legacy_session_upgrades_without_changing_token(self):
        self.redis.pipeline.return_value.execute.return_value = [b"user", -1, None]
        self.assertEqual(await resolve_session("legacy"), (b"user", True))
        self.redis.set.assert_any_call("legacy", b"user", ex=SESSION_SECONDS)
        self.db.user_sessions.update_one.assert_awaited_once()

    async def test_durable_session_restores_evicted_cache(self):
        self.db.user_sessions.find_one.return_value = {
            "user_id": "507f1f77bcf86cd799439011", "revoked_at": None,
            "expires_at": datetime.datetime.utcnow() + datetime.timedelta(days=1),
        }
        result, renewed = await resolve_session("cookie-survived")
        self.assertEqual(result, b"507f1f77bcf86cd799439011")
        self.assertTrue(renewed)
        self.redis.set.assert_any_call("cookie-survived", b"507f1f77bcf86cd799439011", ex=SESSION_SECONDS)

    async def test_returning_before_inactivity_expiry_renews_full_lifetime(self):
        now = datetime.datetime.utcnow()
        inactive_seconds = SESSION_SECONDS - 24 * 3600
        self.redis.pipeline.return_value.execute.return_value = [b"user", SESSION_SECONDS - inactive_seconds, None]
        self.db.user_sessions.find_one.return_value = {
            "user_id": "user", "revoked_at": None,
            "last_accessed_at": now - datetime.timedelta(seconds=inactive_seconds),
            "expires_at": now + datetime.timedelta(seconds=SESSION_SECONDS - inactive_seconds),
        }
        self.assertEqual(await resolve_session("returning-visitor"), (b"user", True))
        self.redis.set.assert_any_call("returning-visitor", b"user", ex=SESSION_SECONDS)
        renewal = self.db.user_sessions.update_one.call_args.args[1]["$set"]["expires_at"]
        self.assertGreaterEqual(renewal, now + datetime.timedelta(seconds=SESSION_SECONDS))

    async def test_revoked_or_expired_sessions_never_recover(self):
        for record in ({"revoked_at": datetime.datetime.utcnow()},
                       {"revoked_at": None, "expires_at": datetime.datetime.utcnow() - datetime.timedelta(seconds=1)}):
            self.db.user_sessions.find_one.return_value = record
            self.assertEqual(await resolve_session("invalid"), (None, False))
        self.redis.set.assert_not_called()

    async def test_database_outage_is_not_reported_as_logout(self):
        self.db.user_sessions.find_one.side_effect = RuntimeError("database unavailable")
        with self.assertRaises(RuntimeError):
            await resolve_session("existing-cookie")

    async def test_socket_recovery_does_not_extend_cookie_lifetime(self):
        self.db.user_sessions.find_one.return_value = {
            "user_id": "507f1f77bcf86cd799439011", "revoked_at": None,
            "expires_at": datetime.datetime.utcnow() + datetime.timedelta(seconds=100),
        }
        _, renewed = await resolve_session("socket", renew=False)
        self.assertFalse(renewed)
        self.assertLessEqual(self.redis.set.call_args.kwargs["ex"], 100)
        self.db.user_sessions.update_one.assert_not_awaited()

    def test_cookie_is_persistent_httponly_and_secure_on_https(self):
        for scheme in ("http", "https"):
            request = Request({"type": "http", "method": "GET", "path": "/", "scheme": scheme,
                               "headers": [], "server": ("example.test", 443), "query_string": b""})
            response = Response()
            with patch.dict(os.environ, {"SESSION_COOKIE_SECURE": "auto"}):
                set_session_cookie(response, request, "opaque-token")
            cookie = next(iter(SimpleCookie(response.headers["set-cookie"]).values()))
            self.assertEqual(int(cookie["max-age"]), SESSION_SECONDS)
            self.assertTrue(cookie["expires"])
            self.assertTrue(cookie["httponly"])
            self.assertEqual(cookie["samesite"], "lax")
            self.assertEqual(bool(cookie["secure"]), scheme == "https")
            self.assertEqual(cookie["path"], "/")


if __name__ == "__main__":
    unittest.main()
