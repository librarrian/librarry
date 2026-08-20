from flask import wrappers


class ImmediateResponse(Exception):
    def __init__(self, response: wrappers.Response, code: int):
        self.response = (response, code)