from shared.database import engine
from shared.models.training_job import TrainingJob

TrainingJob.metadata.create_all(bind=engine)

print("Database tables created.")