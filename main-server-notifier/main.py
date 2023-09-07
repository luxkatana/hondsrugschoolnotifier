from fastapi import FastAPI, Response
import uvicorn
from threading import Thread
def main() -> None:
    pass

main_background = Thread()

app = FastAPI()


@app.get('/heartbeat/')
async def heartbeat():
    return Response("{\"response\": true}", media_type='application/json')

if __name__ ==  "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
    print("Application started")
