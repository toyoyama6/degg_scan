from setuptools import setup, find_packages

setup(name='fatcat_db',
      version='1.0',
      description='Tools for validating json and inserting into the database',
      author='WIPAC',
      url='https://github.com/WIPACrepo/fatcat_db',
      install_requires=[
          'pymongo>=3,<4',
          'python_dateutil',
          'colorama',
          'paramiko',
          #'setuptools_rust==0.11.4',
          #'cryptography==3.3.2',
          #'pynacl==1.4.0',
          #'bcrypt==3.1.7',
          #'paramiko==2.11.0',
      ],
      packages=find_packages()
      )
