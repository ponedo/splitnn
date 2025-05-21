import os
import paramiko
from scp import SCPClient
from concurrent.futures import ThreadPoolExecutor, as_completed

class RemoteMachine:
    def __init__(self, hostname, username, password, port=22, working_dir='/tmp'):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port
        self.working_dir = working_dir
        self.ssh = None
        self.scp = None
        # self.sftp = None

    def connect(self):
        """
        Connects to the remote machine and returns the remote machine identifier (self).
        """
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(self.hostname, port=self.port, username=self.username, password=self.password)
            self.scp = SCPClient(self.ssh.get_transport())
            print(f"Connected to {self.hostname}")
        except Exception as e:
            print(f"Failed to connect to {self.hostname}: {str(e)}")
            return None
        return self

    def execute_command(self, command, output_file=None, use_sudo=False):
        """
        Executes a command on the remote machine.
        Optionally redirects stdout to a file on the remote machine.
        Optionally runs the command with sudo privileges.
        
        :param command: The command to execute.
        :param output_file: Path to the file on the remote machine where stdout should be redirected.
        :param use_sudo: If True, the command will be executed with sudo privileges.
        """
        if self.ssh is None:
            print("Not connected to any remote machine.")
            return None

        try:
            # If sudo is needed, prepend the command with sudo -S and provide the password via stdin
            if use_sudo:
                if output_file:
                    full_command = f"cd {self.working_dir} && echo {self.password} | sudo -E -S {command} > {output_file} 2>&1"
                else:
                    full_command = f"cd {self.working_dir} && echo {self.password} | sudo -E -S {command}"
            else:
                if output_file:
                    full_command = f"cd {self.working_dir} && {command} > {output_file} 2>&1"
                else:
                    full_command = f"cd {self.working_dir} && {command}"

            stdin, stdout, stderr = self.ssh.exec_command(full_command)

            # Capture stderr for any potential errors
            errors = stderr.read().decode()

            if errors and not errors.startswith("[sudo]"):
                print(f"Error occured when executing {full_command}")
                print(f"Errors:\n{errors}\n")
            else:
                if output_file:
                    print(f"Command output has been redirected to {output_file}")
                else:
                    output = stdout.read().decode()
                    return output
        except Exception as e:
            print(f"Failed to execute command: {str(e)}")
            return None


    # def send_file(self, local_file_path, remote_file_path):
    #     """
    #     Sends and overwrites a file to the remote machine.
    #     """
    #     if self.ssh is None:
    #         print("Not connected to any remote machine.")
    #         return None
    #     try:
    #         if self.sftp is None:
    #             self.sftp = self.ssh.open_sftp()

    #         self.sftp.put(local_file_path, remote_file_path)
    #         print(f"File {local_file_path} successfully transferred to {remote_file_path}")
    #     except Exception as e:
    #         print(f"Failed to send file: {str(e)}")
    #         return None

    # def receive_file(self, remote_file_path, local_file_path):
    #     """
    #     Receives a file from the remote machine and saves it to the local machine.
        
    #     :param remote_file_path: Path to the file on the remote machine.
    #     :param local_file_path: Path where the file should be saved on the local machine.
    #     """
    #     if self.ssh is None:
    #         print("Not connected to any remote machine.")
    #         return None

    #     try:
    #         if self.sftp is None:
    #             self.sftp = self.ssh.open_sftp()

    #         self.sftp.get(remote_file_path, local_file_path, recursive=True)
    #         print(f"File {remote_file_path} successfully received and saved to {local_file_path}")
    #     except Exception as e:
    #         print(f"Failed to receive file from {self.hostname}: {str(e)}")
    #         return None

    def send_file(self, local_path, remote_path, recursive=False):
        """
        Sends a file or directory to the remote machine.

        :param local_path: Path to the local file or directory.
        :param remote_path: Path on the remote machine.
        :param recursive: Set to True to send a directory.
        """
        if self.scp is None:
            print("Not connected to any remote machine.")
            return None
        try:
            self.scp.put(local_path, remote_path, recursive=recursive)
            print(f"{local_path} successfully transferred to {remote_path}")
        except Exception as e:
            print(f"Failed to send {local_path}: {str(e)}")
            return None

    def receive_file(self, remote_path, local_path, recursive=False):
        """
        Receives a file or directory from the remote machine.

        :param remote_path: Path to the file or directory on the remote machine.
        :param local_path: Path where the file/directory should be saved on the local machine.
        :param recursive: Set to True to receive a directory.
        """
        if self.scp is None:
            print("Not connected to any remote machine.")
            return None
        try:
            self.scp.get(remote_path, local_path, recursive=recursive)
            print(f"{remote_path} successfully received and saved to {local_path}")
        except Exception as e:
            print(f"Failed to receive {remote_path}: {str(e)}")
            return None

    def close_connection(self):
        """
        Closes the connection to the remote machine.
        """
        # if self.sftp:
        #     self.sftp.close()
        if self.scp:
            self.scp.close()
        if self.ssh:
            self.ssh.close()
        print(f"Connection to {self.hostname} closed.")


def execute_command_on_multiple_machines(machines, commands):
    """
    Executes commands concurrently on multiple machines, with each command executed in its own working directory.
    Optionally executes the commands with sudo privileges.
    
    :param machines: A list of RemoteMachine objects.
    :param commands: A dictionary where the key is the machine hostname and the value is a tuple:
                     (command, working_directory, output_file, use_sudo).
    """
    def execute_on_machine(machine, command, working_dir, output_file=None, use_sudo=False):
        # Change the working directory before executing the command
        machine.working_dir = working_dir
        return machine.execute_command(command, output_file, use_sudo)

    results = {}
    with ThreadPoolExecutor(max_workers=len(machines)) as executor:
        # Submit tasks to execute different commands on different machines with custom working directories
        future_to_machine = {}
        for machine in machines:
            if machine.hostname in commands:
                command_info = commands[machine.hostname]
                
                # Parse the command tuple, which now includes the use_sudo flag
                if len(command_info) == 4:
                    command, working_dir, output_file, use_sudo = command_info
                elif len(command_info) == 3:
                    command, working_dir, output_file = command_info
                    use_sudo = False
                else:
                    command, working_dir = command_info
                    output_file, use_sudo = None, False

                future_to_machine[executor.submit(execute_on_machine, machine, command, working_dir, output_file, use_sudo)] = machine

        # Collect results as they complete
        for future in as_completed(future_to_machine):
            machine = future_to_machine[future]
            try:
                result = future.result()
                if result:
                    results[machine.hostname] = result
                else:
                    if isinstance(commands[machine.hostname], tuple) and len(commands[machine.hostname]) >= 3:
                        results[machine.hostname] = f"Output redirected to {commands[machine.hostname][2]}"
                    else:
                        results[machine.hostname] = "Command executed successfully"
            except Exception as e:
                results[machine.hostname] = f"Error: {str(e)}"

    return results


def send_file_to_multiple_machines(machines, file_paths):
    """
    Sends files concurrently to multiple machines with different local and remote file paths, 
    and waits until all transfers finish.
    
    :param machines: A list of RemoteMachine objects.
    :param file_paths: A dictionary where the key is the machine hostname and the value is a tuple (local_file_path, remote_file_path).
    """
    def send_file_to_machine(machine, local_file_path, remote_file_path, recursive):
        return machine.send_file(local_file_path, remote_file_path, recursive)

    results = {}
    with ThreadPoolExecutor(max_workers=len(machines)) as executor:
        # Submit tasks to send different files to different remote paths on each machine
        future_to_machine = {
            executor.submit(
                send_file_to_machine, machine,
                file_paths[machine.hostname][0],
                file_paths[machine.hostname][1],
                file_paths[machine.hostname][2]
            ): machine
            for machine in machines if machine.hostname in file_paths
        }

        # Collect results as they complete
        for future in as_completed(future_to_machine):
            machine = future_to_machine[future]
            try:
                result = future.result()
                results[machine.hostname] = "File transfer succeeded"
            except Exception as e:
                results[machine.hostname] = f"Error: {str(e)}"

    return results

def receive_file_from_multiple_machines(machines, file_paths):
    """
    Receives files concurrently from multiple machines and saves them to different local paths.
    
    :param machines: A list of RemoteMachine objects.
    :param file_paths: A dictionary where the key is the machine hostname and the value is a tuple:
                       (remote_file_path, local_file_path).
    """
    def receive_file_from_machine(machine, remote_file_path, local_file_path, recursive):
        return machine.receive_file(remote_file_path, local_file_path, recursive)

    results = {}
    with ThreadPoolExecutor(max_workers=len(machines)) as executor:
        # Submit tasks to receive files concurrently from multiple machines
        future_to_machine = {
            executor.submit(
                receive_file_from_machine, machine,
                file_paths[machine.hostname][0],
                file_paths[machine.hostname][1],
                file_paths[machine.hostname][2]
            ): machine
            for machine in machines if machine.hostname in file_paths
        }

        # Collect results as they complete
        for future in as_completed(future_to_machine):
            machine = future_to_machine[future]
            try:
                future.result()
                results[machine.hostname] = f"File received successfully from {machine.hostname}"
            except Exception as e:
                results[machine.hostname] = f"Error: {str(e)}"

    return results
