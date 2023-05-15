#!/usr/bin/env python3
"""Configure in-ice xDevice ICM with firmware images"""
import argparse
import ssl
import subprocess as sp
import sys
import urllib.request
from hashlib import md5
from os import makedirs
from os.path import basename, splitext, isfile, isdir, dirname
from pathlib import Path
from pprint import pprint
from time import time, localtime, strftime, sleep
from urllib.parse import urlparse

from icm_flash_writer import ICMFlashWriter
from icmnet import ICMNet

CONFIGURE_FILE = 'icu_in_ice_config.json'
CONFIGURE_URL = 'https://user-web.icecube.wisc.edu/~jweber/icm/configuration/' \
                + CONFIGURE_FILE
CONFIGURATION_DOC = \
    'https://user-web.icecube.wisc.edu/~jweber/icm/configuration/00README.txt'
DEFINITION_URL = \
    'https://github.com/WIPACrepo/ICM-firmware-redux' \
                  '#installation-configuration'
CACHE_DIR = str(Path.home()) + '/' + '.' + basename(splitext(__file__)[0])
DEBUG = False
QUIET = False
BOOT_DELAY = 3.0  # s
GOLDEN_IMAGE_MAX = 1
DEVICE_MIN = 0
DEVICE_FH = 8
DEVICE_MAX = DEVICE_FH
NUM_IMAGES = 8
BIN_DIR = dirname(__file__) or '.'
WRITE_PROT_OFF = BIN_DIR + '/' + 'icm_flash_unlock.py'
MULTIBOOT = BIN_DIR + '/' + 'icm_fpga_reboot.py'

Exec_stdout = sp.DEVNULL
Exec_stderr = None
Arg = argparse.Namespace()


def debug(msg: str) -> None:
    """Output a debugging message if enabled."""
    if Arg.debug:
        ftime = time()  # floating point since Unix epoch
        itime = int(ftime)  # integer since Unix epoch
        fmt = '%H:%M:%S'
        fftime = ftime - itime  # fractional seconds remainder
        timestamp = '%s.%03d' % ((strftime(fmt, localtime(itime)),
                                  int(1000 * fftime)))
        sys.stdout.write(timestamp + ' ')
        sys.stdout.write(msg.rstrip() + '\n')


def info(msg: str) -> None:
    """Output a debugging message if not quiet."""
    if not Arg.quiet:
        sys.stdout.write(msg.rstrip() + '\n')


def error(msg: str):
    """Output an error message."""
    sys.stderr.write(msg.rstrip() + '\n')


def fatal(msg: str) -> None:
    """Output an error message and exit with nonzero status."""
    error(msg)
    sys.exit(1)


def url_download(url: str, file: str, ssl_cert_verify: bool = False) -> None:
    """Download a URL to a local file."""
    ctx = None
    if not ssl_cert_verify:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    debug(f'download {url} -> local {file}, SSL verify: {ssl_cert_verify}')
    with open(file, 'w') as f_out:
        with urllib.request.urlopen(url, context=ctx) as f_in:
            f_out.write(f_in.read().decode('utf-8'))


def md5sum_file(file: str) -> str:
    """Calculate MD5SUM of a local file."""
    with open(file, 'rb') as f:
        data = f.read()
    return md5(data).hexdigest()


def download_images(config: list) -> None:
    """ Check or create image cache. Download images if needed."""
    for ix in range(len(config)):
        if 'image' in config[ix]:
            path = urlparse(config[ix]['image']).path
            file = basename(path)
            local = Arg.cache_dir + '/' + file
            config[ix]['local'] = local
            download = True
            md5_ref = config[ix].get('md5sum')
            if md5_ref is not None:
                if isfile(local):
                    md5_calc = md5sum_file(local)
                    md5_ref = config[ix]['md5sum']
                    debug(f'ix {ix} md5 ref: {md5_ref} calc: {md5_calc}')
                    # Finally compare original MD5 with freshly calculated
                    if md5_ref == md5_calc:
                        download = False
                        info(f're-using local cache {local}, md5sum verified')
                    else:
                        info(f'local cache {local} md5sum failed, downloading')
                else:
                    info(f'local cache {local} not found, downloading')

            if download:
                url_download(config[ix]['image'], local, Arg.ssl_cert_verify)
                if md5_ref is not None:
                    md5_calc = md5sum_file(local)
                    debug(f'index {ix} image {config[ix]["image"]} '
                          f'md5sum {md5_calc} s/b {md5_ref}')
                    if md5_ref == md5_calc:
                        debug(f'debug: index {ix} image {local} md5sum '
                              f'verified')
                    else:
                        fatal(f'index {ix} image {config[ix]["image"]} '
                              f'md5sum {md5_calc} s/b {md5_ref}')


def write_protect_disable() -> None:
    """Disable write protect. Terminate upon failure."""
    args = [WRITE_PROT_OFF, '--host', Arg.host, '--port', str(Arg.port),
            '--wp_addr', str(Arg.wp_addr)]
    try:
        info('attempt to disable write protect for golden image updates')
        debug('run subprogram "%s"' % ' '.join(args))
        sp.run(args, check=True, stdout=Exec_stdout, stderr=Exec_stderr)
        info('write protect disable success')
    except sp.CalledProcessError:
        fatal('write protect disable failure. HW write protect enabled?')


def read_configuration(path: str) -> list:
    """Read the configuration from a local JSON file."""
    from json import loads
    with open(path, 'r') as f:
        config = loads(f.read())
    assert len(config) == NUM_IMAGES, f'{path} has {NUM_IMAGES} images'
    return config


def verify_fw(index: int, config: dict) -> int:
    """Verify firmware version and/or golden image indicator"""
    failures = 0
    fh = ICMNet(host=Arg.host, port=Arg.port)
    version_check = config.get('version_check')
    version_read = fh.request(f'read {Arg.wp_addr} {0xff}')['value']
    if version_check:
        if version_check == version_read:
            info(f'index {index} fw version {version_read} verified')
        else:
            error(f'index {index} fw version {version_read} should be '
                  f'{version_check}')
            failures = failures + 1

    gi_check = config.get('golden_image_indicator_check').lower()
    gi_read = fh.request(f'read {Arg.wp_addr} {0xfe}')['value']
    if gi_check:
        if gi_check == gi_read:
            info(f'index {index} golden image indicator {gi_read} verified')
        else:
            error(f'index {index} golden image indicator {gi_read} should be '
                  f'{gi_check}')
            failures = failures + 1

    return failures


def icm_reprogram(index: int, file: str) -> None:
    """Write the image to the flash index."""
    writer = ICMFlashWriter(Arg.port, Arg.wp_addr, Arg.host, verbose=True)
    writer.program(file, index)


def erase(index: int) -> None:
    """Erase firmware at index."""
    info(f'erase wp_addr {Arg.wp_addr} index {index}')
    assert 1 < index < ICMNet.FH_DEVICE_NUM  # sanity check
    fh = ICMNet(host=Arg.host, port=Arg.port)
    value = index | 0x80  # ICM reg 0x11 ICM_FLASHP_CFG erase-only image
    assert fh.request(f'write {Arg.wp_addr} {0x11} {value}')['status'] == 'OK'
    assert fh.request(f'write {Arg.wp_addr} {0x10} {0x9c}')['status'] == 'OK'
    for _ in range(40):
        val = fh.request(f'read {Arg.wp_addr} {0x14}')['value']
        # ICM reg 0x14 ICM_RCFG_STAT: FLASH_PROG_DONE, SUBPROC_DONE
        if (int(val, 0) & 0xff) == 0xa0:
            return
        sleep(0.2)
    raise Exception(f'unable to erase wp_addr {Arg.wp_addr} index {index}')


def configure(config: list) -> int:
    """Configure the ICM images. This is the primary implementation."""
    default_image = None
    rtn_val = 0
    run_index = None
    for ix in range(Arg.max_image, Arg.min_image - 1, -1):
        local = config[ix].get('local')
        if config[ix].get('default'):
            default_image = ix
        if local is not None:
            info(
                f'configure {Arg.host}:{Arg.port} device {Arg.wp_addr} '
                f'index {ix} <- image {basename(local)}')
            icm_reprogram(ix, local)
        elif Arg.erase:
            erase(ix)
        else:
            info(f'skip device {Arg.wp_addr} unconfigured index {ix}')

        if config[ix].get('version_check') or \
                config[ix].get('golden_image_indicator_check'):
            args = [MULTIBOOT, '--host', Arg.host, '--port', str(Arg.port),
                    '--wp_addr', str(Arg.wp_addr), '--id', str(ix)]
            debug('run subprogram "%s"' % ' '.join(args))
            sp.run(args, check=True, stdout=Exec_stdout, stderr=Exec_stderr)
            run_index = ix
            sleep(BOOT_DELAY)  # TODO better to wait for aliveness from ICM
            rtn_val += verify_fw(ix, config[ix])
            # TODO for now a verification failure is fatal.
            if rtn_val:
                return rtn_val

    if default_image is not None and run_index != default_image:
        local = config[default_image].get('local')
        file = basename(local)
        info(f'reboot to default image index {default_image} file {file}')
        args = [MULTIBOOT, '--host', Arg.host, '--port', str(Arg.port),
                '--wp_addr', str(Arg.wp_addr), '--id', str(default_image)]
        debug('run subprogram "%s"' % ' '.join(args))
        sp.run(args, check=True, stdout=Exec_stdout, stderr=Exec_stderr)

        return rtn_val


def main() -> int:
    """Main program to parse args and configure ICM images."""
    global Arg
    global Exec_stdout
    ap = argparse.ArgumentParser
    desc = __doc__ + ' per the definition ' + DEFINITION_URL + ' . ' + \
    'If the golden image indices 0,1 are to be configured (non default), ' + \
    'then the ICM write protect must also be disabled.'
    parser = ap(description=desc,
                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--cache-dir', default=CACHE_DIR,
                        help='Download files cache directory')
    parser.add_argument('--configuration-url', '--cfg-url',
                        default=CONFIGURE_URL,
                        help='Specify configuration URL')
    parser.add_argument('--debug', '--dbg', action='store_true', default=False,
                        help='Enable debugging output.')
    parser.add_argument('--erase', action='store_true', default=True,
                        help='Erase locations without new images.')
    parser.add_argument('--no-erase', action='store_false', dest='erase',
                        default=False,
                        help='Inhibit erase locations without new images.')
    parser.add_argument('--golden-image', action='store_true', default=False,
                        help='This option is also required to configure '
                             'images 0,1. Write protect must be disabled.')
    parser.add_argument('--host', default='localhost',
                        help='domnet server host')
    parser.add_argument('--local', action='store_true', default=False,
                        help='Use local cached files. Do not download files')
    parser.add_argument('--max-image', type=int, default=NUM_IMAGES - 1,
                        help='Maximum image index')
    parser.add_argument('--min-image', type=int, default=0,
                        help='Minimum image index')
    parser.add_argument('--port', '-p', default=6000, type=int,
                        help='domnet server port')
    parser.add_argument('--quiet', action='store_true', default=False,
                        help='Limit output to errors and significant events')
    parser.add_argument('--show', action='store_true', default=False,
                        help='Show in-ice xDevice canonical ICM firmware '
                        'defined by ' + DEFINITION_URL + ' then exit.\n' + \
                            'The ICM is not altered.')
    parser.add_argument('--ssl-cert-verify', action='store_true',
                        default=False,
                        help='Verify URL SSL certificate')
    parser.add_argument('-w', '--wp_addr', type=int,
                        help='Wire pair address 0-7')
    Arg = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    if Arg.debug:
        Exec_stdout = None

    configuration_path = Arg.cache_dir + '/' + CONFIGURE_FILE
    if Arg.local:
        info(f'Re-using cache directory {Arg.cache_dir}')
        assert isdir(Arg.cache_dir), 'local cache directory must exist'
        assert isfile(configuration_path), 'Cache config file must exist'
    else:
        info(f'Using cache directory {Arg.cache_dir}')
        makedirs(CACHE_DIR, exist_ok=True)
        info(f'Using configuration URL {Arg.configuration_url}')
        url_download(Arg.configuration_url, configuration_path,
                     Arg.ssl_cert_verify)

    config = read_configuration(configuration_path)
    if Arg.show:
        print('Target configuration:')
        pprint(config)
        sys.exit(0)

    if not Arg.golden_image and Arg.min_image <= GOLDEN_IMAGE_MAX:
        Arg.min_image = GOLDEN_IMAGE_MAX + 1  # TODO no overwrite parsed Arg
        info(f'Setting minimum image index to {Arg.min_image} without '
             f'--golden_image option')
    assert \
        0 <= Arg.min_image <= Arg.max_image < NUM_IMAGES, 'invalid image limit'

    if Arg.wp_addr is None:
        error('wire pair address undefined')
        parser.print_usage(sys.stderr)
        sys.exit(1)
    assert DEVICE_MIN <= int(Arg.wp_addr) <= DEVICE_MAX, 'invalid device'

    if Arg.golden_image:
        # TODO read WP status from ICM when the capability has been added.
        write_protect_disable()
    download_images(config)
    return configure(config)


if __name__ == '__main__':
    sys.exit(main())
