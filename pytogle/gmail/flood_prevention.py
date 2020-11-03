from datetime import date, datetime, timedelta


class FloodPrevention:

    def __init__(
        self,
        similarities: list,
        after_date: date or datetime = date.today() - timedelta(days= 1),
        number_of_messages: int  = 1
        ):
        self.similarities = similarities
        if not 'to' in self.similarities:
            similarities.append('to')
        self.after_date = after_date
        self.number_of_messages = number_of_messages
