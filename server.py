import os
import time

from fastapi import FastAPI

from main import main
ENDPOINT_NAME = os.getenv("ENDPOINT_NAME")

app = FastAPI()


@app.post(ENDPOINT_NAME)
async def root():
    print("application started")
    main()
    print("application ended")