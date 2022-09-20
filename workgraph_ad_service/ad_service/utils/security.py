from Crypto.Cipher import AES
from Crypto import Random
import codecs
import yaml
import os

with open(os.getcwd() + "/security_secrets.yaml", 'r') as stream:
    secrets = yaml.load(stream)
encryption_key = secrets['ENCRYPTION_KEY']


def encrypt(data):
    iv = Random.new().read(AES.block_size)
    cipher = AES.new(encryption_key, AES.MODE_CFB, iv)
    msg = iv + cipher.encrypt(str(data))
    msg = codecs.encode(msg, 'hex_codec')
    return msg


def decrypt(data):
    iv = data[:32]
    iv = codecs.decode(iv, 'hex_codec')
    cipher = AES.new(encryption_key, AES.MODE_CFB, iv)
    decrypted_data = cipher.decrypt(codecs.decode(data, 'hex_codec'))[len(iv):]
    return decrypted_data
