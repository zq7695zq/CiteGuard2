import os
import sys

# Ensure backend directory is in path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import Base, engine

def reset_system():
    print(">>> Starting System Reset <<<")
    
    # 1. Clean Database Files
    files_to_remove = [
        "citeguard.db",
        "celery_broker.db", 
        "celery_results.db"
    ]
    
    print("\n1. Removing database files...")
    for filename in files_to_remove:
        if os.path.exists(filename):
            try:
                os.remove(filename)
                print(f"   [OK] Removed {filename}")
            except PermissionError:
                print(f"   [ERROR] Cannot remove {filename}. It is being used by another process.")
                print("   !!! Please STOP 'uvicorn', 'celery', and any python scripts first !!!")
                return False
            except Exception as e:
                print(f"   [ERROR] Failed to remove {filename}: {e}")
                return False
        else:
            print(f"   [SKIP] {filename} not found.")

    # 2. Re-initialize Database
    print("\n2. Re-creating database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("   [OK] Tables created successfully.")
    except Exception as e:
         print(f"   [ERROR] Failed to create tables: {e}")
         return False

    print("\n>>> System Reset Complete <<<")
    print("You can now restart Uvicorn and Celery.")
    return True

if __name__ == "__main__":
    reset_system()
