from setuptools import setup


setup(name='degg_measurements',
      version='0.1',
      description='Collection of scripts to take data with D-Eggs' +
                  'and analyze it.',
      author='Icehap',
      url='https://github.com/icehap/degg_measurements',
      install_requires=['numpy', 'pandas', 'tqdm', 'tables',
                        'matplotlib', 'click', 'scipy',
                        'gspread', 'oauth2client', 'gitpython',
                        'zmq', 'termcolor', 'slackclient',
                        'paramiko', 'IPython', 'pyserial'],
      packages=['degg_measurements'])
