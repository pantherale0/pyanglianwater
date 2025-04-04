import hashlib
import hmac
import os
import json
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64

plaintext = 171260490
key = "d8ssmJ1c$qZq441%nC^u0!P!w96K@RdF"

def pbkdf2(password, salt, key_length=32, iterations=100, hash_function=hashlib.sha256):
    """PBKDF2 with SHA256 and 100 iterations (matching the JS)."""
    derived_key = b''
    counter = 1

    while len(derived_key) < key_length:
        hmac_obj = hmac.new(password, salt + counter.to_bytes(4, 'big'), hash_function)
        u = hmac_obj.digest()
        result = u

        for _ in range(1, iterations):
            hmac_obj = hmac.new(password, u, hash_function)
            u = hmac_obj.digest()
            result = bytes(x ^ y for x, y in zip(result, u))

        derived_key += result
        counter += 1

    return derived_key[:key_length]

def encrypt_aes256(password_str, data):
    """Encrypts data using AES-256 with PBKDF2 key derivation."""
    password = password_str.encode('utf-8')
    salt = os.urandom(16)  # Generate 16-byte random salt
    iv = os.urandom(16)  # Generate 16-byte random IV

    if isinstance(data, (int, float)):
        data_bytes = str(data).encode('utf-8')
    elif isinstance(data, (dict, list)):
        data_bytes = json.dumps(data).encode('utf-8')
    elif isinstance(data, str):
        data_bytes = data.encode('utf-8')
    else:
        data_bytes = data #if byte array, or other accepted type.

    key = pbkdf2(password, salt)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_data = pad(data_bytes, AES.block_size)
    ciphertext = cipher.encrypt(padded_data)

    return base64.b64encode(salt + iv + ciphertext).decode('utf-8')

def decrypt_aes256(password_str, encrypted_base64):
    """Decrypts AES-256 encrypted data."""
    password = password_str.encode('utf-8')
    encrypted_bytes = base64.b64decode(encrypted_base64)
    salt = encrypted_bytes[:16]
    iv = encrypted_bytes[16:32]
    ciphertext = encrypted_bytes[32:]

    key = pbkdf2(password, salt)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_data = cipher.decrypt(ciphertext)
    unpadded_data = unpad(padded_data, AES.block_size)

    try:
        return json.loads(unpadded_data.decode('utf-8')) # attempt to decode json
    except json.JSONDecodeError:
        try:
            return unpadded_data.decode('utf-8') # attempt to decode as string
        except UnicodeDecodeError:
            return unpadded_data # return raw bytes if all else fails.

def encrypt_aes256_as_hex(password_str, data):
    """Encrypts data using AES-256 and returns the result as a hex string."""
    encrypted_base64 = encrypt_aes256(password_str, data)
    return to_hex(encrypted_base64)

def decrypt_aes256_from_hex(password_str, encrypted_hex):
    """Decrypts AES-256 encrypted data from a hex string."""
    encrypted_base64 = from_hex(encrypted_hex)
    return decrypt_aes256(password_str, encrypted_base64)

def to_hex(base64_str):
    """Converts a base64 string to a hex string."""
    return ''.join(hex(ord(c))[2:].zfill(2) for c in base64_str)

def from_hex(hex_str):
    """Converts a hex string to a base64 string."""
    return base64.b64encode(bytes.fromhex(hex_str)).decode('utf-8')

data = encrypt_aes256_as_hex(key, plaintext)
print(f"Encrypted: {data}")
#print(f"Decrypted: {decrypt_aes256_from_hex(key, "756c424437746f67666f4564696335776d3566416437657a777a646f546d504557533062377853415936786b486b6c38324e6332364a7947475a6a6d53475475")}")
