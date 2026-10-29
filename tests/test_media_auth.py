import os
import tempfile
import unittest
from datetime import datetime, timezone

os.environ["FLASK_CONFIG"] = "development"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["FLASK_DEBUG"] = "false"
os.environ["CORS_ORIGINS"] = "http://127.0.0.1:8082"
os.environ["SOCKETIO_CORS_ORIGINS"] = "http://127.0.0.1:8082"
os.environ["PUBLIC_BASE_URL"] = "https://media.example:9304"

from app import create_app
from flask_construction.auth import generate_token
from flask_construction.media_signing import signed_media_url
from flask_construction.models import (
    ConstructionLog,
    LogPhoto,
    Project,
    User,
    db,
)


class MediaAuthenticationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upload_dir = tempfile.TemporaryDirectory()
        cls.app = create_app()
        cls.app.config.update(
            TESTING=True,
            UPLOAD_FOLDER=cls.upload_dir.name,
            SECRET_KEY="test-secret",
        )
        with cls.app.app_context():
            db.create_all()
            user = User(username="media-tester", role="user")
            user.set_password("not-used-in-tests")
            db.session.add(user)
            db.session.commit()
            cls.user_id = user.id
            cls.token = generate_token(user.id)
            project = Project(name="Test Project")
            db.session.add(project)
            db.session.flush()
            log = ConstructionLog(
                project_id=project.id,
                date=datetime.now(timezone.utc).date(),
            )
            db.session.add(log)
            db.session.flush()
            db.session.add(
                LogPhoto(
                    log_id=log.id,
                    filename="site.jpg",
                    original_filename="site.jpg",
                )
            )
            db.session.commit()
            cls.project_id = project.id
        for filename in ("site.jpg", "chat.jpg"):
            with open(os.path.join(cls.upload_dir.name, filename), "wb") as handle:
                handle.write(b"\xff\xd8\xff\xe0test-image")

    @classmethod
    def tearDownClass(cls):
        cls.upload_dir.cleanup()

    def client(self, authenticated=False):
        client = self.app.test_client()
        if authenticated:
            client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {self.token}"
        return client

    def test_photo_requires_authentication(self):
        response = self.app.test_client().get("/api/photos/site.jpg")

        self.assertEqual(response.status_code, 401)

    def test_photo_accepts_bearer_token(self):
        response = self.client(authenticated=True).get("/api/photos/site.jpg")

        self.assertEqual(response.status_code, 200)
        response.close()

    def test_photo_accepts_signed_url_for_installed_clients(self):
        with self.app.test_request_context("/"):
            photo_url = signed_media_url("photo", "site.jpg", absolute=False)
        response = self.app.test_client().get(photo_url)

        self.assertEqual(response.status_code, 200)
        response.close()

    def test_log_api_returns_signed_photo_url(self):
        response = self.client(authenticated=True).get(
            f"/api/logs?project_id={self.project_id}",
        )
        photo_url = response.get_json()[0]["photos"][0]["url"]
        response.close()

        self.assertIn("sig=", photo_url)
        self.assertIn("expires=", photo_url)
        image = self.app.test_client().get(photo_url)
        self.assertEqual(image.status_code, 200)
        image.close()

    def test_chat_image_requires_authentication(self):
        response = self.app.test_client().get("/api/chat/images/chat.jpg")

        self.assertEqual(response.status_code, 401)

    def test_chat_image_accepts_bearer_token(self):
        response = self.client(authenticated=True).get(
            "/api/chat/images/chat.jpg",
        )

        self.assertEqual(response.status_code, 200)
        response.close()

    def test_chat_image_accepts_signed_url_for_installed_clients(self):
        with self.app.test_request_context("/"):
            image_url = signed_media_url("chat", "chat.jpg", absolute=False)
        response = self.app.test_client().get(image_url)

        self.assertEqual(response.status_code, 200)
        response.close()

    def test_absolute_media_url_uses_configured_public_base(self):
        with self.app.test_request_context("/"):
            image_url = signed_media_url("chat", "chat.jpg", absolute=True)

        self.assertTrue(image_url.startswith("https://media.example:9304/"))

    def test_cors_does_not_allow_unknown_origin(self):
        response = self.app.test_client().get(
            "/api/app/version",
            headers={"Origin": "https://evil.example"},
        )

        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
        response.close()


if __name__ == "__main__":
    unittest.main()
