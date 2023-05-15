import os
import glob
import json
import subprocess
import logging
import logging.config


# init print and logging settings
#-------------------------------------------------
_here = os.path.dirname(os.path.abspath(__file__))
_filename = os.path.join(_here, 'configs', 'log_config.json')
with open(_filename) as sf:
    _settings = json.load(sf)
USE_OLD_PRINT = _settings['use_old_print']
USE_LOGGER = _settings['use_logger']
PRINT_LEVEL = _settings['old_print_level']
if not USE_OLD_PRINT:
    PRINT_LEVEL = 99
logging.config.dictConfig(_settings['logger_config'])
logger = logging.getLogger('fatcat')
if not USE_LOGGER:
    logger.setLevel(99)
#-------------------------------------------------


def HELP():
    pfprint(3, 'Please contact Matt Kauer (mkauer@icecube.wisc.edu) for help')


class Color:
    try:
        from colorama import Fore, Style, init
        init()
        green   = Fore.GREEN
        yellow  = Fore.YELLOW
        red     = Fore.RED
        cyan    = Fore.CYAN
        magenta = Fore.MAGENTA
        blue    = Fore.BLUE
        white   = Fore.WHITE
        black   = Fore.BLACK
        bold    = Style.BRIGHT
        dim     = Style.DIM
        reset   = Fore.RESET + Style.RESET_ALL
    except:
        green   = ""
        yellow  = ""
        red     = ""
        cyan    = ""
        magenta = ""
        blue    = ""
        white   = ""
        black   = ""
        bold    = ""
        dim     = ""
        reset   = ""


def setVerbosity(verbosity, set_log=True):
    if verbosity.upper() == 'DEBUG':
        print_level = 0
        log_level = logging.DEBUG
    elif verbosity.upper() == 'INFO':
        print_level = 1
        log_level = logging.INFO
    elif verbosity.upper() == 'WARNING':
        print_level = 2
        log_level = logging.WARNING
    elif verbosity.upper() == 'ERROR':
        print_level = 3
        log_level = logging.ERROR
    else:
        print('WARNING: Unknown verbosity setting [{0}]'.format(verbosity))
        print('   Please use debug, info, warning, or error')
        print_level = 1
        log_level = logging.INFO
    if not USE_OLD_PRINT: print_level = 99
    if not USE_LOGGER: log_level = 99
    global PRINT_LEVEL
    PRINT_LEVEL = print_level
    global LOG_LEVEL
    LOG_LEVEL = log_level
    if set_log:
        logger.setLevel(log_level)
    return


def pfprint(level, message):
    
    if isinstance(PRINT_LEVEL, str):
        setVerbosity(PRINT_LEVEL, set_log=False)
    V = PRINT_LEVEL
    
    # for true/false status messages
    if isinstance(level, bool):
        if level is True:
            logger.info(Color.green + message + Color.reset)
            if V <= 1:
                print(Color.green + message + Color.reset)
        else:
            logger.warning(Color.yellow + message + Color.reset)
            if V <= 2:
                print(Color.yellow + message + Color.reset)
    else:
        # for general messages
        if level == 0:
            logger.debug(Color.dim + message + Color.reset)
            if V <= 0:
                print(Color.dim + 'DEBUG: '+message + Color.reset)
        elif level == 1:
            logger.info(message)
            if V <= 1:
                print('INFO: '+message)
        elif level == 2:
            logger.warning(Color.bold + message + Color.reset)
            if V <= 2:
                print(Color.bold + 'WARNING: '+message + Color.reset)
        elif level == 3:
            logger.error(Color.bold + message + Color.reset)
            if V <= 3:
                print(Color.bold + 'ERROR: '+message + Color.reset)
        # for json validation specific messages
        elif level == 10:
            logger.info(Color.green + message + Color.reset)
            if V <= 1:
                print(Color.green + message + Color.reset)
        elif level == 20:
            logger.warning(Color.yellow + message + Color.reset)
            if V <= 2:
                print(Color.yellow + message + Color.reset)
        elif level == 30:
            logger.error(Color.red + message + Color.reset)
            if V <= 3:
                print(Color.red + message + Color.reset)
        else:
            print((Color.red+'ERROR: no handler for pfprint level [{0}] \n'
                  '   message: {1}'+Color.reset)
                  .format(level, message))


def checkRepoVersion():
    pfprint(0, '[{0}] checking fatcat_db git repo'.format(__name__))
    
    output = subprocess.check_output(['git', 'fetch', '--quiet'],
                                    cwd=os.path.dirname(os.path.abspath(__file__)))
    local = subprocess.check_output(['git', 'rev-parse', '--short', 'master'],
                                    cwd=os.path.dirname(os.path.abspath(__file__))
                                    ).decode('ascii').strip()
    remote = subprocess.check_output(['git', 'rev-parse', '--short', 'origin/master'],
                                     cwd=os.path.dirname(os.path.abspath(__file__))
                                     ).decode('ascii').strip()
    if local != remote:
        #print('{0} != {1}'.format(local, remote))
        pfprint(2, 'Local fatcat_db repo [{0}] is not up-to-date with remote [{1}] \n'
                '   Please pull the latest version of fatcat_db'.format(local, remote))
        return False
    else:
        pfprint(1, 'Local fatcat_db repo is up-to-date with remote [{0}]'.format(remote))
        return True

