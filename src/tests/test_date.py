import datetime
import pytz

test_dates = [
    "today",
    "tomorrow",
    "this week",
    "next week",
    "C:Monday",
    "C:Tuesday",
    "C:Wednesday",
    "C:Thursday",
    "C:Friday",
    "C:Saturday",
    "C:Sunday",
    "F:Monday",
    "F:Tuesday",
    "F:Wednesday",
    "F:Thursday",
    "F:Friday",
    "F:Saturday",
    "F:Sunday",
    "S:Jan 1",
    "S:Feb 14",
    "S:Mar 15",
    "S:Apr 1",
    "S:May 25",
    "S:Jun 30",
    "S:Jul 4",
    "S:Aug 23",
    "S:Sep 10",
    "S:Oct 31",
    "S:Nov 11",
    "S:Dec 25"
]

# Purpose: parses date and returns a datetime object
# Input: date (string), timezone (string)
# Output: start_date, end_date (datetime objects)
def parse_date(input_date, timezone='America/Vancouver'):

    input_date = input_date.lower().strip()

    # localize to timezone
    local_tz = pytz.timezone(timezone)
    now = datetime.datetime.now(tz=local_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    
    if input_date == 'today':
        start_date = now
        end_date = start_date + datetime.timedelta(days=1)
    elif input_date == 'tomorrow':
        start_date = now + datetime.timedelta(days=1)
        end_date = start_date + datetime.timedelta(days=1)
    elif input_date == 'this week':
        start_date = now - datetime.timedelta(days=now.weekday())
        end_date = start_date + datetime.timedelta(days=7)
    elif input_date == 'next week':
        start_date = now + datetime.timedelta(days=7-now.weekday())
        end_date = start_date + datetime.timedelta(days=7)
    elif input_date.startswith('c:'):
        day_of_week = input_date[2:]
        start_date, end_date = get_date_for_day(now, day_of_week)
    elif input_date.startswith('f:'):
        day_of_week = input_date[2:]
        start_date, end_date = get_date_for_day(now, day_of_week, next_week=True)
    elif input_date.startswith('s:'):
        # S:Sep 10 -> ["S", "Sep 10"]
        _, date_part = input_date.split(':')  
        # Sep 10 -> ["Sep", "10"]
        month_abbr, day = date_part.split()  
        day = int(day)

        # map month to number
        months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
            "may": 5, "jun": 6, "jul": 7, "aug": 8,
            "sep": 9, "oct": 10, "nov": 11, "dec": 12
        }
        month = months.get(month_abbr)

        # check if valid month 
        if month is None:
            raise ValueError("Invalid month abbreviation")

        year = now.year # TODO: handle different years
        start_date = datetime.datetime(year, month, day, tzinfo=local_tz)
        end_date = start_date + datetime.timedelta(days=1)
    else:
        raise ValueError("Invalid date format")
    
    return start_date, end_date

# Purpose: get a datetime object for a specific day of the week
# Input: current_date (datetime object), day_of_week (string), next_week (boolean)
# Output: start_date, end_date (datetime objects)
def get_date_for_day(current_date, day_of_week, next_week=False):
    day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    # Monday is 0, Sunday is 6
    current_day_index = current_date.weekday()  
    target_day_index = day_names.index(day_of_week)

    # calculate the difference in days to target day
    days_difference = target_day_index - current_day_index

    # e.g. today is sunday, target day is monday: 0 - 6 = -6 --> move back 6 days
    # e.g. today is tuesday, target day is friday: 4 - 1 = 3 --> move forward 3 days
    start_date = current_date + datetime.timedelta(days=days_difference)

    # if looking for next week, add 7 days
    if next_week:
        start_date += datetime.timedelta(days=7)

    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + datetime.timedelta(days=1) # for 1 whole day

    return start_date, end_date

if __name__ == '__main__':
    for date in test_dates:
        start_date, end_date = parse_date(date)
        print(f"{date}: {start_date} - {end_date}")