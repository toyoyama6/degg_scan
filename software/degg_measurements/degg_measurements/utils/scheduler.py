import configparser
from importlib import import_module
import os

from degg_measurements.utils.master_tools import open_json

class Scheduler(object):
    def __init__(self, recover=False):
        self._task_list = []
        self._task_title_list = []
        self._task_arg_list = []
        self._backup_task = None
        self._backup_kwargs = None
        self._backup_list = []
        self._run_file = None
        self._verbose = False
        self._recover = recover
        self._recovery_task_title_list = []
        self._config_file = None
        self._run_key = None
        self._pdf_obj = None

        self._fat_str = 'MasterFAT_00'

    ##make sure that you can't repeat an FAT run without running with recover
    def check_valid_option(self):
        if self._recover == True:
            return True
        elif self._recover == False:
            current_dict = open_json(self._run_file, verbose=False)
            for key in current_dict.keys():
                if key == self._fat_str:
                    print('MasterFAT entry already in json file! Run with --recover !')
                    raise ValueError('Run with --recover instead')
            return True

        else:
            raise ValueError(f'Value for recover is invalid!: {self.recover}')

    def set_config_file(self, config_file):
        if self._config_file != None:
            raise Warning(f"Config File already configured: {self._config_file}!")
        if not os.path.isfile(config_file):
            raise IOError(f'Path to config_file is not valid!')
        self._config_file = config_file

    def get_config_file(self):
        return self._config_file

    def set_pdf_obj(self, pdf_obj):
        if self._pdf_obj != None:
            raise Warning(f"PDF Object File not none!")
        if pdf_obj != None:
            self._pdf_obj = pdf_obj

    def get_pdf_obj(self):
        return self._pdf_obj

    def set_run_key(self, key):
        if key != None:
            self._run_key = key

    def get_run_key(self):
        key = self._run_key
        if key == None:
            raise ValueError(f'Key Value is {key}!')
        else:
            return key

    def set_run(self, run_file):
        if self._run_file != None:
            raise Warning(f'Run File already configured: {self._run_file}!')
        string = run_file.split(".")
        string = string[-1]
        if string != 'json':
            raise IOError(f'Make sure run_file is json format!')
        if not os.path.isfile(run_file):
            raise IOError(f'Path to run_file is not valid!')
        self._run_file = run_file

    def get_run(self):
        return self._run_file

    def verbosity(self):
        return self._verbose

    def enable_recovery(self):
        self._recover = True

    def recovery(self):
        return self._recover

    def set_recovery_task_title_list(self, r_list):
        if len(r_list) == 0:
            raise ValueError(f'Recovery list size is 0!: {r_list}')

        ##r_list has attached numbers in the format [#] name_of_task
        ##slice away these numbers
        new_r_list = [''] * len(r_list)
        for i, r in enumerate(r_list):
            _r = r.split(" ")[-1]
            new_r_list[i] = _r

        self._recovery_task_title_list = new_r_list
        print("Recovery task list configured")

    def resolve_recovery(self):
        r_list = self._recovery_task_title_list
        t_list = self._task_title_list
        tasks = self._task_list
        args = self._task_arg_list
        if len(r_list) == 0 or len(t_list) == 0:
            raise ValueError('No resolution to recovery possible' +
                             '- lists size 0')
        if r_list == t_list:
            raise ValueError('Recovery list same as run list! '+
                             'No need to run in recovery mode')


        print("Updating task list to recovery task list")
        ##lists are both sorted and sequential
        ##so just get first valid task
        new_start_ind = t_list.index(r_list[0])
        new_tasks = tasks[new_start_ind:]
        new_args  = args[new_start_ind:]
        new_tasks_title = t_list[new_start_ind:]
        self._task_list = new_tasks
        self._task_arg_list = new_args
        self._task_title_list = new_tasks_title

        '''
        for r in r_list:
            ind = t_list.index(r)
            this_task = tasks[ind]
            this_args = args[ind]
        '''

    def set_backup_task(self, task, kwargs=None):
        self._backup_task = task
        self._backup_kwargs = kwargs

    def get_task_list(self):
        task_list = self._task_list
        return task_list

    def get_task_title_list(self):
        task_title_list = self._task_title_list
        return task_title_list

    def get_task_arg_list(self):
        task_arg_list = self._task_arg_list
        return task_arg_list

    def add_task(self, task, title, args=None, run_backup=False):
        self._task_list.append(task)
        self._task_title_list.append(title)
        if args is None:
            print(f"Warning {task} has arguments None")
        self._task_arg_list.append(args)
        self._backup_list.append(run_backup)

    def execute_task(self, task_title):
        task_list = self._task_list
        task_title_list = self._task_title_list
        task_arg_list = self._task_arg_list
        index = task_title_list.index(task_title)
        if len(task_arg_list[index]) == 0:
            task_list[index](self._run_file)
        else:
            task_list[index](self._run_file, *task_arg_list[index])
        if self._backup_task is None:
            raise ValueError('Scheduler backup_task not configured!')
        elif self._backup_task is not None:
            if self._backup_list[index]:
                self._backup_task(**self._backup_kwargs)

    def execute_analysis(self, task_title):
        task_list = self._task_list
        task_title_list = self._task_title_list
        task_arg_list = self._task_arg_list
        index = task_title_list.index(task_title)
        info = task_list[index](self._run_file, self._pdf_obj, *task_arg_list[index])
        return info

    def get_task_string(self, task):
        task_str = str(task)
        task_str = task_str.split(" ")
        task_str = task_str[1]
        return task_str

    def get_task_print_string(self, task, task_num):
        task_str = str(task)
        task_str = task_str.split(" ")
        if len(task_str) != 1:
            task_str = task_str[1]
        else:
            task_str = task_str[0]
        print_task_str = "[" + str(task_num) + "] " + str(task_str)
        return print_task_str

    def delete_task_list(self):
        self._task_list = []
        return True

    def delete_task_arg_list(self):
        self._task_arg_list = []
        return True

    def get_config_verbosity(self, constants):
        try:
            verbose = bool(constants['verbose'])
            if verbose not in [True, False]:
                raise ValueError(f"Use True/False for verbosity! ({verbose})")
            self._verbose = verbose
        except:
            self._verbose = False

    def get_config_run(self, constants):
        keys = constants.keys()
        for key in keys:
            if key == 'run_file':
                run_file = constants[key]
        self.set_run(run_file)
        if self._run_file == None:
            raise ValueError('Run file could not be set from configuration file!')

        print(self._run_file)

    ##----------------------------------------------------------------------
    ##modules are imported and need to be added to the schedule
    ##fragments semi-automate adding to the schedule outside the config
    ##----------------------------------------------------------------------
    def get_modules_and_fragments(self, config):
        sections = config.sections()
        run_backup = True
        for sec in sections:
            if sec == 'constants':
                continue
            keys = config[sec].keys()
            args = []
            _task = False
            _frag = False
            for key in keys:
                if key == 'task':
                    action = config[sec]['task']
                    _task = True
                    continue
                if key == 'fragment':
                    action = config[sec]['fragment']
                    _frag = True
                    continue
                if key == 'run_backup':
                    run_backup = bool(config[sec]['run_backup'])
                    continue
                if key == 'package':
                    continue
                ##get the argument values
                if config[sec][key].lower() == 'true':
                    args.append(True)
                elif config[sec][key].lower() == 'false':
                    args.append(False)
                else:
                    args.append(config[sec][key])

            if _task == False and _frag == False:
                raise ValueError(f'In {sec} no valid task or fragment found!')
            if _task == True and _frag == True:
                raise ValueError(f'In {sec} cannot be both task and fragment!')

            module = import_module(str(config[sec]['package']))
            func = getattr(module, action)
            if _task == True:
                self.add_task(func, sec, args, run_backup=run_backup)
            if _frag == True:
                func(self, sec, *args)

    def get_schedule_from_file(self, config_file):
        config = configparser.ConfigParser()
        config.read(config_file)
        sections = config.sections()
        ##just get constants
        for sec in sections:
            if sec == 'constants':
                constants = config[sec]
                break
        self.get_config_run(constants)
        self.get_config_verbosity(constants)
        self.set_config_file(config_file)
        self.get_modules_and_fragments(config)
        valid = self.check_valid_option()
        self._valid = valid

##end
