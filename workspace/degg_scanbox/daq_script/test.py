import click
from daq_script.measure_2d import save_degg_data
from measure_2d import setup_degg, measure_degg_charge_stamp,save_degg_data


def test(run_json, comment):

    nevents = 100000

    ##initialise DEgg settings
    config_threshold0 = 100 ##units of ADC
    config_threshold1 = 6000 ##units of ADC

    measure_mode = 'stamp'
    degg, degg_dict, degg_file = setup_degg(run_json, '.', measure_mode, 
            nevents, config_threshold0, config_threshold1)

    measure_degg_charge_stamp(degg, nevents)

    save_degg_data(degg, measure_mode, '.')
    


@click.command()
@click.argument('run_json')
@click.argument('comment')

def main(run_json, comment):
    test(run_json, comment)

if __name__ == "__main__":
    main()
##end
