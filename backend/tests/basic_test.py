from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import Base, engine, get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# Setup in-memory DB for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine_test = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)

Base.metadata.drop_all(bind=engine_test)
Base.metadata.create_all(bind=engine_test)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to CiteGuard API"}

def test_submission_and_status():
    # 1. Submit
    bib_content = b"@article{test, title={Test Paper}, author={Author}, year={2023}}"
    files = {
        'bib_file': ('test.bib', bib_content, 'text/plain')
    }
    
    response = client.post("/api/v1/submit/", files=files)
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    task_id = data["task_id"]
    print(f"Task created: {task_id}")

    # 2. Check Status
    response = client.get(f"/api/v1/status/{task_id}")
    assert response.status_code == 200
    status_data = response.json()
    assert status_data["id"] == task_id
    assert status_data["status"] in ["pending", "processing", "completed"]
    print(f"Task status: {status_data['status']}")

    # 3. Check Details
    response = client.get(f"/api/v1/status/{task_id}/details")
    assert response.status_code == 200
    details = response.json()
    assert details["task_id"] == task_id
    assert isinstance(details["jobs"], list)

if __name__ == "__main__":
    try:
        test_read_main()
        test_submission_and_status()
        print("✅ ALL TESTS PASSED")
        # clean up
        if os.path.exists("./test.db"):
            os.remove("./test.db")
    except Exception as e:
        print(f"❌ TESTS FAILED: {e}")
        exit(1)
