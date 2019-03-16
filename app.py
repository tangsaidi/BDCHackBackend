from flask import Flask, render_template, flash, request, redirect, Response
from flask_cors import CORS, cross_origin
import pandas as pd
import json
from sklearn.preprocessing import StandardScaler

import numpy as np
import pymysql.cursors

conn = pymysql.connect(host='hackathon-db.bdc.n360.io',
                             port=3306,
                             user='events',
                             password='Hack@th0n2019',
                             db='hackathon',
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor)


import redis
import time
import pickle
import decimal
from sklearn.neighbors import NearestNeighbors

r = redis.Redis(host='localhost', port=6379, db=0)

features = ["odometer", "transmission_type", "new", "price", "passengers", "car_year"]

app = Flask(__name__)

CORS(app)


def get_cars(inventory_id):
    with conn:
        cur = conn.cursor()
        query = "SELECT * FROM car_inventory WHERE inventory_id={0}".format(inventory_id)
        cur.execute(query)

        rows = cur.fetchall()
        res = pd.DataFrame(rows)
    return res


def number_crunch(inventory_id):
    inv = get_cars(inventory_id)
    for_sale = inv.loc[(inv['car_status'] != "SOLD") & (inv['car_status'] != "DELETED")]
    feature_df = for_sale[features]
    processed_feature_df = pd.concat([feature_df, pd.get_dummies(feature_df["transmission_type"])
                                  .drop("MANUAL", axis = 1)], axis = 1).drop("transmission_type", axis = 1)
    processed_feature_df = processed_feature_df.fillna(processed_feature_df.mean())
    scaler = StandardScaler()
    scaler.fit(processed_feature_df)
    processed_feature_df = pd.DataFrame(scaler.transform(processed_feature_df), columns = feature_df.columns)
    nbrs = NearestNeighbors(n_neighbors=6, algorithm='ball_tree').fit(processed_feature_df)
    distances, indices = nbrs.kneighbors(processed_feature_df)
    distances = pd.DataFrame(distances).drop([0], axis = 1)
    indices = pd.DataFrame(indices).drop([0],axis = 1)

    scaler = StandardScaler()
    print(scaler.fit(distances))
    scaler.transform(distances)
    distances = distances.applymap(lambda x: 10 - x)

    indices = pd.concat([pd.DataFrame(indices), for_sale["car_id"].reset_index(drop = True)], axis =1)
    distances = pd.concat([pd.DataFrame(distances), for_sale["car_id"].reset_index(drop = True)], axis = 1)
    return indices, distances

indices, distances = number_crunch(6)


@app.route("/")
def hello():
    return "Hey BDC"

@app.route("/api/v1/log/<anonymous_id>/<car_id>", methods=['GET', 'POST'])
def log_visit(anonymous_id, car_id):
    lst = []
    if (r.get(anonymous_id) == None):
        lst = [{
            "time": time.time(),
            "car_id": car_id
        }]
    else:
        lst = pickle.loads(r.get(anonymous_id))
        lst.append({"time": time.time(),
                    "car_id": car_id})
    
    r.set(anonymous_id, pickle.dumps(lst))
    return "Success"


@app.route("/api/v1/login/<anonymous_id>/<user_id>", methods=['GET', 'POST'])
def log_in(anonymous_id, user_id):
    if (r.get(anonymous_id) != None):
        temp = r.get(anonymous_id)
        r.set(user_id, temp)
        r.delete(anonymous_id)
        return "Success"
    else:
        raise "anonymous id does not exist in Redis"

@app.route("/api/v1/car_info/<car_id>", methods = ['GET', 'POST'])
def get_car_info(car_id):
    with conn:
        cur = conn.cursor()
        query = "SELECT * FROM car_inventory WHERE car_id={0}".format(car_id)
        cur.execute(query)

        rows = cur.fetchall()
        res = pd.DataFrame(rows)
        
    diction = res.loc[0].to_dict()

    for k, v in diction.items():
        if (isinstance(v, np.int64)):
            diction[k] = int(v)
        if (isinstance(v, pd.Timestamp)):
            diction[k] = v.strftime('%Y-%m-%d')
        if (isinstance(v, decimal.Decimal)):
            diction[k] = float(v)
        
    return Response(json.dumps(diction),  mimetype='application/json')
    

@app.route("/api/v1/similar/<car_id>", methods = ['GET', 'POST'])
def get_similar_car(car_id):
    import sys

    print(distances, file=sys.stderr)

    arr = indices.loc[indices["car_id"] == int(car_id)][[1, 2, 3, 4, 5]]
    return Response(json.dumps({"indices": arr.loc[0].apply(lambda x: indices.loc[x]["car_id"]).tolist(),
                                "distances": distances[[1, 2, 3, 4, 5]][distances["car_id"] == 5204244].loc[0].tolist()}))


if __name__ == '__main__':
    app.run(host='0.0.0.0')
