import bcrypt
from backend.core.security import verify_password, hash_password

def test_bcrypt():
    passwd = "password123"
    hashed = hash_password(passwd)
    print("Hashed password:", hashed)
    
    # Try verifying
    try:
        match = verify_password(passwd, hashed)
        print("Verification result:", match)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_bcrypt()
