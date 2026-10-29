import os
import unittest

os.environ["FLASK_CONFIG"] = "development"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["FLASK_DEBUG"] = "false"
os.environ["CORS_ORIGINS"] = "http://127.0.0.1:8082"
os.environ["SOCKETIO_CORS_ORIGINS"] = "http://127.0.0.1:8082"

from app import create_app
from flask_construction.auth import generate_token
from flask_construction.models import User, db


class UserDisableTest(unittest.TestCase):
    """后台用户管理 - 账号启用/禁用功能"""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True, SECRET_KEY="test-secret")

    def setUp(self):
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            admin = User(username="admin", nickname="管理员", role="admin")
            admin.set_password("admin123")
            another_admin = User(username="admin2", nickname="管理员2", role="admin")
            another_admin.set_password("admin2pass")
            worker = User(username="worker", nickname="工人", role="user")
            worker.set_password("worker123")
            db.session.add_all([admin, another_admin, worker])
            db.session.commit()
            self.admin_id = admin.id
            self.another_admin_id = another_admin.id
            self.user_id = worker.id
            self.user_token = generate_token(worker.id)

        self.admin_client = self.app.test_client()
        self.user_client = self.app.test_client()
        self.anon_client = self.app.test_client()

    # ---------- 辅助方法 ----------

    def _login_admin(self, client=None, username="admin", password="admin123"):
        client = client or self.admin_client
        return client.post(
            "/admin/login", data={"username": username, "password": password}
        )

    def _toggle(self, user_id, client=None):
        client = client or self.admin_client
        return client.post(f"/admin/users/{user_id}/toggle", follow_redirects=True)

    def _login_user(self, client=None):
        client = client or self.anon_client
        return client.post(
            "/api/login", json={"username": "worker", "password": "worker123"}
        )

    def _user_is_active(self, user_id):
        with self.app.app_context():
            user = db.session.get(User, user_id)
            return bool(user.is_active)

    # ---------- 登录拦截 ----------

    def test_disabled_user_cannot_login(self):
        self._login_admin()
        self._toggle(self.user_id)

        response = self._login_user()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json().get("error"), "Account disabled")

    def test_old_token_rejected_after_disable(self):
        self._login_admin()
        self._toggle(self.user_id)

        response = self.anon_client.get(
            "/api/me", headers={"Authorization": f"Bearer {self.user_token}"}
        )

        self.assertEqual(response.status_code, 401)

    def test_existing_session_invalidated_after_disable(self):
        self.assertEqual(self._login_user(self.user_client).status_code, 200)
        self.assertEqual(self.user_client.get("/api/me").status_code, 200)

        self._login_admin()
        self._toggle(self.user_id)

        self.assertEqual(self.user_client.get("/api/me").status_code, 401)

    def test_reenable_restores_login_and_token(self):
        self._login_admin()
        self._toggle(self.user_id)
        self._toggle(self.user_id)  # 再次切换 = 启用

        self.assertTrue(self._user_is_active(self.user_id))
        self.assertEqual(self._login_user().status_code, 200)
        response = self.anon_client.get(
            "/api/me", headers={"Authorization": f"Bearer {self.user_token}"}
        )
        self.assertEqual(response.status_code, 200)

    # ---------- 权限与保护 ----------

    def test_toggle_requires_admin(self):
        self.assertEqual(self._login_user(self.user_client).status_code, 200)

        response = self._toggle(self.user_id, client=self.user_client)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(self._user_is_active(self.user_id))

    def test_toggle_requires_login(self):
        response = self.anon_client.post(f"/admin/users/{self.user_id}/toggle")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(self._user_is_active(self.user_id))

    def test_cannot_disable_default_admin(self):
        self._login_admin()

        response = self._toggle(self.admin_id)

        self.assertIn("不能禁用默认管理员账户", response.get_data(as_text=True))
        self.assertTrue(self._user_is_active(self.admin_id))

    def test_cannot_disable_self(self):
        self._login_admin(self.user_client, username="admin2", password="admin2pass")

        response = self._toggle(self.another_admin_id, client=self.user_client)

        self.assertIn("不能禁用当前登录的账号", response.get_data(as_text=True))
        self.assertTrue(self._user_is_active(self.another_admin_id))

    def test_disabled_admin_cannot_access_admin_pages(self):
        self._login_admin()
        self._toggle(self.admin_id)  # 默认管理员受保护，禁用不会生效
        self.assertTrue(self._user_is_active(self.admin_id))

        another_client = self.app.test_client()
        self._login_admin(another_client, username="admin2", password="admin2pass")
        with self.app.app_context():
            admin2 = db.session.get(User, self.another_admin_id)
            admin2.is_active = False
            db.session.commit()

        response = another_client.get("/admin/users")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login", response.headers.get("Location", ""))

    # ---------- 后台列表 / 编辑表单 ----------

    def test_user_list_shows_status(self):
        self._login_admin()
        self._toggle(self.user_id)

        body = self.admin_client.get("/admin/users").get_data(as_text=True)

        self.assertIn("已禁用", body)
        self.assertIn("已启用", body)
        self.assertIn(f"/admin/users/{self.user_id}/toggle", body)

    def test_user_list_hides_toggle_for_default_admin(self):
        self._login_admin()

        body = self.admin_client.get("/admin/users").get_data(as_text=True)

        self.assertNotIn(f"/admin/users/{self.admin_id}/toggle", body)

    def test_edit_form_can_set_inactive(self):
        self._login_admin()

        response = self.admin_client.post(
            f"/admin/users/{self.user_id}/edit",
            data={"nickname": "工人", "role": "user", "is_active": "0", "password": ""},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(self._user_is_active(self.user_id))

        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            self.assertFalse(user.is_active)

    def test_edit_form_cannot_disable_default_admin(self):
        self._login_admin()

        response = self.admin_client.post(
            f"/admin/users/{self.admin_id}/edit",
            data={"nickname": "管理员", "role": "admin", "is_active": "0", "password": ""},
            follow_redirects=True,
        )

        self.assertIn("不能禁用默认管理员账户", response.get_data(as_text=True))
        self.assertTrue(self._user_is_active(self.admin_id))

    def test_create_user_defaults_to_active(self):
        self._login_admin()

        self.admin_client.post(
            "/admin/users/create",
            data={"username": "newbie", "password": "newbie123", "nickname": "", "role": "user"},
        )

        with self.app.app_context():
            newbie = User.query.filter_by(username="newbie").first()
            self.assertIsNotNone(newbie)
            self.assertTrue(newbie.is_active)

    # ---------- REST API ----------

    def test_list_users_includes_is_active(self):
        self._login_admin()
        self._toggle(self.user_id)

        with self.app.app_context():
            token = generate_token(self.admin_id)
        response = self.admin_client.get(
            "/api/users", headers={"Authorization": f"Bearer {token}"}
        )

        self.assertEqual(response.status_code, 200)
        payload = {u["username"]: u for u in response.get_json()}
        self.assertFalse(payload["worker"]["is_active"])
        self.assertTrue(payload["admin"]["is_active"])

    def test_api_update_user_can_disable_and_enable(self):
        with self.app.app_context():
            token = generate_token(self.admin_id)
        headers = {"Authorization": f"Bearer {token}"}

        response = self.admin_client.put(
            f"/api/users/{self.user_id}", json={"is_active": False}, headers=headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json().get("is_active"))
        self.assertEqual(self._login_user().status_code, 403)

        response = self.admin_client.put(
            f"/api/users/{self.user_id}", json={"is_active": True}, headers=headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._login_user().status_code, 200)

    def test_api_cannot_disable_default_admin(self):
        with self.app.app_context():
            token = generate_token(self.admin_id)
        response = self.admin_client.put(
            f"/api/users/{self.admin_id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(self._user_is_active(self.admin_id))


if __name__ == "__main__":
    unittest.main()
