from core.database import DatabaseManager


def main():
    db = DatabaseManager()
    users = db.get_all_users()
    if not users:
        db.create_user("Matteo", "matteo@example.com")
        db.create_user("Paola", "paola@example.com")
        db.setup_default_categories()
        print("Utenti e categorie di default creati.")
    else:
        print("Utenti già presenti.")


if __name__ == "__main__":
    main()
