from datetime import datetime, timedelta

def minutes_difference(minute1:int, minute2:int) -> int:
    # 
    difference = (minute2 - minute1) % 60
    return min(difference, 60 - difference)


def check_minute_normally(minute:int, now:int) -> bool:
    if minute > 59 or now > 59 or minute < 0:
        return False
    
    elif minute > now:
        if now > 1:
            return False
        elif minute < 58:
            return False
        
    elif now - minute > 5:
        return False
    
    return True