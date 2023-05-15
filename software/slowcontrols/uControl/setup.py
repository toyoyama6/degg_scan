from setuptools import setup

setup(name='uControl',
      version='0.1',
      description='microController-based adjustmnet of freezer or minifiledhub power supply',
      author='Icehap',
      url='https://github.com/icehap/slowcontrols/uControl',
      install_requires=['datetime', 'click', 'OpenCV-python', 'board', 'Adafruit-Blinka', 'Adafruit-PlatformDetect', 'Adafruit-PureIO'],
      packages=['uControl']
)
