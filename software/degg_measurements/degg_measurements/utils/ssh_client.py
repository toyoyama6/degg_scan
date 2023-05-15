import os
import subprocess
import paramiko
import stat
import uuid
from getpass import getuser, getpass

from degg_measurements.utils import rerun_after_exception
from paramiko.ssh_exception import SSHException


class SSHClient(object):
    def __init__(self, hostname, username=None, auto_add=True,
                 user_config_file='~/.ssh/config'):
        self.hostname = hostname
        if username is None:
            self.username = getuser()
        else:
            self.username = username

        self.connected = False
        self.client = paramiko.SSHClient()
        self.client.load_host_keys(
            os.path.expanduser('~/.ssh/known_hosts'))

        self.ssh_config = paramiko.SSHConfig()
        user_config_file = os.path.expanduser(user_config_file)
        if os.path.exists(user_config_file):
            with open(user_config_file) as f:
                self.ssh_config.parse(f)

        if auto_add:
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        self.pw_dict = {}

    def __connect__(self, hostname=None, username=None, port=None):
        if not self.connected:
            if hostname is None:
                hostname = self.hostname
            if hostname is None:
                raise ValueError('Either a default is needed or '
                                 '"hostname" has to be passed!')
            cfg = {'hostname': hostname,
                   'username': username}
            if hostname in self.ssh_config.get_hostnames():
                host_cfg = self.ssh_config.lookup(hostname)
                for k in ['hostname', 'user', 'identityfile']:
                    if k in host_cfg.keys():
                        if k == 'user':
                            cfg['username'] = host_cfg['user']
                        elif k == 'hostname':
                            cfg['hostname'] = host_cfg['hostname']
                        elif k == 'identityfile':
                            identity_file = str(host_cfg['identityfile'][0])
                            password, key = self.__get_auth__(identity_file)
                            cfg['password'] = password
                            cfg['pkey'] = key
            if 'password' not in cfg.keys():
                cfg['password'] = None
            if 'pkey' not in cfg.keys():
                cfg['pkey'] = None
            if cfg['password'] is None and cfg['pkey'] is None:
                if hostname in self.pw_dict.keys():
                    cfg['password'] = self.pw_dict[hostname]
                else:
                    cfg['password'], _ = self.__get_auth__()
                    self.pw_dict[hostname] = cfg['password']
            if cfg['username'] is None:
                cfg['username'] = self.username
            self.client.connect(**cfg)
            self.connected = True
        else:
            print('Already connected!')

    def __disconnect__(self):
        if self.connected:
            self.connected = False
            self.client.close()
        else:
            print('Not connected. Cannot disconnect!')

    def __get_auth__(self, ident_file=None):
        if ident_file is not None:
            ident_file = os.path.expanduser(ident_file)
            password = None
            try:
                ident_file = paramiko.RSAKey.from_private_key_file(ident_file)
            except paramiko.PasswordRequiredException:
                msg = f'Passphrase for {os.path.basename(ident_file)}'
                pwd = getpass(msg)
                ident_file = paramiko.RSAKey.from_private_key_file(ident_file,
                                                                   pwd)
        if ident_file is None:
            print('No valid key found!')
            msg = 'Login via password: '
            password = getpass(msg)
        return password, ident_file

    def __call__(self, hostname=None, username=None):
        if hostname is not None:
            self.hostname = hostname
        if username is not None:
            self.username = username
        return self

    def __enter__(self):
        self.__connect__()
        return self

    def __exit__(self, type, value, traceback):
        self.__disconnect__()

    @property
    def transport(self):
        return self.client.get_transport()

    @rerun_after_exception(SSHException, 2)
    def run_cmd(self, cmd, hostname=None, username=None):
        with self(hostname=hostname, username=username):
            stdin, stdout, stderr = self.client.exec_command(cmd)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                raise RuntimeError(
                    f'{cmd} finished with {exit_status}!\n'
                    f'stderr: {stdout.channel.recv_stderr(10000)}')

    def __get_file_info__(self, sftp, path):
        try:
            info = sftp.lstat(path)
        except IOError:
            exists = False
            is_dir = False
            try:
                info_dir = sftp.lstat(os.path.dirname(path))
            except IOError:
                dir_exists = False
            else:
                if not stat.S_ISDIR(info_dir.st_mode):
                    raise ValueError(f'{path} is an invalid path!')
                dir_exists = True
        else:
            exists = True
            dir_exists = True
            is_dir = stat.S_ISDIR(info.st_mode)
        return exists, is_dir, dir_exists

    def __get_file_info_local__(self, path):
        try:
            info = os.stat(path)
        except IOError:
            exists = False
            is_dir = False
            try:
                info_dir = os.stat(os.path.dirname(path))
            except IOError:
                dir_exists = False
            else:
                if not stat.S_ISDIR(info_dir.st_mode):
                    raise ValueError(f'{path} is an invalid path!')
                dir_exists = True
        else:
            exists = True
            dir_exists = True
            is_dir = stat.S_ISDIR(info.st_mode)
        return exists, is_dir, dir_exists

    @rerun_after_exception(SSHException, 2)
    def send_file(self,
                  local_path,
                  remote_path,
                  hostname=None,
                  username=None,
                  force=False):
        with self(hostname=hostname, username=username):
            sftp = self.client.open_sftp()
            valid_remote_path = False
            exists, is_dir, dir_exists = self.__get_file_info__(
                sftp, remote_path)

            if exists and not is_dir:
                if not force:
                    raise ValueError(
                        'Remote file already exists (use "force" to override)')
                else:
                    valid_remote_path = True

            elif exists and is_dir:
                remote_path = os.path.join(remote_path,
                                           os.path.basename(local_path))
                exists, _, _ = self.__get_file_info__(
                    sftp, remote_path)
                if exists:
                    if not force:
                        raise ValueError(
                            'Remote file already exists (use "force" to override)')
                    else:
                        valid_remote_path = True
                else:
                    valid_remote_path = True

            elif not exists and not is_dir and dir_exists:
                valid_remote_path = True

            if not valid_remote_path:
                raise ValueError(f'Remote path {remote_path} is invalid!')

            sftp.put(local_path, remote_path)
            return remote_path

    def get_file(self,
                 remote_path,
                 local_path,
                 hostname=None,
                 username=None):
        with self(hostname=hostname, username=username):
            sftp = self.client.open_sftp()
            local_path = os.path.abspath(local_path)

            if os.path.isdir(local_path):
                local_path = os.path.join(
                    local_path,
                    os.path.basename(remote_path))

            sftp.get(remote_path, local_path)
        return local_path

    def __create_tarball__(self,
                           in_path,
                           out_file,
                           hostname=None,
                           username=None,
                           local=True):
        if local:
            in_path = os.path.abspath(in_path)
            in_path_infos = self.__get_file_info_local__(in_path)
            with self(hostname=hostname, username=username):
                sftp = self.client.open_sftp()
                out_file_infos = self.__get_file_info__(sftp, out_file)
        else:
            with self(hostname=hostname, username=username):
                sftp = self.client.open_sftp()
                in_path_infos = self.__get_file_info__(sftp, in_path)
            out_file_infos = self.__get_file_info_local__(out_file)

        if in_path_infos[0] and in_path_infos[1]:
            target_dir = os.path.dirname(in_path)
            target = os.path.basename(in_path)
        else:
            raise ValueError(f'{in_path} is not a directory!')

        if not out_file_infos[0] and out_file_infos[1]:
            raise ValueError(f'{out_file} is not a directory!')

        unique_ext = str(uuid.uuid4())
        output_file = os.path.join(out_file, f'{unique_ext}{target}.tar.gz')

        cmd = f'tar -zvcf {output_file} -C {target_dir} {target}'
        if local:
            args = cmd.split(' ')
            with open(os.devnull, 'w') as devnull:
                subprocess.Popen(args,
                                 stdout=devnull,
                                 stderr=subprocess.STDOUT).wait()

        else:
            self.run_cmd(cmd)
        return output_file

    def __extract_tarball__(self,
                            in_file,
                            out_path,
                            hostname=None,
                            username=None,
                            local=True):
        cmd = f'tar -xvzf {in_file} -C {out_path}'
        if local:
            args = cmd.split(' ')
            with open(os.devnull, 'w') as devnull:
                subprocess.Popen(args, stdout=devnull,
                                 stderr=subprocess.STDOUT).wait()
        else:
            self.run_cmd(cmd)

    def send_directory(self,
                       local_path,
                       remote_path,
                       hostname=None,
                       username=None,
                       force=True):
        target_dir = os.path.dirname(local_path)
        with self(hostname=hostname, username=username):
            sftp = self.client.open_sftp()
            exists, is_dir, dir_exists = self.__get_file_info__(sftp, remote_path)
            if not is_dir and dir_exists:
                raise ValueError('Can only extract tarball in an existing directory!')

            tarball_file = self.__create_tarball__(local_path,
                                                   target_dir,
                                                   local=True)
            remote_tarball_file = self.send_file(tarball_file, remote_path)
            self.__extract_tarball__(remote_tarball_file,
                                     remote_path,
                                     local=False)
            self.run_cmd(f'rm -f {remote_tarball_file}')
            os.remove(tarball_file)

    def send_tarball(self,
                     local_path,
                     remote_path,
                     hostname=None,
                     username=None,
                     force=True):
        target_dir = os.path.dirname(local_path)
        with self(hostname=hostname, username=username):
            sftp = self.client.open_sftp()
            exists, is_dir, dir_exists = self.__get_file_info__(sftp, remote_path)

            tarball_file = self.__create_tarball__(local_path,
                                                   target_dir,
                                                   local=True)
            remote_tarball_file = self.send_file(tarball_file, remote_path)
            os.remove(tarball_file)

    def get_directory(self,
                      remote_path,
                      local_path,
                      hostname=None,
                      username=None,
                      force=True):
        target_dir = os.path.dirname(remote_path)
        with self(hostname=hostname, username=username):
            tarball_file = self.__create_tarball__(remote_path,
                                                   target_dir,
                                                   local=False)
            local_tarball_file = self.get_file(tarball_file, local_path)
            self.__extract_tarball__(local_tarball_file,
                                     local_path,
                                     local=True)
            self.run_cmd(f'rm -f {tarball_file}')
            os.remove(local_tarball_file)


