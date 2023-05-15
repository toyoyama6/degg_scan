from src.oriental_motor import AZD_AD
import time

driver = AZD_AD(port='/dev/ttyUSB2')

print('hi')
driver.moveRelative(1, 120)
print('hi')
time.sleep(10)
driver.moveToHome(1)