import pytz
import datetime
import re

class CalendarUtilities:
    @staticmethod
    def parse_date_reference(date_reference, day_of_week=None, specific_date=None, timezone='America/Vancouver'):
        local_tz = pytz.timezone(timezone)
        now = datetime.datetime.now(tz=local_tz).replace(hour=0, minute=0, second=0, microsecond=0)

        if date_reference == 'today':
            start_date = now
            end_date = start_date + datetime.timedelta(days=1)
        elif date_reference == 'tomorrow':
            start_date = now + datetime.timedelta(days=1)
            end_date = start_date + datetime.timedelta(days=1)
        elif date_reference == 'yesterday':
            start_date = now - datetime.timedelta(days=1)
            end_date = start_date + datetime.timedelta(days=1)
        elif date_reference in ['this week', 'next week', 'last week']:
            if day_of_week:
                start_date, end_date = CalendarUtilities.get_date_for_day(now, day_of_week, date_reference)
            else:
                week_offset = 0 if date_reference == 'this week' else (1 if date_reference == 'next week' else -1)
                start_date = now + datetime.timedelta(days=(7 * week_offset - now.weekday()))
                end_date = start_date + datetime.timedelta(days=7)
        elif date_reference == 'specific_date' and specific_date:
            start_date = CalendarUtilities.parse_specific_date(specific_date, now.year, local_tz)
            end_date = start_date + datetime.timedelta(days=1)
        else:
            raise ValueError("Invalid date reference or missing required information")

        return start_date.replace(tzinfo=None), end_date.replace(tzinfo=None)

    @staticmethod
    def get_date_for_day(current_date, day_of_week, week_reference):
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        current_day_index = current_date.weekday()
        target_day_index = day_names.index(day_of_week.lower())

        days_difference = target_day_index - current_day_index
        if week_reference == 'next week':
            days_difference += 7
        elif week_reference == 'last week':
            days_difference -= 7

        start_date = current_date + datetime.timedelta(days=days_difference)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + datetime.timedelta(days=1)

        return start_date, end_date

    @staticmethod
    def parse_specific_date(specific_date, current_year, timezone):
        try:
            date_obj = datetime.datetime.strptime(f"{specific_date} {current_year}", "%b %d %Y")
            return timezone.localize(date_obj)
        except ValueError:
            raise ValueError(f"Invalid specific date format: {specific_date}. Expected format: MMM DD (e.g., Aug 3)")

    @staticmethod
    def parse_time_range(time_range):
        
        # custom handling for empty time range
        if not time_range:
            start_time = datetime.time(0, 0)
            end_time = datetime.time(0, 0)
            return start_time, end_time
        
        time_pattern = r'(\d+(?::\d+)?)\s*(am|pm|AM|PM)?(?:\s*-\s*(\d+(?::\d+)?)\s*(am|pm|AM|PM)?)?'
        match = re.match(time_pattern, time_range)

        if not match:
            raise ValueError(f"Invalid time range format: {time_range}")

        start_time = CalendarUtilities.parse_time(match.group(1), match.group(2))
        
        if match.group(3):  # If end time is specified
            end_time = CalendarUtilities.parse_time(match.group(3), match.group(4))
        else:
            end_time = (start_time + datetime.timedelta(hours=1)).time()

        return start_time, end_time

    @staticmethod
    def parse_time(time_str, meridiem):
        if ':' in time_str:
            hour, minute = map(int, time_str.split(':'))
        else:
            hour, minute = int(time_str), 0

        if meridiem and meridiem.lower() == 'pm' and hour != 12:
            hour += 12
        elif meridiem and meridiem.lower() == 'am' and hour == 12:
            hour = 0

        return datetime.time(hour, minute)
    
def get_user_input(prompt, options=None):
    while True:
        user_input = input(prompt).strip().lower()
        if options and user_input not in options:
            print(f"Invalid input. Please choose from: {', '.join(options)}")
        else:
            return user_input

def main():
    print("Welcome to the Interactive Test!")
    
    while True:
        print("\nChoose a test case:")
        print("1. Parse date reference")
        print("2. Parse time range")
        print("3. Exit")
        
        choice = get_user_input("Enter your choice (1-3): ", ["1", "2", "3"])
        
        if choice == "3":
            print("Thank you for using the Interactive Test. Goodbye!")
            break
        
        if choice == "1":
            date_reference = get_user_input("Enter date reference (today, tomorrow, yesterday, this week, next week, last week, specific_date): ")
            
            day_of_week = None
            specific_date = None
            
            if date_reference in ["this week", "next week", "last week"]:
                use_day = get_user_input("Do you want to specify a day of the week? (yes/no): ", ["yes", "no"])
                if use_day == "yes":
                    day_of_week = get_user_input("Enter day of week: ")
            
            if date_reference == "specific_date":
                specific_date = input("Enter specific date (e.g., Aug 3): ")
            
            timezone = "America/Vancouver"
            
            try:
                start_date, end_date = CalendarUtilities.parse_date_reference(date_reference, day_of_week, specific_date, timezone)
                print(f"Start date: {start_date}")
                print(f"End date: {end_date}")
            except ValueError as e:
                print(f"Error: {str(e)}")
        
        elif choice == "2":
            time_range = input("Enter time range (e.g., 2:30pm-3:30pm): ")
            
            try:
                start_time, end_time = CalendarUtilities.parse_time_range(time_range)
                print(f"Start time: {start_time}")
                print(f"End time: {end_time}")
            except ValueError as e:
                print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()