from datetime import date, datetime, timedelta


class FloodPrevention:
    ''' 
    A class to control flood prevention when sending emails

    The point is the if you make a bot that will reply to emails automatically you might end up
    in a email sending loop with a bot answering to all of your replies - this is why i made this feature.

    ...

    Attributes
    ----------
    similarities : list of strings
        a list of things to check for when sending an email to determine if a similar email was sent,
        for example: ['subject', 'to'] will check if an email with the same subject was sent to the same email as the email
        you are trying to send
    after_date : date or datetime or int
        a date for which to check for similar emails
    number_of_messages : int
        number of messages that is considered a flood
    '''
        
    def __init__(
        self,
        similarities: list,
        after_date: date or datetime or int,
        number_of_messages: int = 1
        ):
        self.similarities = similarities
        if not 'to' in self.similarities:
            similarities.append('to')
        if isinstance(after_date, int):
            after_date = date.today() - timedelta(days= after_date)
        self.after_date = after_date
        self.number_of_messages = number_of_messages
