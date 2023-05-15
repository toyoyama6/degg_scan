import sys
from concurrent.futures import ProcessPoolExecutor, wait
import numpy as np

from degg_measurements.utils import MFH_SETUP_CONSTANTS

if (sys.version_info.major == 3 and
    sys.version_info.minor < 10):
    from collections import Iterable
else:
    from collections.abc import Iterable


def run_jobs_with_mfhs(func, n_jobs, force_static=[],
                       n_wirepairs=None,
                       **kwargs):
    if n_wirepairs is None:
        n_wirepairs = MFH_SETUP_CONSTANTS.n_wire_pairs
    n_per_wp = int(MFH_SETUP_CONSTANTS.in_ice_devices_per_wire_pair)
    aggregated_results = []

    static = []
    dynamic = []
    dynamic_lens = []
    for keyword in kwargs.keys():
        if keyword in force_static:
            static.append(keyword)
        elif (isinstance(kwargs[keyword], Iterable) and not
                (isinstance(kwargs[keyword], str) or
                 isinstance(kwargs[keyword], dict))):
            dynamic.append(keyword)
            dynamic_lens.append(len(kwargs[keyword]))
        else:
            static.append(keyword)

    if len(np.unique(dynamic_lens)) > 1:
        raise ValueError(
            f'Could not determine which parameters to run in dynamic '
            f'mode. Please provide iterables with the same length '
            f'instead of {dynamic_lens} for {dynamic}.')

    static_kwargs = dict(zip(static, [kwargs[stc] for stc in static]))

    for i in range(n_per_wp):
        wp_slice = slice(i, None, n_per_wp)
        dyn_sliced = dict()
        for dyn in dynamic:
            dyn_sliced[dyn] = kwargs[dyn][wp_slice]

        if len(dyn_sliced[dyn]) == 0:
            # if dyn_sliced is empty, skip this iteration
            continue

        with ProcessPoolExecutor(max_workers=int(n_jobs)) as executor:
            futures = []
            n_iterations = np.minimum(
                n_wirepairs,
                np.ceil(np.unique(dynamic_lens)[0]/n_per_wp))
            for j in range(int(n_iterations)):
                dyn_j = dict(zip(dynamic, [dyn_sliced[dyn][j] for dyn in dynamic]))
                func_kwargs = dyn_j
                func_kwargs.update(static_kwargs)

                futures.append(
                    executor.submit(
                        func,
                        **func_kwargs
                    )
                )
        results = wait(futures)
        aggregated_results.extend(results.done)
    return aggregated_results

