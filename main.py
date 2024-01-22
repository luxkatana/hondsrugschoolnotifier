import logging
import pytz
from json import dumps
from datetime import datetime, timedelta 
import requests
from waitress import serve
import somtodaypython.nonasyncsomtoday as somtoday
from time import sleep as wait
from threading import Thread
from flask import Flask, render_template
logging.basicConfig(filename="main_server_log.log", filemode='a', level=logging.ERROR,
                    format="%(asctime)s: %(message)s")
app = Flask(__name__)
with open('./main_server_log.log', 'w') as file:
    file.truncate()

CEST = pytz.FixedOffset(60)
print("CEST => {}".format(datetime.now(CEST)))
print("NORMAL DEFAULT => {}".format(datetime.now()))

school = somtoday.find_school("Hondsrug College")

def get_nearest_time(subjects: list[somtoday.Subject],
                     now:  datetime) -> tuple[somtoday.Subject]:
    def check(subject:  somtoday.Subject) -> bool:
        return \
            subject.begin_time > now and\
            (offsetby10 := (
                subject.begin_time - timedelta(minutes=10))).hour == now.hour \
            and offsetby10.minute == now.minute
                
            
    result = tuple(filter(check,  subjects))
    return result


    
def main() -> None:
    while True:
        with open("./main_server_log.log", 'r') as f:
            if len(f.readline()) >= 100:
                f.truncate()
        student = school.get_student('133600', 'inchem2009')
        now = datetime.now(CEST)
        # now = datetime(2023, 9, 11, 9, 50, tzinfo=CEST)
        rooster: list[somtoday.Subject] = student\
            .fetch_schedule(now, now + timedelta(days=1))
        # rooster: [Subject, Subject, ...]
        nearest_subject_now  = get_nearest_time(rooster, now)
        if nearest_subject_now !=  ():
            vak = nearest_subject_now[0]
            response = requests.post("https://ntfy.sh/",
                       data=dumps({
                           'topic': 'luxkatanaschool133600',
                           'title':  f'{vak.subject_name} ({vak.begin_hour}{"ste" if vak.begin_hour in [1, 8] else "de"} uur) gaat zo over 10 minuten beginnen!',
                           'message': f'begint om {vak.begin_time.strftime("%H:%M")} lokaal {vak.location}',
                           "priority": 4,
                       }
                           ),
                       )
            if response.status_code == 200:
                logging.error("Message has been successfully sent")
            else:
                logging.error(f"Response returned status code {response.status_code} with error: {response.text}")
            
        else:
            logging.error(f"Condition was not correct {nearest_subject_now}\t {now}")
        wait(60)

@app.get('/')
def index():
    student = school.get_student('133600', 'inchem2009')
    now = datetime.now(CEST)
    schedule = student.fetch_schedule(now, now + timedelta(days=1))
    nearest_time = get_nearest_time(schedule)
    if nearest_time != ():
        return render_template('index.html', status='les')
    return render_template('index.html', status='vrij')

if __name__ == '__main__':
    Thread(target=main).start()
    
