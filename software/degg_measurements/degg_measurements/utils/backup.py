from degg_measurements.utils import SSHClient
import os
import time


def run_backup(local_path, remote_folder, run_number, remote_filename):
    if not remote_filename.endswith('.tar.gz'):
        raise ValueError(f'remote_filename is expected to end with .tar.gz')
    timestamp = int(time.time())
    remote_filename = remote_filename.replace('.tar.gz', f'_{timestamp}.tar.gz')
    remote_path = os.path.join(remote_folder, f'run_{run_number:05d}',
                               remote_filename)
    ssh_client = SSHClient('grappa')
    ssh_client.run_cmd(f'mkdir -p {os.path.dirname(remote_path)}')
    ssh_client.send_tarball(local_path, remote_path)

if __name__ == '__main__':
    local_path = '/home/scanbox/data/json'
    remote_path = '/misc/disk19/users/icecube/fat_backup'
    run_backup(local_path, remote_path, run_number=123,
               remote_filename='run_json.tar')

