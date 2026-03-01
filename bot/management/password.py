import os
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

encryption_key = get_random_bytes(16)

def encrypt_password(password: str):
    nonce = os.urandom(12)
    cipher = AES.new(encryption_key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(password.encode('utf-8'))
    encrypted_payload = nonce + tag + ciphertext
    return encrypted_payload

def decrypt_password(encrypted_password: bytes) -> str:
    nonce = encrypted_password[:12]
    tag = encrypted_password[12:28]
    password = encrypted_password[28:]
    
    cipher = AES.new(encryption_key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(password, tag).decode('utf-8')