from texttable import Texttable
import click
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
import numpy as np
import json
import datetime
import latextable

##Local Packages
from degg_measurements.utils.scheduler import Scheduler
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils.degg import DEgg
from degg_measurements.utils.analysis import Analysis
##generic functions from master_tools
from degg_measurements.utils.master_tools import open_json

def run_schedule(schedule, deggs):
    verbose = schedule.verbosity()
    current_dict = open_json(schedule.get_run())
    task_list = schedule.get_task_list()
    task_title_list = schedule.get_task_title_list()
    print(task_title_list)
    print("=" * 20) 
    task_num = 0
    ana_info_list = [] 
    for task, task_title in zip(task_list, task_title_list):
        print_task_str = schedule.get_task_print_string(task,
                                                        task_num)
        print(print_task_str)
        task_str = schedule.get_task_string(task)
        dict_task_str = "[" + str(task_num) + "] " + str(task_title)
        ana_info = schedule.execute_analysis(task_title)
        
        ##match and fill DEgg objects with correct analysis
        for info in ana_info:
            degg_name = info.getDEggName()
            match = False
            for d in deggs:
                d_name = d.getDEggSerialNumber()
                if d_name == degg_name:
                    d.addAnalysis(info)
                    match = True
                    break
            if match == False:
                raise KeyError(f'Could not find match for {degg_name}!')

def unpack_info(schedule, deggs):
    n_meas = len(deggs[0].getAnalysisKeys())
    print(f'Number of unique measurements: {n_meas}')
    table = Texttable()
    table.set_cols_align(["c"] * (n_meas + 1))

    #construct each row for the table
    info = []
    header = ["DEgg Name"]
    header = np.append(header, deggs[0].getAnalysisKeys())
    info.append(header)
    for d in deggs:
        row = []
        degg_name = d.getDEggSerialNumber()
        row.append(degg_name)
        keys = d.getAnalysisKeys()
        #get all analyses
        for key in keys:
            ana = d.getAnalysis(key)
            verdict = ana.getVerdict()
            u_verdict = verdict[0]
            l_verdict = verdict[1]
            total_n   = verdict[2]
            u_rate = float(u_verdict/total_n)
            l_rate = float(l_verdict/total_n)
            row.append(f"{u_rate} | {l_rate}")
        info.append(row)

    ##bring all info together
    table.add_rows(info)
    print(table.draw())

    table = Texttable()
    table.set_cols_align(["c"] * 4)
    meta_info = []
    header = ['Run', 'Analysis Time', 'Data Starts From', 'GitSha']
    meta_info.append(header)
    now = datetime.datetime.now().strftime('%Y-%m-%d')
    info = [f'{schedule.get_run()}', f'{now}', f'{deggs[0].getRunStartDate()}', f'{deggs[0].getGitSha()}']
    meta_info.append(info)
    table.add_rows(meta_info)
    print(table.draw())

    import matplotlib
    from matplotlib import rcParams
    #import matplotlib.font_manager
    #rcParams['font.family'] = 'monospace'
    #rcParams['font.monospace'] = ['Terminal']

    tex = latextable.draw_latex(table)
    tex = tex.replace('\n', ' ')
    tex = tex.replace('\t', '')
    tex = tex.replace('_', '\_')

    plt.rc('text', usetex=True)
    #plt.rcParams['figure.constrained_layout.use'] = True
    #import matplotlib
    #matplotlib.rcParams["text.latex.preamble"].append(r'\usepackage{tabularx}')

    fig = plt.figure(figsize=(7.0, 1.2))
    fig.text(0,0,tex)
    schedule.get_pdf_obj().savefig(fig)

def construct_deggs(run_file):
    list_of_deggs = load_run_json(run_file)
    deggs = []
    with open(run_file, 'r') as open_file:
        current_dict = json.load(open_file)
        run_date = current_dict['date']
    for path in list_of_deggs:
        degg_dict = load_degg_dict(path)
        degg = DEgg()
        degg.setDEggSerialNumber(degg_dict['DEggSerialNumber'])
        degg.setPmtSerialNumber(degg_dict['UpperPmt']['SerialNumber'], 'upper')
        degg.setPmtSerialNumber(degg_dict['LowerPmt']['SerialNumber'], 'lower')
        degg.setRunStartDate(run_date)
        degg.setGitSha(degg_dict['GitShortSHA'])
        deggs.append(degg)

    return deggs

##start the main function
@click.command()
@click.argument('config_file')
@click.option('--test', is_flag=True, default=False)
@click.option('--force', is_flag=True)
def main(config_file, test, force):
    ##construct schedule, recover mode False
    schedule = Scheduler(False)
    schedule.get_schedule_from_file(config_file)

    pdf_pages_object = PdfPages('test.pdf')
    deggs = construct_deggs(schedule.get_run())
    schedule.set_pdf_obj(pdf_pages_object)
    
    ##run analyses, insert analysis results to DEgg object
    run_schedule(schedule, deggs)

    ##create_summary
    unpack_info(schedule, deggs)

    ##send to output file (pdf?)
    pdf_pages_object.close()

if __name__ == "__main__":
    main()
##end
