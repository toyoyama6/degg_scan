import gspread
from oauth2client.service_account import ServiceAccountCredentials as SAC
import pandas as pd
import numpy as np
import os
import time

from termcolor import colored

CRED_FILE = os.path.join(
    os.path.dirname(__file__),
    'credentials/degg-spreadsheet-aee2cc2407b0.json')
SCOPE = ['https://spreadsheets.google.com/feeds']
SHEET_URL = ('https://docs.google.com/spreadsheets/d/' +
             '106HVuN8rGGZCn-_r0ItVK2oeUPXQEeolRWAkIeqb0EQ/'
             'edit#gid=113019555')
CACHE_FILE = os.path.join(
    os.path.dirname(__file__),
    'cache/logbook_cache.hdf'
)


class DEggLogBook(object):
    def __init__(self,
                 sheet_url=SHEET_URL,
                 path_to_cred=CRED_FILE,
                 cache_file=CACHE_FILE,
                 update_cache=False):
        self.cache_file = cache_file
        cached = self._check_cache()
        if not cached or update_cache:
            #  Reload the logbook from google drive
            creds = SAC.from_json_keyfile_name(path_to_cred, SCOPE)
            client = gspread.authorize(creds)
            self._sheets = client.open_by_url(sheet_url)
            self._sheets_to_skip = ['to_start']
            self.to_pandas()
            del self._sheets
            # Update the cache
            self._update_cache()
        else:
            # Load the dfs from cache
            print('Found a cached logbook!')
            self._load_from_cache()

    def _check_cache(self):
        if not os.path.isfile(self.cache_file):
            print('Logbook cache not found! Recaching!')
            return False
        else:
            modification_time = os.path.getmtime(self.cache_file)
            current_time = time.time()
            delta_t = current_time - modification_time
            sec_per_day = 60 * 60 * 24
            if delta_t / sec_per_day > 1:
                print('Logbook cache older than 1 day! Recaching!')
                return False
            else:
                return True

    def _update_cache(self):
        try:
            for key, df in self.dfs.items():
                df = df.drop(columns=[''], errors='ignore')
                df.to_hdf(self.cache_file, key=key)
        except:
            print('Error updating the cache. Cache will be cleared!')
            os.remove(self.cache_file)
            raise
        else:
            print('Logbook cache updated!')

    def _load_from_cache(self):
        self.dfs = {}
        with pd.HDFStore(self.cache_file) as store:
            for key in store.keys():
                # Remove prepended slash in keynames from pandas
                self.dfs[key[1:]] = store[key]
        return self.dfs

    def _check_headers(self, headers):
        lengths = [len(head) for head in headers]
        passed = False
        if len(np.nonzero(lengths)[0]) >= 2:
            passed = True
        return passed

    def to_pandas(self):
        dfs = {}
        for sheet in self._sheets.worksheets():
            title = sheet.title
            title = title.lower()
            title = title.replace(' ', '_')
            if title in self._sheets_to_skip:
                continue
            data = sheet.get_all_values()

            found_headers = False
            while not found_headers:
                headers = data.pop(0)
                found_headers = self._check_headers(headers)
            dfs[title] = pd.DataFrame(data, columns=headers)
        self.dfs = dfs
        return dfs

    def get_serial_number_from_pmt(self, pmt_name):
        pmt_name = pmt_name.lower()
        sheets_to_check = ['half_d-egg_for_dvt',
                           'half_d-egg_batch#1',
                           'half_d-egg_batch#2',
                           'half_d-egg_batch#3']
        serial = None
        for sheet in sheets_to_check:
            df = self.dfs[sheet]
            mask = df['PMT'].str.lower() == pmt_name
            if np.sum(mask) == 0:
                continue
            serial = df.loc[mask, 'Serial number'].values[0]
            if serial is not None:
                break
        if serial is None:
            print(colored(f"degg_logbook - {pmt_name}: Error for missing pmt temporarily removed", 'red'))
            serial = 'TEST-VAL'
            #raise ValueError(f'PMT {pmt_name} not found in ' +
            #                 f'the sheets {sheets_to_check}!')
        return serial

    def get_degg_serial_number_from_pmt(self, pmt_name):
        half_degg_serial = self.get_serial_number_from_pmt(pmt_name)
        sheets_to_check = ['d-egg_batch#1',
                           'd-egg_batch#2',
                           'd-egg_batch#3']
        columns_to_check = ['Serial number (Upper D-Egg half)',
                            'Serial number (Lower D-Egg half)']
        serial = None
        for sheet in sheets_to_check:
            df = self.dfs[sheet]
            for column in columns_to_check:
                mask = df[column].str.lower() == half_degg_serial.lower()
                if np.sum(mask) == 0:
                    continue
                else:
                    serial_vals = df.loc[mask, 'Serial number'].values
                    if len(serial_vals) > 1:
                        print(
                            f'Found {len(serial_vals)} D-Egg serial numbers ' +
                            f'matching PMT {pmt_name}: {serial_vals}'
                        )
                        # Find number of unique D-Egg IDs with potentially
                        # different versions
                        n_unique = len(np.unique(
                            [s.split('_')[0] for s in serial_vals])
                        )
                        if n_unique > 1:
                            raise ValueError(
                                f'Found more than one unique D-Egg serial '
                                f'number for PMT {pmt_name}. '
                                f'Matching D-Egg serial numbers are: '
                                f'{serial_vals}. \n'
                                f'Make sure you understand why this happens '
                                f'and come up with a solution to resolve '
                                f'this ambiguity.'
                            )
                        else:
                            # Figure out the index of the highest version
                            vs = [
                                int(s.split('_v')[-1])
                                if len(s.split('_v')) == 2 else 0
                                for s in serial_vals
                            ]
                            index = np.argmax(vs)
                            serial = serial_vals[index]
                    else:
                        serial = serial_vals[0]
                    break
        if serial is None:
            print(f'Could not find degg serial number from {pmt_name}')
        return serial

    def get_degg_serial_number_from_mainboard(self, mb_name):
        sheets_to_check = ['d-egg_batch#1',
                           'd-egg_batch#2',
                           'd-egg_batch#3']
        columns_to_check = ['Mainboard']
        serial = None
        for sheet in sheets_to_check:
            df = self.dfs[sheet]
            for column in columns_to_check:
                mask = df[column].str.lower() == mb_name.lower()
                if np.sum(mask) == 0:
                    continue
                else:
                    serial = df.loc[mask, 'Serial number'].values[0]
                    break
        if serial is None:
            print(f'Could not find degg serial number from {mb_name}')
        return serial

    def get_mainboard_serial_number(self, mb_name):
        sheets_to_check = ['degg-mainboard']
        columns_to_check = ['Label number']
        serial = None
        for sheet in sheets_to_check:
            df = self.dfs[sheet]
            for column in columns_to_check:
                mask = df[column].str.lower() == mb_name.lower()
                if np.sum(mask) == 0:
                    continue
                else:
                    serial = df.loc[mask, 'Serial number'].values[0]
                    break
        if serial is None:
            print(f'Could not find mainboard serial number from {mb_name}')
        return serial

    def get_camera_ring_from_camera_id(self, camera_id):
        camera_id = camera_id.lower()
        sheets_to_check = ['degg_camera_ring']
        columns_to_check = ['Camera 1', 'Camera 2', 'Camera 3']
        ring = None
        for sheet in sheets_to_check:
            df = self.dfs[sheet]
            #for k in df.keys():
            #    print(k)
            #exit(1)


            for column in columns_to_check:
                mask = df[column] == camera_id
                if np.sum(mask) == 0:
                    continue
                #ring = df.loc[mask, 'Camera Ring'].values[0].lower()
                ring = df.loc[mask, 'Serial number'].values[0].lower()
                if ring is not None:
                    break
        if ring is None:
            raise ValueError(f'Camera {camera_id} not found in ' +
                             f'the sheets {sheets_to_check}!')
        return ring

    def get_degg_id_from_camera_id(self, camera_id):
        camera_id = camera_id.lower()
        sheets_to_check = ['degg-camera-ring']
        columns_to_check = ['Camera 1', 'Camera 2', 'Camera 3']
        serial = None
        for sheet in sheets_to_check:
            df = self.dfs[sheet]
            #for k in df.keys():
            #    print(k)
            #exit(1)

            for column in columns_to_check:
                mask = df[column] == camera_id
                if np.sum(mask) == 0:
                    continue
                #serial = df.loc[mask, 'Camera Ring'].values[0].lower()
                serial = df.loc[mask, 'Serial number'].values[0].lower()
                if serial is not None:
                    break
        if serial is None:
            raise ValueError(f'Camera {camera_id} not found in ' +
                             f'the sheets {sheets_to_check}!')
        return serial

    ##get D-Egg information from the MB flashID
    def get_degg_from_flashID(self, flashID, sheets_to_check):
        print("WARNING - flashIDs were found to be non-unique")
        if flashID == -1:
            print("Passed in flashID is -1")
            print("Exiting")
            exit(1)

        for sheet in sheets_to_check:
            df = self.dfs[sheet]
            id_column = df['FlashID']
            row = df.loc[id_column == flashID]
            num_rows, num_columns = row.shape
            if num_rows == 1:
                return row
            else:
                continue

    def get_degg_from_string(self, matchStr, columnName, sheets_to_check):

        for sheet in sheets_to_check:
            df = self.dfs[sheet]
            id_column = df[columnName]
            row = df.loc[id_column == matchStr]
            num_rows, num_columns = row.shape
            if num_rows == 1:
                return row
            elif num_rows > 1:
                print(f"Found multiple matches for: {matchStr}!!!")
                print(row)
            else:
                continue

        if num_rows == 0:
            raise ValueError('Number of found rows is 0!')

    ##get D-Egg information from the ICM ID
    def get_degg_from_ID(self, icm_id, string_id, matching_string, icm_sheet, sheets_to_check):
        if icm_id == -1:
            raise ValueError("Must provide search with valid search parameter")

        df = self.dfs[icm_sheet]
        try:
            id_column = df[string_id]
            row = df.loc[id_column == icm_id]
        except:
            print(f"WARNING - Could not find: {string_id}")
            exit(1)
        #batch = row["D-Egg batch"]
        lnum = row[matching_string].values[0]

        for sheet in sheets_to_check:
            df = self.dfs[sheet]
            try:
                id_column = df["ICM"]
                row = df.loc[id_column == lnum]
            except:
                print(f"WARNING - Could not find: {lnum} in D-Egg Sheet")
                continue

            num_rows, num_columns = row.shape
            if num_rows == 1:
                return row
            elif num_rows == 2:
                return row
            else:
                continue

        raise IOError("Function exited without returning - could not find this module!")
##end
