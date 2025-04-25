import os
import time

from fastapi import FastAPI

from main import main
ENDPOINT_NAME = os.getenv("ENDPOINT_NAME")

app = FastAPI()


@app.post(ENDPOINT_NAME)
async def root():
    # main()
    print("Got request")
    time.sleep(20)
    print("Hello guys")