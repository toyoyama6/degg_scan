"""Access tool for ICM EEPROM and mainboard EEPROM."""
# requires Python3

import argparse
import sys

import icm_maxim_eeprom as ep
from icmnet import ICMNet


def main():
    # Parse command-line options
    ap = argparse.ArgumentParser
    parser = ap(description=__doc__,
                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--clear', action='store_true', default=False,
                        help='clear EEPROM contents')
    parser.add_argument('--configuration', '--cfg',
                        help=f'specify configuration file, else search '
                             f'{ep.CONFIG_SEARCH_PATH}')
    parser.add_argument('--Debug', action='store_true', default=False,
                        help='enable debug output')
    parser.add_argument('--dump', action='store_true', default=False,
                        help='dump raw EEPROM contents')
    parser.add_argument('--eeprom', default=ep.EEPROM_MAINBOARD,
                        help='Target EEPROM device: %s or %s' % (
                            ep.EEPROM_MAINBOARD, ep.EEPROM_ICM))
    parser.add_argument('--host', default='localhost',
                        help='connect to host')
    parser.add_argument('--list', action='store_true', default=False,
                        help='List formatted EEPROM contents')
    parser.add_argument('-p', '--port', type=int, default=6000,
                        help='domnet command port')
    parser.add_argument('--quiet', action='store_true', default=False,
                        help='Do not print information messages')
    parser.add_argument('--read', help='Read field')
    parser.add_argument('--test_pattern', action='store_true', default=False,
                        help='Write test pattern: value = offset')
    parser.add_argument('-w', '--wp_addr', type=int, required=True,
                        help='target this wire pair address (required)')
    parser.add_argument('--write', help='Write FIELD=VALUE')
    args = parser.parse_args()

    if args.eeprom not in [ep.EEPROM_MAINBOARD, ep.EEPROM_ICM]:
        raise Exception(f'--eeprom value must be '
                        f'{ep.EEPROM_MAINBOARD} (default) or {ep.EEPROM_ICM}')

    icms = ICMNet(args.port, host=args.host)  # Connect to FH server
    if not args.quiet:
        print(f'Connect to command server {args.host}:{args.port}')

    eeprom = ep.IcmMaximEeprom(icms, eeprom=args.eeprom,
                               config_file=args.configuration,
                               debug=args.Debug, device=args.wp_addr,
                               quiet=args.quiet)
    if args.dump:
        eeprom.dump()
    elif args.clear:
        eeprom.clear()
    elif args.test_pattern:
        eeprom.write_test_pattern()
    elif args.list:
        eeprom.list()
    elif args.read:
        value = eeprom.read(args.read)
        print(value)
    elif args.write:
        (field, sep, value) = args.write.partition('=')
        if not value:
            parser.print_help(sys.stderr)
            sys.exit(1)
        eeprom.write(field, value)

    sys.exit(0)


if __name__ == "__main__":
    main()
