from src.core.database import DatabaseManager


def test_database_initialization(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    dm = DatabaseManager(db_path=str(db_file))
    # creating a user should work
    user_id = dm.create_user("Test", "test@example.com")
    assert isinstance(user_id, int)
