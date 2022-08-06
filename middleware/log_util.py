from io import StringIO
import logging

class StringHandler(logging.StreamHandler):
    str_io = StringIO()
    def __init__(self):
        logging.StreamHandler.__init__(self, StringHandler.str_io)
