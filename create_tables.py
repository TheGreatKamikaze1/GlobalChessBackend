from payment_service.app.db.base import Base
from payment_service.app.db.session import engine

# 🔴 force import models so SQLAlchemy knows them
from payment_service.app.models.payment import Payment  # noqa

print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("Done.")