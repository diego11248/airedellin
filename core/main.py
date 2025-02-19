from fastapi import FastAPI, Request, Depends,Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

import json
import random

import asyncio

from .tools.dummy_donations import load_data,retrieve_data_for_sensor
from .tools.dataTool import Sensors
from .tools.pred import linear_regresion,arima,random_forest,sarima,lasso,xgboost,exponential_smoothing, LSTM

from .tools.tools import *

app = FastAPI(debug=True)
app.mount('/static', StaticFiles(directory='core/static', html=True), name='static')

token = readtxtline("data/token.txt")
dummy_donations=load_data("data/dummy_donations.json")
host = "influxdb.canair.io"
sensors = Sensors("canairio", host)
templates = Jinja2Templates(directory="core/templates")

algorithm_names = ["originalData","linearRegression", "Arima", "randomForest","Sarima","Lasso","Xgboost","ExponentialSmoothing","LSTM"]
algorithm_map = {
    "linearRegression": linear_regresion,
    "Arima": arima,
    "randomForest": random_forest,
    "Sarima":sarima,
    "Lasso":lasso,
    "Xgboost":xgboost,
    "ExponentialSmoothing":exponential_smoothing,
    "LSTM":LSTM
}

formatted_data = []

async def update_sensor_data():
    global formatted_data
    while True:
        # Update the formatted data every 30 minutes
        formatted_data = await sensors.get_formatted_data()
        await asyncio.sleep(1800)  # 1800 seconds = 30 minutes

@app.on_event("startup")
async def startup_event():
    # Start the background task to update sensor data every 30 minutes
    asyncio.create_task(update_sensor_data())
    
@app.on_event("shutdown")
async def shutdown_event():
    for task in asyncio.all_tasks():
        task.cancel()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    data = [
        {
            'type': 'Feature',
            'properties': {'name': 'Jardins du Trocadéro <b>(not working🚧)</b>', 'pm25': 16},
            'geometry': {'type': 'Point', 'coordinates': [2.289207, 48.861561]},
        },
        {
            'type': 'Feature',
            'properties': {'name': 'Jardin des Plantes <b>(not working🚧)</b>', 'pm25': 39},
            'geometry': {'type': 'Point', 'coordinates': [2.359823, 48.843995]},
        },
        {
            'type': 'Feature',
            'properties': {'name': 'Jardins das Tulherias <b>(not working🚧)</b>', 'pm25': 9999},
            'geometry': {'type': 'Point', 'coordinates': [2.327092, 48.863608]},
        },
        {
            'type': 'Feature',
            'properties': {'name': 'Parc de Bercy <b>(not working🚧)</b>', 'pm25': 58},
            'geometry': {'type': 'Point', 'coordinates': [2.382094, 48.835962]},
        },
        {
            'type': 'Feature',
            'properties': {'name': 'Jardin du Luxemburg <b>(not working🚧)</b>', 'pm25': 6},
            'geometry': {'type': 'Point', 'coordinates': [2.336975, 48.846421]},
        },
    ] + formatted_data

    return templates.TemplateResponse("index.html", {"request": request, "token": token, "data": data})


@app.get("/sensor{sensor_name}", response_class=HTMLResponse)
async def get_sensor(request: Request, sensor_name: str):
    data = sensors.data(sensor_name)
    data = [int(value) for value in data if value is not None]
    donations=retrieve_data_for_sensor(sensor_name,dummy_donations)
    return templates.TemplateResponse("sensors.html", {
        "request": request,
        "sensor_name": sensor_name,
        "data": data,
        "donations": donations ,
    })

@app.post("/sensor{sensor_name}")
async def post_sensor(request: Request, sensor_name: str, rangetime: str = Form("24h")):
    range_option = rangetime  # This value comes directly from the form submission
    print(range_option)
    # You might need to map range_option to the format your sensors.data function expects
    if range_option == "1w":
        time_range = "7d"
    elif range_option == "1m":
        time_range = "4w"
    elif range_option == "1y":
        time_range = "182d"
    else:
        time_range = "24h"
    print(time_range)
    data = sensors.data(sensor_name, time_range)
    data = [int(value) for value in data if value is not None]
    donations=retrieve_data_for_sensor(sensor_name,dummy_donations)

    return templates.TemplateResponse("sensors.html", {
        "request": request,
        "sensor_name": sensor_name,
        "data": data,
        "donations": donations ,

    })

@app.get("/sensor{sensor_name}/statistics", response_class=HTMLResponse)
async def statistics(request: Request, sensor_name: str):
    #data = sensors.data(sensor_name)
    data=sensors.data_complate_particules(sensor_name)
    pm25=data["pm25"]
    pm10=data["pm10"]
    pm1=data["pm1"]

    #print(data)
    stad = statistics_extractor(pm25)
    #data = [int(value) for value in data if value is not None]
    return templates.TemplateResponse("statistics.html", {
        "request": request,
        "sensor_name": sensor_name,
        "data": pm25,
        "pm10":pm10,
        "statistics":stad,
        "pm1":pm1,
    })


@app.get("/sensor{sensor_name}/predictions", response_class=HTMLResponse)
async def get_mlalgorithm(request: Request, sensor_name: str):
    data = sensors.data(sensor_name)
    data = [int(value) for value in data if (value is not None and 0<value<1024)]
    return templates.TemplateResponse("ml_algorithms.html", {
        "request": request,
        "algorithm_names": algorithm_names,
        "algorithm_selected": "",
        "data": data,
        "result": None
    })

@app.post("/sensor{sensor_name}/predictions", response_class=HTMLResponse)
async def post_mlalgorithm(
    request: Request,
    sensor_name: str,
    algorithm: str = Form(...),
):  
    pm25,dates = sensors.data(sensor_name,date=True)
    print(dates,pm25)
    data = [int(value) for value in pm25 if value is not None]
    
    # Apply the selected algorithm
    if algorithm in algorithm_map:

        result = algorithm_map[algorithm](data)
    elif algorithm=="originalData":
        result = [[int(value) for value in data if value is not None],"0"]
    else:
        random_list = [random.randint(0, 55) for _ in range(200)]
        result = [random_list,"THE ALGORITHM SELECTED NOT EXIST"]  # If no valid algorithm is selected, return the original data
    
    #print(data[0:20],result[0:20]) # for debug

    return templates.TemplateResponse("ml_algorithms.html", {
        "request": request,
        "algorithm_names": algorithm_names,
        "algorithm_selected": algorithm,
        "data": list(map(int,result[0])),
        "result": "Error of "+str(result[1])
    })


@app.get("/index", response_class=HTMLResponse)
async def landing_page(request: Request):
    return templates.TemplateResponse("landing_page.html", {
        "request": request
    })

@app.get("/add_donation", response_class=HTMLResponse)
async def add_donation(request: Request):
    return templates.TemplateResponse("add_donation.html", {
        "request": request
    })
