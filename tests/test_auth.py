from app.auth import password_hash, verify_login
from app.config import Settings


def test_login_verifies_argon2_hash(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        podcast_dir=tmp_path / "podcasts",
        admin_username="operator",
        admin_password_hash=password_hash.hash("correct horse battery staple"),
    )
    assert verify_login(settings, "operator", "correct horse battery staple")
    assert not verify_login(settings, "operator", "wrong")
    assert not verify_login(settings, "someone", "correct horse battery staple")

