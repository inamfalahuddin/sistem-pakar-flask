import hashlib

password = "El*yoh123"
password = hashlib.sha256(password.encode()) 
print(password.hexdigest())
