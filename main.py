#!/usr/bin/python3
import pytz
import requests
import nonasyncsomtoday as somtoday
from datetime import datetime, timedelta 
from json import dumps
from typing import NamedTuple, Union
from time import sleep as wait
from dotenv import load_dotenv
from sys import stderr
from os import getenv



# ------------ CONFIGURATIONS ------------


load_dotenv()
STUDENT_NAME = getenv("STUDENT_NAME")
STUDENT_PASSWORD = getenv("STUDENT_PASSWORD")
NTFY_TOPIC_NAME = getenv("NTFY_TOPIC_NAME")
if None in [STUDENT_NAME, STUDENT_PASSWORD, NTFY_TOPIC_NAME]:
    stderr.write("Required environment variables are missing.\n")
    stderr.write("The following environment variables are required:\n")
    stderr.write("STUDENT_NAME\n> STUDENT_PASSWORD\n>NTFY_TOPIC_NAME\n")
    stderr.flush()
    exit(1)
# ------------ CONFIGURATIONS ------------

# ------------ CONSTANTS ------------
class Extra(NamedTuple):
    starting_hour: int
    starting_minute: int
    ending_hour: int
    ending_minute: int
    title: str
    description: str
    to_notify_before_min: int

CET = pytz.FixedOffset(60)
NTFY_ENDPOINT: str = 'https://ntfy.sh'
school = somtoday.find_school("Hondsrug College")
weekends = {5, 6} # saturday and sunday (index offset by 1)
extras: tuple[Extra, ...] = (
    Extra(starting_hour=11, starting_minute=30, ending_hour=11, ending_minute=45, description='van 11:30 tot 11:45', title='Korte pauze begint over 10 minuten!', to_notify_before_min=10),
    # 11:30 - 11:45 korte pauze (extra)
    Extra(starting_hour=13, starting_minute=15, ending_hour=13, ending_minute=45, description='van 13:15 tot 13:45', title='Lange pauze begint over 10 minuten!', to_notify_before_min=10)
    # 13:15 - 13:45 lange pauze (extra)
)
# ------------ CONSTANTS ------------




# ------------ HELPER FUNCTIONS ------------
def log(level: str='INFO', message: str='', *args, **kwargs):
    now = datetime.now()
    print(f'{level.upper()} - {now.strftime("%d/%m/%y, %H:%M")}  \t{message}', *args, **kwargs)

def get_nearest_time(subjects: list[somtoday.Subject],
                     now:  datetime) -> tuple[somtoday.Subject]:
    def check(subject:  Union[somtoday.Subject, Extra]) -> bool:
        if isinstance(subject, Extra):
            extra_dt = datetime(year=now.year, month=now.month, day=now.day, hour=subject.starting_hour, minute=subject.starting_minute, tzinfo=CET)
            return (
                extra_dt > now and
                (offset_time := (extra_dt - timedelta(minutes=subject.to_notify_before_min))).hour == now.hour and
                offset_time.minute == now.minute
            )
        return (
            subject.begin_time > now and
            (offsetby10 := (subject.begin_time - timedelta(minutes=10))).hour == now.hour 
            and offsetby10.minute == now.minute)
                
            
    result = tuple(filter(check,  subjects))
    return result

def fill_rooster_extras(rooster: list[somtoday.Subject]) -> list[somtoday.Subject]:
    if len(rooster) == 0:
        return []
    rooster = rooster.copy()
    for extra_thing in extras:
        for index, subject in enumerate(rooster):
            if not isinstance(subject, Extra) and subject.end_time.hour == extra_thing.starting_hour and subject.end_time.minute == extra_thing.starting_minute and (index + 1 ) < len(rooster):
                rooster.insert(index + 1, extra_thing)
    return rooster

            


            
            
# ------------ HELPER FUNCTIONS ------------

    
def main() -> None:
    while True:
        now = datetime.now(CET)
        if now.weekday() in weekends:
            upcoming_monday = (now + timedelta(days=7 - now.weekday())).replace(hour=8, minute=0)
            log('INFO', f'Pausing(it\'s weekend, no school) so I\'ll sleep until {upcoming_monday.strftime("%d/%m/%Y %H:%M")}')
            wait((upcoming_monday - now).total_seconds())
            log('INFO', 'hey I\'m back!')
            continue

        if now.hour < 8:
            log('INFO', f'Pausing(theres are no classes before 8:00 AM) so I\'ll sleep until {now.replace(hour=8, minute=0).strftime("%d/%m/%Y %H:%M")}')
            duration_to_wait = (now.replace(hour=8, minute=0) - now).total_seconds() 
            wait(duration_to_wait)
            log('INFO', 'hey I\'m back!')
            continue
        if now.hour >= 16:
            sleeping_until = now.replace(hour=8, minute=0) + timedelta(days=1)
            duration = (sleeping_until - now).total_seconds()
            log('INFO', f'Classes are over for today, I\'ll sleep until {sleeping_until.strftime("%d/%m/%Y %H:%M")}')
            wait(duration)
            log('INFO', 'hey I\'m back!')
            continue
        # if (now.weekday() in weekends) or (now.hour < 8) or (now.hour >= 16):
        #     '''
        #     (now.weekday() in weekends) => check if now is saturday or sunday
        #     (now.hour < 8) => check if the time is before 8:00 AM (no lessons at my school)
        #     (now.hour >= 16) => check if the time is later than 4:00 PM (class finished)
        #     '''
        #     log('INFO', 'CYCLE SKIPPED')
        #     continue
            
        student = school.get_student(STUDENT_NAME, STUDENT_PASSWORD)
        rooster: list[somtoday.Subject] = student\
            .fetch_schedule(now, now + timedelta(days=1))
        # rooster: [Subject, Subject, ...]

        # 今天 = {
        #     'year': 2024,
        #     'month': 1,
        #     'day': 23,
        #     'tzinfo': CET
        # }
        # testing_subjects  = [
        #     somtoday.Subject(subject='Wiskunde', begindt=datetime(**今天, hour=9, minute=15), enddt=datetime(**今天, hour=10, minute=0)),
        #     somtoday.Subject(subject='Aardrijkskunde', begindt=datetime(**今天, hour=10, minute=0), enddt=datetime(**今天, hour=10, minute=45)),
        #     somtoday.Subject(subject='Engels', begindt=datetime(**今天, hour=10, minute=45), enddt=datetime(**今天, hour=11, minute=30)),
        #     somtoday.Subject(subject='ICT', begindt=datetime(**今天, hour=11, minute=45), enddt=datetime(**今天, hour=12, minute=30)),
        #     somtoday.Subject(subject='ICT', begindt=datetime(**今天, hour=12, minute=30), enddt=datetime(**今天, hour=13, minute=15)),
        #     somtoday.Subject(subject='Nederlands', begindt=datetime(**今天, hour=13, minute=45), enddt=datetime(**今天, hour=14, minute=30)),
            
        # ]
        nearest_subject_now = get_nearest_time(fill_rooster_extras(rooster), now)
        # nearest_subject_now  = get_nearest_time(rooster, now)

        if nearest_subject_now !=  ():
            vak = nearest_subject_now[0]
            if isinstance(vak, Extra):
                vak: Extra
                response = requests.post(NTFY_ENDPOINT,
                                         data=dumps(
                                             {
                                                 'topic': NTFY_TOPIC_NAME,
                                                 'title': vak.title,
                                                 'message': vak.description,
                                                 'priority': 4
                                             }
                                         ))
                if response.status_code == 200:
                    log('INFO', "Extra has been sent")
                else:
                    log('ERROR', f'Response returned status code {response.status_code} with error: {response.text}')
                
            else:
                response = requests.post(NTFY_ENDPOINT,
                        data=dumps({
                            'topic': NTFY_TOPIC_NAME,
                            'title':  f'{vak.subject_name} ({vak.begin_hour}{"ste" if vak.begin_hour in [1, 8] else "de"} uur) gaat zo over 10 minuten beginnen!',
                            'message': f'begint om {vak.begin_time.strftime("%H:%M")} lokaal {vak.location}',
                            "priority": 4,
                        }
                            ),
                            )
                if response.status_code == 200:
                    log('INFO', "Message has been successfully sent")
                else:
                    log('ERROR', f"Response returned status code {response.status_code} with error: {response.text}")
        else:
            log('INFO', 'YAAY! No classes :D!')
            
        wait(60)

if __name__ == '__main__':
    log('INFO', "Notifier started")
    try:
        main() # starting the loop 
    except KeyboardInterrupt:
        ...
