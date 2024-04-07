#!/usr/bin/python3
import pytz
import requests
import nonasyncsomtoday as somtoday
from datetime import datetime, timedelta 
from enum import Enum
from json import dumps
from typing import NamedTuple, Union
from time import sleep as wait
from dotenv import load_dotenv
from sys import stderr
from os import getenv



# ------------ CONFIGURATIONS ------------


load_dotenv()
STUDENT_NAME = getenv("LEERLING_LEERLINGNUMMER")
STUDENT_PASSWORD = getenv("LEERLING_WACHTWOORD")
NTFY_TOPIC_NAME = getenv("NTFY_TOPIC_NAME")
if None in [STUDENT_NAME, STUDENT_PASSWORD, NTFY_TOPIC_NAME]:
    stderr.write("Required environment variables are missing.\n")
    stderr.write("The following environment variables are required:\n")
    stderr.write(">STUDENT_NAME\n> STUDENT_PASSWORD\n>NTFY_TOPIC_NAME\n")
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

class DiffResult(Enum):
    NAME_CHANGED = 0
    CLASS_DISMISSED = 1
    TEACHER_CHANGED = 2
    CLASS_ADDED = 3
CET = pytz.FixedOffset(60)
NTFY_ENDPOINT: str = 'https://ntfy.sh'
school = somtoday.find_school("Hondsrug College")
buffer_current_rooster: list[somtoday.Subject] = []
ste_of_de = lambda n: f"{n}ste" if n in (1, 8) else f'{n}de' # noqa
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
                     now:  datetime) -> tuple[somtoday.Subject, ...]:
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

            

def find_differences(before: list[Union[somtoday.Subject, Extra]], after: list[Union[somtoday.Subject, Extra]]) -> list[dict[str]]:
    diff: list[dict[str]] = []
    for before_vak, after_vak in zip(before, after):
        payload = {
            'before_vak': before_vak,
            'after_vak': after_vak,
            'reason': -1
        }
        if True in (isinstance(before_vak, Extra), isinstance(after_vak, Extra)):
            NotImplemented # NOTE: implement this in the future :D
            continue
        before_vak: somtoday.Subject
        after_vak: somtoday.Subject
        if before_vak.subject_name != after_vak.subject_name and after_vak.subject_name == 'Unknown':
            payload['reason'] = DiffResult.CLASS_DISMISSED
            log("DEBUG", "Class dismissed")
            diff.append(payload)
        elif before_vak.teacher_short != after_vak.teacher_short:
            log("DEBUG", "Teacher changed")
            payload['reason'] = DiffResult.TEACHER_CHANGED
            diff.append(payload)
        elif before_vak.subject_name != after_vak.subject_name and before_vak.subject_name == 'Unknown':
            log("DEBUG", "Class added")
            payload['reason'] = DiffResult.CLASS_ADDED
            diff.append(payload)
        elif before_vak.subject_name != after_vak.subject_name and 'Unknown' not in [before_vak.subject_name, after_vak.subject_name]:
            payload['reason'] = DiffResult.NAME_CHANGED
            log("DEBUG", "Name changed")
            diff.append(payload)

                
    
    return diff

def handle_rooster_changes(diff: list[dict[str]]):
    for wijziging in diff:
        changes_request_payload = {
            'topic': NTFY_TOPIC_NAME,
            'title': '[ROOSTERWIJZIGING] ',
            'message': '',
            'priority': 2,
        }
        before_vak: somtoday.Subject = wijziging['before_vak']
        after_vak: somtoday.Subject = wijziging['after_vak']
        reason = wijziging['reason']
        if reason == DiffResult.CLASS_ADDED:
            changes_request_payload['title'] += f'Een vrije uur is veranderd naar {after_vak.subject_name}'
            changes_request_payload['message'] = f'Om {after_vak.begin_time.strftime("%H:%M")} heb je {after_vak.subject_name}'
        elif reason == DiffResult.TEACHER_CHANGED:
            changes_request_payload['title'] += f'Leraar voor {after_vak.subject_name} is veranderd'
            changes_request_payload['message'] = f'Eerder was het {before_vak.teacher_short}, nu {after_vak.teacher_short}'
        elif reason == DiffResult.NAME_CHANGED:
            changes_request_payload['title'] += f'Het {ste_of_de(after_vak.begin_hour)} uur is veranderd naar {after_vak.subject_name}'
            changes_request_payload['message'] = f"Eerder was het {before_vak.subject_name}"
        log("DEBUG-161", str(changes_request_payload))

        response = requests.post(NTFY_ENDPOINT, data=dumps(changes_request_payload))
        if response.status_code == 200:
            log('INFO', 'Wijziging sent')
        else:
            log('ERROR', f'Wijziging response is not 200: {response.json()}')

            
            
# ------------ HELPER FUNCTIONS ------------

    
def main() -> None:
    global buffer_current_rooster
    student = school.get_student(STUDENT_NAME, STUDENT_PASSWORD)
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
            
        
        try:
            rooster: list[somtoday.Subject] = student.fetch_schedule(now, now + timedelta(days=1))
        except:
            main()
        
        # rooster: [Subject, Subject, ...]

        # 今天 = { 
        #     'year': 2024,
        #     'month': 1,
        #     'day': 23,
        #     'tzinfo': CET
        # }
        # match (input('>>')):
        #     case 'anything':
        #         rooster  = [
        #             somtoday.Subject(subject='Wiskunde', begindt=datetime(**今天, hour=9, minute=15), enddt=datetime(**今天, hour=10, minute=0), beginhour=1, endhour=2),
        #             somtoday.Subject(subject='Aardrijkskunde', begindt=datetime(**今天, hour=10, minute=0), enddt=datetime(**今天, hour=10, minute=45), beginhour=2, endhour=3),
        #             somtoday.Subject(subject='Engels', begindt=datetime(**今天, hour=10, minute=45), enddt=datetime(**今天, hour=11, minute=30), beginhour=3, endhour=4),
        #             somtoday.Subject(subject='Maatschapijleer', begindt=datetime(**今天, hour=11, minute=45), enddt=datetime(**今天, hour=12, minute=30), beginhour=4, endhour=5),
        #         ]
        #     case _:
        #         rooster  = [
        #             somtoday.Subject(subject='Wiskunde', begindt=datetime(**今天, hour=9, minute=15), enddt=datetime(**今天, hour=10, minute=0), beginhour=1, endhour=2),
        #             somtoday.Subject(subject='Aardrijkskunde', begindt=datetime(**今天, hour=10, minute=0), enddt=datetime(**今天, hour=10, minute=45), beginhour=2, endhour=3),
        #             somtoday.Subject(subject='Engels', begindt=datetime(**今天, hour=10, minute=45), enddt=datetime(**今天, hour=11, minute=30), beginhour=3, endhour=4),
                    
        #         ]
                
                

        filled = fill_rooster_extras(rooster)
        nearest_subject_now = get_nearest_time(filled, now)
        # nearest_subject_now  = get_nearest_time(rooster, now)
        # for i in filled:
        #     if isinstance(i, somtoday.Subject):
        #         i: somtoday.Subject
        #         print(f'{i} \t {i.begin_time.strftime("%H:%M")} -> {i.end_time.strftime("%H:%M")}')
        #     else:
        #         i: Extra
        #         print(f'{i} \t {i.starting_hour}:{i.starting_minute} -> {i.ending_hour}:{i.ending_minute}')
        diff = find_differences(buffer_current_rooster, filled)
        handle_rooster_changes(diff)

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
    log('INFO', "Notifier started")
    try:
        main() # starting the loop 
    except KeyboardInterrupt: ...
    except Exception as e:
        log('ERROR', f'Uncaught error: {e}')
        exit(1)
