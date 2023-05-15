

from datetime import datetime, timedelta













# utc_time_str = datetime.now()

#icm_time = icms.request('get_icm_time 8')['value']
#utc_time_str = icms.request('read 8 0x2B')['value']
# utc_time_str = utc_time_str.split('T')
#Years, days, hours, min, sec
# years   = int(utc_time_str[0].split('-')[0])
# days    = int(utc_time_str[0].split('-')[1])
# days    = utc_time_str.day
# hours   = int(utc_time_str[1].split(':')[0])
# minutes = int(utc_time_str[1].split(':')[1])
# seconds = int(utc_time_str[1].split(':')[2])
# dt = datetime(years, 1, 1, hours, minutes, seconds) + timedelta(days=(days-1))
# dt = datetime(utc_time_str.year, 1, 1, utc_time_str.hour, utc_time_str.minute, utc_time_str.second) + timedelta(days=(days-1))
utc_time = datetime.now().timestamp()

    

# print(timedelta(days=(days-1)))
# print(dt)
print(utc_time)