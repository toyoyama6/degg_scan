from thorlabs_apt_device import BSC201
import time

class HDR50(BSC201):

    def __init__(self, serial_port=None, vid=None, pid=None, manufacturer=None, product=None, serial_number="40", location=None, home=True, invert_direction_logic=False, swap_limit_switches=True):

        super().__init__(serial_port=serial_port, vid=vid, pid=pid, manufacturer=manufacturer, product=product, serial_number=serial_number, location=location, home=home, invert_direction_logic=invert_direction_logic, swap_limit_switches=swap_limit_switches)

        self.set_velocity_params(acceleration=4506, max_velocity=8987328)
        self.set_jog_params(size=75091, acceleration=4506, max_velocity=8987328)
        self.set_home_params(velocity=8987328, offset_distance=0)

    def move_absolute(self, degree=None, now=True, bay=0, channel=0):

        position = degree * 75091

        return super().move_absolute(position=position, now=now, bay=bay, channel=channel)

    def move_jog(self, step=None, direction="forward", bay=0, channel=0):

        step = step * 75091

        if(step!=None):
            self.set_jog_params(size=step, acceleration=4030885, max_velocity=4030885)

        return super().move_jog(direction=direction, bay=bay, channel=channel)

    def move_relative(self, degree=None, now=True, bay=0, channel=0):

        distance = degree * 75091

        return super().move_relative(distance=distance, now=now, bay=bay, channel=channel)

    def get_positoin_status(self):

        angle = self.status["position"]/75091

        return angle


    def wait_up(self):
        pos = int(self.status["position"])

        while True:
            print('Moving now ...(^_^)...')
            time.sleep(2)
            now = pos - int(self.status["position"])
            if(now==0):
                print(self.status["position"])
                break
            pos = int(self.status["position"])

    def turn_on(self):

        self.set_enabled(True)

        return 0

    def turn_off(self):

        self.set_enabled(False)

        return 0