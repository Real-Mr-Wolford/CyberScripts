import random as r
import hashlib as h
import os

filename = input("Enter the filename to shred: ")
def hash_file(filename):
    sha256_hash = h.sha256()
    with open(filename,"rb") as f:
        for byte_block in iter(lambda: f.read(4096),b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()
originalHash = hash_file(filename)
print(f"Original file hash: {originalHash}")
count = 0
def shredder():
    if count==0:
        print("\n--- !!! WARNING !!! ---")
        print(f"You are about to IRREVERSIBLY SHRED: {filename}")
        print("This will overwrite the file with hex-bloat and delete it forever.")
        confirm = input("To proceed, type 'SHRED': ")

        if confirm != "SHRED":
            print("Safety triggered. Aborting destruction.")
            return
    encrypt = []
    ranCharHolder ={}
    def shred(file):
        
      
        for i,char in enumerate(file):
            if char not in ranCharHolder:
                ranCharHolder[char] = r.randint(1,5000)
            enValue = ranCharHolder[char]+(i*123)
            encrypt.append(hex(enValue))
            enValue = enValue*r.randint(0,128)
            encrypt.append(hex(enValue))
        
        
        with open(filename, 'rb+') as shredd_file:
            shredd_file.write(' '.join(encrypt).encode('utf-8'))
        print(encrypt)
        return encrypt
    
    try:
        with open(filename, 'rb') as file:
            content = file.read()  
            shred(content) 
        print(content)
    except FileNotFoundError:
        print("File not found. Please check the filename and try again.")
        

    


for i in range(2):
    shredder()
    count+=1
newHash = hash_file(filename)
print(f"New file hash: {newHash}")

if originalHash != newHash:
    print("Successfully shredded file")
else:
    print("Shredding failed. ")
try:
    os.remove(filename)
    print(f"{filename} has been shredded and deleted.")

except FileNotFoundError:
    print("File not found.")
except PermissionError:
    print("Permission denied. Unable to delete the file.")
except Exception as e:
    print(f"An error occurred: {e}")
