import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import FastAPI

from main import main
ENDPOINT_NAME = os.getenv("ENDPOINT_NAME")

app = FastAPI()


@app.get(ENDPOINT_NAME)
async def root():
    print("application started")
    executor = ThreadPoolExecutor(max_workers=1)
    executor.submit(main)
    print("application ended")
    return {"message": "Working"}