#pip install python-dotenv
import dotenv
import os
import sys

class Env:
    def __init__(self, path):
        dotenv.load_dotenv(verbose=True)
        self.env = path + '/.env'
    def changeENV(self, key, value):
        dotenv.set_key(self.env, key, value)
    def get(self, key):
        dotenv.load_dotenv(self.env, override=True)
        return os.environ.get(key)