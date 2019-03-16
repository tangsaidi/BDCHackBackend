from flask import Flask, render_template, flash, request, redirect
from flask_cors import CORS, cross_origin
import pandas as pd

app = Flask(__name__)

CORS(app)

@app.route("/")
def hello():
    return "Hey BDC"


if __name__ == '__main__':
    app.run(host='0.0.0.0')
