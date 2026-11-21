from app.db.session import Base, engine, SessionLocal
from app.models.user import User
from app.core.security import get_password_hash


# Create database tables if they do not exist
Base.metadata.create_all(bind=engine)


def seed_users():
    db = SessionLocal()

    try:
        # Create or retrieve Priya (Manager)
        manager = db.query(User).filter(
            User.email == "priya.manager@leavedesk.test"
        ).first()

        if manager is None:
            manager = User(
                name="Priya Manager",
                email="priya.manager@leavedesk.test",
                hashed_password=get_password_hash("Manager@123"),
                role="manager",
                manager_id=None
            )
            db.add(manager)
            db.flush()

        # Create or retrieve Arjun (Employee)
        arjun = db.query(User).filter(
            User.email == "arjun@leavedesk.test"
        ).first()

        if arjun is None:
            arjun = User(
                name="Arjun Employee",
                email="arjun@leavedesk.test",
                hashed_password=get_password_hash("Employee@123"),
                role="employee",
                manager_id=manager.id
            )
            db.add(arjun)

        # Create or retrieve Meera (Employee)
        meera = db.query(User).filter(
            User.email == "meera@leavedesk.test"
        ).first()

        if meera is None:
            meera = User(
                name="Meera Employee",
                email="meera@leavedesk.test",
                hashed_password=get_password_hash("Employee@123"),
                role="employee",
                manager_id=manager.id
            )
            db.add(meera)

        db.commit()

        print("Seed users created successfully!")

        for user in [manager, arjun, meera]:
            print(
                f"Name: {user.name} | "
                f"Email: {user.email} | "
                f"Role: {user.role} | "
                f"Manager ID: {user.manager_id}"
            )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_users()