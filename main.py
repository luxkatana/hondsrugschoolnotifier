from fastapi import FastAPI, Response
import uvicorn
import schedule
import somtodaypython.nonasyncsomtoday as somtodaypython
# ok
from threading import Thread
def main() -> None:
    while True:
        pass

main_background = Thread(target=main)

app = FastAPI()


@app.get('/heartbeat/')
async def heartbeat():
    school = somtodaypython.find_school("Hondsrug College")
    student = school.get_student("133600", 'inchem2009')
    print(student)
    return Response("{\"response\": \"%s\"}" % student.full_name, media_type='application/json')

if __name__ ==  "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
    print("Application started")
