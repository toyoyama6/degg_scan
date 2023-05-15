from src.oriental_motor import AZD_AD

driver = AZD_AD(port='/dev/ttyUSB2')
driver.moveToHome(1)
driver.moveToHome(2)
driver.moveToHome(3)
driver.moveToHome(4)
driver.moveToHome(5)
