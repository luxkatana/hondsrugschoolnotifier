#!/usr/bin/python3
from threading import Thread
from datetime import datetime, timedelta 
from json import dumps
from typing import NamedTuple, Union
from time import sleep as wait
from dotenv import load_dotenv
from sys import stderr
from os import getenv
import socket
import pytz
import requests
import somtodaypython.nonasyncsomtoday as somtoday


def webserver() -> None:
    log(message='Webserver daemon has started on 0.0.0.0:8000')
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', 8000))
    server.listen(5)
    while True:
        client, _ = server.accept()
        client.close()
    

# ------------ CONFIGURATIONS ------------


load_dotenv()
STUDENT_NAME = getenv("LEERLING_LEERLINGNUMMER")
STUDENT_PASSWORD = getenv("LEERLING_WACHTWOORD")
NTFY_TOPIC_NAME = getenv("NTFY_TOPIC_NAME")
if None in [STUDENT_NAME, STUDENT_PASSWORD, NTFY_TOPIC_NAME]:
    stderr.write("Required environment variables are missing.\n")
    stderr.write("The following environment variables are required:\n")
    stderr.write(">STUDENT_NAME\n>STUDENT_PASSWORD\n>NTFY_TOPIC_NAME\n")
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


CET = pytz.timezone("Europe/Amsterdam")
# CET = pytz.FixedOffset(60)
NTFY_ENDPOINT: str = 'https://ntfy.sh'
SCHOOL: somtoday.School = somtoday.find_school("Hondsrug College")
buffer_current_rooster: list[somtoday.Subject] = []
ste_of_de = lambda n: f"{n}ste" if n in (1, 8) else f'{n}de' # noqa
weekends = {5, 6} # saturday and sunday (index offset by 1)
extras: tuple[Extra, ...] = (
    Extra(starting_hour=11, starting_minute=5, ending_hour=11, ending_minute=20, description='van 11:05 tot 11:20', title='Korte pauze begint over 10 minuten!', to_notify_before_min=10),
    # 11:05 - 11:20 korte pauze (extra)
    Extra(starting_hour=13, starting_minute=0, ending_hour=13, ending_minute=30, description='van 13:00 tot 13:30', title='Lange pauze begint over 10 minuten!', to_notify_before_min=10)
    # 13:00 - 13:30 lange pauze (extra)
)
# ------------ CONSTANTS ------------




# ------------ HELPER FUNCTIONS ------------
def log(level: str='INFO', message: str='', *args, **kwargs):
    now = datetime.now()
    print(f'{level.upper()} - {now.strftime("%d/%m/%y, %H:%M")}  \t{message}', *args, **kwargs)


def get_nearest_time(subjects: list[somtoday.Subject],
                     now:  datetime) -> tuple[somtoday.Subject, ...]:
    def check(subject:  Union[somtoday.Subject, Extra]) -> bool:
        if isinstance(subject, Extra):
            extra_dt = datetime(year=now.year, month=now.month, day=now.day, hour=subject.starting_hour, minute=subject.starting_minute, tzinfo=CET)
            return (
                extra_dt > now and
                (offset_time := (extra_dt - timedelta(minutes=subject.to_notify_before_min))).hour == now.hour and
                offset_time.minute == now.minute
            )
        subject.begin_time = subject.begin_time.replace(tzinfo=CET)
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
    while rooster[-1].end_time.hour != 16: # 8 uurtjes
        if rooster[-1].end_time.hour == 11 and rooster[-1].end_time.minute == 30: # 11:30
            rooster.append(somtoday.Subject(subject='Unknown', begindt=rooster[-1].end_time, enddt=rooster[-1].end_time + timedelta(minutes=15)))
        elif rooster[-1].end_time.hour == 13 and rooster[-1].end_time.minute == 15: # 13:15
            rooster.append(somtoday.Subject(subject='Unknown', begindt=rooster[-1].end_time, enddt=rooster[-1].end_time + timedelta(minutes=30)))
        else:
            rooster.append(somtoday.Subject(subject='Unknown', begindt=rooster[-1].end_time, enddt=rooster[-1].end_time + timedelta(minutes=45)))
    for extra_thing in extras:
        for index, subject in enumerate(rooster):
            if not isinstance(subject, Extra) and subject.end_time.hour == extra_thing.starting_hour and subject.end_time.minute == extra_thing.starting_minute and (index + 1 ) < len(rooster):
                rooster[index + 1] = extra_thing
    return rooster

            

def find_differences(before: list[somtoday.Subject], after: list[somtoday.Subject]) -> list[tuple[str, somtoday.Subject, somtoday.Subject]]:
    reutrn_val = []
    for before_vak, after_vak in zip(before, after):
        if isinstance(before_vak, Extra) or isinstance(after_vak, Extra):
            continue

        if before_vak.__dict__ != after_vak.__dict__:
            for key in before_vak.__dict__:
                if before_vak.__dict__[key] != after_vak.__dict__[key]:
                    reutrn_val.append((key, before_vak, after_vak))
                    break

    return reutrn_val

def handle_rooster_changes(diff: list[tuple[str, somtoday.Subject, somtoday.Subject]]):
    for wijziging in diff:
        changes_request_payload = {
            'topic': NTFY_TOPIC_NAME,
            'title': '[ROOSTERWIJZIGING] ',
            'message': '',
            'priority': 3,
        }
        attr, before_vak, after_vak = wijziging
        match attr:
            case 'subject_name':
                changes_request_payload['title'] += f'Het {ste_of_de(after_vak.begin_hour)} uur is veranderd naar {after_vak.subject_name}'
                changes_request_payload['message'] = f"Eerder was het {before_vak.subject_name}"
            case 'teacher_short':
                changes_request_payload['title'] += f'Leraar voor {after_vak.subject_name} is veranderd'
                changes_request_payload['message'] = f'Eerder was het {before_vak.teacher_short}, nu {after_vak.teacher_short}'
            case 'location':
                changes_request_payload['title'] += f'{ste_of_de(after_vak.begin_hour)} uur {after_vak.subject_name} locatie is veranderd naar {after_vak.location}'
                changes_request_payload['message'] = f'Eerder was het {before_vak.location}'
            case _:
                log('INFO', f'Unknown attribute: {attr}')

        response = requests.post(NTFY_ENDPOINT, data=dumps(changes_request_payload))
        if response.status_code == 200:
            log('INFO', 'Wijziging sent')
        else:
            log('ERROR', f'Wijziging response is not 200: {response.json()}')

            
            
# ------------ HELPER FUNCTIONS ------------
    
def main() -> None:
    requests.post(NTFY_ENDPOINT,
                            data=dumps(
                                {
                                    'topic': NTFY_TOPIC_NAME,
                                    'title': 'Startup',
                                    'message': 'Notifier started.',
                                    'priority': 3,
                                }
                            ))
    student = SCHOOL.get_student(STUDENT_NAME, STUDENT_PASSWORD)
    global buffer_current_rooster
    while True:

        now = datetime.now(CET)
        if now.weekday() in weekends:
            upcoming_monday = (now + timedelta(days=7 - now.weekday())).replace(hour=8, minute=0)
            log('INFO', f'Pausing(it\'s weekend, no school) so I\'ll sleep until {upcoming_monday.strftime("%d/%m/%Y %H:%M")}')
            wait((upcoming_monday - now).total_seconds())
            log('INFO', 'hey I\'m back!')
            continue

        if now.hour < 8:
            log('INFO', f'Pausing (theres are no classes before 8:00 AM) so I\'ll sleep until {now.replace(hour=8, minute=0).strftime("%d/%m/%Y %H:%M")}')
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
            
        
        try:
            rooster: list[somtoday.Subject] = student.fetch_schedule(now, now + timedelta(days=1))
        except Exception:
            student = SCHOOL.get_student(STUDENT_NAME, STUDENT_PASSWORD)
            log("INFO", "Student has been refreshed.")
            continue
        
        # rooster: [Subject, Subject, ...]


        filled = fill_rooster_extras(rooster)
        nearest_subject_now = get_nearest_time(filled, now)
        handle_rooster_changes(find_differences(buffer_current_rooster, filled))

        if nearest_subject_now != ():
            vak = nearest_subject_now[0]
            if isinstance(vak, Extra):
                vak: Extra
                response = requests.post(NTFY_ENDPOINT,
                                         data=dumps(
                                             {
                                                 'topic': NTFY_TOPIC_NAME,
                                                 'title': vak.title,
                                                 'message': vak.description,
                                                 'priority': 4,
                                                 'icon': 'https://play-lh.googleusercontent.com/EjGVjryW47wRq_m2K6N4eJ0BLpIWt3y5bdHKakeb7uQxZZQDP9ZeCoqeeAG_V42RkA=w240-h480'
                                             }
                                         ))
                if response.status_code == 200:
                    buffer_current_rooster = filled
                    log('INFO', "Extra has been sent")
                else:
                    log('ERROR', f'Response returned status code {response.status_code} with error: {response.text}')
                
            else:
                vak: somtoday.Subject
                if vak.subject_name == 'Unknown':
                    continue
                response = requests.post(NTFY_ENDPOINT,
                        data=dumps({
                            'topic': NTFY_TOPIC_NAME,
                            'title':  f'{vak.subject_name} ({ste_of_de(vak.begin_hour)} uur) gaat zo over 10 minuten beginnen!',
                            'message': f'begint om {vak.begin_time.strftime("%H:%M")} lokaal: {vak.location} docent: {vak.teacher_short}',
                            "priority": 4,
                            'icon': 'https://play-lh.googleusercontent.com/EjGVjryW47wRq_m2K6N4eJ0BLpIWt3y5bdHKakeb7uQxZZQDP9ZeCoqeeAG_V42RkA=w240-h480'
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
    Thread(target=webserver, daemon=True).start()
    log('INFO', "Notifier started")

    try:
        main() # starting the loop 
    except KeyboardInterrupt: ...
    except Exception as e:
        log('ERROR', f'Uncaught error: {e}')
        exit(1)
