import unittest
import datetime
import pytz
from freezegun import freeze_time
import re


class CalendarUtilities:
    @staticmethod
    def parse_date_reference(date_reference, day_of_week, specific_date, timezone='America/Vancouver'):
        local_tz = pytz.timezone(timezone)
        now = datetime.datetime.now(tz=local_tz).replace(hour=0, minute=0, second=0, microsecond=0)

        if date_reference == 'today':
            start_date = now
            end_date = start_date + datetime.timedelta(days=1)
        elif date_reference == 'tomorrow':
            start_date = now + datetime.timedelta(days=1)
            end_date = start_date + datetime.timedelta(days=1)
        elif date_reference == 'this week':
            start_date = now - datetime.timedelta(days=now.weekday())
            end_date = start_date + datetime.timedelta(days=7)
        elif date_reference == 'next week':
            start_date = now + datetime.timedelta(days=7-now.weekday())
            end_date = start_date + datetime.timedelta(days=7)
        elif date_reference == 'specific_date':
            start_date, end_date = CalendarUtilities.parse_specific_date(specific_date, local_tz)
        else:
            raise ValueError("Invalid date reference")

        if day_of_week:
            start_date, end_date = CalendarUtilities.adjust_for_day_of_week(start_date, day_of_week, date_reference == 'next week')

        return start_date.replace(tzinfo=None), end_date.replace(tzinfo=None)

    @staticmethod
    def parse_specific_date(specific_date, local_tz):
        now = datetime.datetime.now(tz=local_tz)
        month_abbr, day = specific_date.split()
        day = int(day)
        months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
        }
        month = months.get(month_abbr.lower())
        if month is None:
            raise ValueError("Invalid month abbreviation")

        year = now.year
        start_date = datetime.datetime(year, month, day, tzinfo=local_tz)
        if start_date < now:
            start_date = datetime.datetime(year + 1, month, day, tzinfo=local_tz)
        end_date = start_date + datetime.timedelta(days=1)
        return start_date, end_date

    @staticmethod
    def adjust_for_day_of_week(start_date, day_of_week, next_week=False):
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        current_day_index = start_date.weekday()
        target_day_index = day_names.index(day_of_week.lower())
        days_difference = target_day_index - current_day_index
        if days_difference < 0:
            days_difference += 7
        if next_week:
            days_difference += 7
        start_date = start_date + datetime.timedelta(days=days_difference)
        end_date = start_date + datetime.timedelta(days=1)
        return start_date, end_date

    @staticmethod
    def parse_time_range(time_range):
        if not time_range:
            return None, None

        time_pattern = r'(\d+:\d+|\d+)\s*(am|pm|AM|PM)'
        matches = re.findall(time_pattern, time_range)

        if not matches:
            return None, None

        def parse_time(time_str, meridiem):
            if ':' in time_str:
                hours, minutes = map(int, time_str.split(':'))
            else:
                hours, minutes = int(time_str), 0
            if meridiem.lower() == 'pm' and hours != 12:
                hours += 12
            elif meridiem.lower() == 'am' and hours == 12:
                hours = 0
            return datetime.timedelta(hours=hours, minutes=minutes)

        start_time = parse_time(matches[0][0], matches[0][1])
        if len(matches) > 1:
            end_time = parse_time(matches[1][0], matches[1][1])
        else:
            end_time = start_time + datetime.timedelta(hours=1)

        return start_time, end_time

    @staticmethod
    def combine_date_and_time(date, time_delta):
        if time_delta is not None:
            return date + time_delta
        return date

class TestCalendarUtilities(unittest.TestCase):
    @freeze_time("2023-07-10")  # A Monday
    def test_parse_date_reference(self):
        tz = 'America/Vancouver'
        
        # Test 'today'
        start, end = CalendarUtilities.parse_date_reference('today', None, None, tz)
        self.assertEqual(start, datetime.datetime(2023, 7, 10))
        self.assertEqual(end, datetime.datetime(2023, 7, 11))

        # Test 'tomorrow'
        start, end = CalendarUtilities.parse_date_reference('tomorrow', None, None, tz)
        self.assertEqual(start, datetime.datetime(2023, 7, 11))
        self.assertEqual(end, datetime.datetime(2023, 7, 12))

        # Test 'this week'
        start, end = CalendarUtilities.parse_date_reference('this week', None, None, tz)
        self.assertEqual(start, datetime.datetime(2023, 7, 10))
        self.assertEqual(end, datetime.datetime(2023, 7, 17))

        # Test 'next week'
        start, end = CalendarUtilities.parse_date_reference('next week', None, None, tz)
        self.assertEqual(start, datetime.datetime(2023, 7, 17))
        self.assertEqual(end, datetime.datetime(2023, 7, 24))

        # Test 'specific_date'
        start, end = CalendarUtilities.parse_date_reference('specific_date', None, 'Aug 15', tz)
        self.assertEqual(start, datetime.datetime(2023, 8, 15))
        self.assertEqual(end, datetime.datetime(2023, 8, 16))

        # Test with day_of_week
        start, end = CalendarUtilities.parse_date_reference('this week', 'wednesday', None, tz)
        self.assertEqual(start, datetime.datetime(2023, 7, 12))
        self.assertEqual(end, datetime.datetime(2023, 7, 13))

    def test_parse_specific_date(self):
        tz = 'America/Vancouver'
        local_tz = pytz.timezone(tz)

        # Test current year
        start, end = CalendarUtilities.parse_specific_date('Aug 15', local_tz)
        self.assertEqual(start, datetime.datetime(2023, 8, 15, tzinfo=local_tz))
        self.assertEqual(end, datetime.datetime(2023, 8, 16, tzinfo=local_tz))

        # Test next year
        with freeze_time("2023-12-31"):
            start, end = CalendarUtilities.parse_specific_date('Jan 15', local_tz)
            self.assertEqual(start, datetime.datetime(2024, 1, 15, tzinfo=local_tz))
            self.assertEqual(end, datetime.datetime(2024, 1, 16, tzinfo=local_tz))

        # Test invalid month
        with self.assertRaises(ValueError):
            CalendarUtilities.parse_specific_date('Foo 15', local_tz)

    @freeze_time("2023-07-10")  # A Monday
    def test_adjust_for_day_of_week(self):
        start = datetime.datetime(2023, 7, 10)

        # Test same week
        result, _ = CalendarUtilities.adjust_for_day_of_week(start, 'wednesday')
        self.assertEqual(result, datetime.datetime(2023, 7, 12))

        # Test next week
        result, _ = CalendarUtilities.adjust_for_day_of_week(start, 'monday', next_week=True)
        self.assertEqual(result, datetime.datetime(2023, 7, 17))

        # Test wrapping to next week
        result, _ = CalendarUtilities.adjust_for_day_of_week(start, 'sunday')
        self.assertEqual(result, datetime.datetime(2023, 7, 16))

    def test_parse_time_range(self):
        # Test single time
        start, end = CalendarUtilities.parse_time_range('2:30pm')
        self.assertEqual(start, datetime.timedelta(hours=14, minutes=30))
        self.assertEqual(end, datetime.timedelta(hours=15, minutes=30))

        # Test time range
        start, end = CalendarUtilities.parse_time_range('2:30pm - 4:45pm')
        self.assertEqual(start, datetime.timedelta(hours=14, minutes=30))
        self.assertEqual(end, datetime.timedelta(hours=16, minutes=45))

        # Test midnight
        start, end = CalendarUtilities.parse_time_range('12:00am - 1:00am')
        self.assertEqual(start, datetime.timedelta(hours=0, minutes=0))
        self.assertEqual(end, datetime.timedelta(hours=1, minutes=0))

        # Test invalid time
        start, end = CalendarUtilities.parse_time_range('invalid time')
        self.assertIsNone(start)
        self.assertIsNone(end)

    def test_combine_date_and_time(self):
        date = datetime.datetime(2023, 7, 10)
        time = datetime.timedelta(hours=14, minutes=30)

        result = CalendarUtilities.combine_date_and_time(date, time)
        self.assertEqual(result, datetime.datetime(2023, 7, 10, 14, 30))

        # Test with None time
        result = CalendarUtilities.combine_date_and_time(date, None)
        self.assertEqual(result, date)

if __name__ == '__main__':
    unittest.main()