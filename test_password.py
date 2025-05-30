#!/usr/bin/env python3
import bcrypt

# The hash from the database
hash_from_db = "$2b$12$4J676KZaKzMyzG3P/EooB.0STfOazrhv3zcKZkR/sfsZ66utFP4UK"

# Test passwords
passwords = ["password", "test123", "testuser", "test", "12345678"]

print("Testing passwords against hash...")
for password in passwords:
    if bcrypt.checkpw(password.encode('utf-8'), hash_from_db.encode('utf-8')):
        print(f"✅ Password '{password}' matches!")
    else:
        print(f"❌ Password '{password}' does not match")