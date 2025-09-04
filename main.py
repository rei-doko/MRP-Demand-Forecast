#Import dependecies and libraries
from flask import Flask, render_template, Response, jsonify, request
from datetime import datetime
import numpy as py
import flaskwebgui
import sqlite3
import pandas as pd
import math
import time
import os

app = Flask(__name__)
gui = flaskwebgui.FlaskUI(app=app, server="flask", width=1920, height=1080)

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    #app.run(debug=True)
    gui.run()
