import subprocess

class DokkuError(Exception):
	def __init__(self, message):
		self.message = message

def dokku_exec(args, **kwargs):
	stdin = subprocess.PIPE if 'stdin' in kwargs else None

	# Start the process, no stdin, redirect stderr to stdout
	proc = subprocess.Popen(args,
		stdout=subprocess.PIPE,
		stderr=subprocess.STDOUT,
		stdin=stdin)
	# Read output
	lines = []

	if 'stdin' in kwargs:
		proc.stdin.write(kwargs['stdin'])
		proc.stdin.close()
	for stdout_line in iter(proc.stdout.readline, ""):
		lines.append(stdout_line)
	proc.stdout.close()
	return_code = proc.wait()
	if return_code:
		raise subprocess.CalledProcessError(return_code, args, '\n'.join(lines))
	return lines


def parse_params(param_list):
	parsed = {}

	for item in param_list:
		(key, value) = item.split('=', 1)
		parsed[key] = value

	return parsed

class DokkuRun(object):
	def __init__(self):
		pass


	def exec_cmd(self, args, **kwargs):
		self.raw_exec_cmd(args, **kwargs)
		return True


	def raw_exec_cmd(self, args, **kwargs):
		try:
			return dokku_exec(['dokku'] + args, **kwargs)
		except subprocess.CalledProcessError as ex:
			raise DokkuError(ex.output)


class Entity(DokkuRun):
	def __init__(self, plugin_name):
		DokkuRun.__init__(self)
		self.plugin_name = plugin_name
		self.params = {}


	def list_raw(self):
		cmd = self.command_base() + 'list'
		return self.raw_exec_cmd([cmd])[1:]


	def list(self):
		return [item.strip().split()[0] for item in self.list_raw()]


	def create_cmd(self, name):
		return [self.command_base() + 'create', name]


	def create(self, name):
		return self.exec_cmd(self.create_cmd(name))


	def destroy_cmd(self, name):
		return ['--force', self.command_base() + 'destroy', name]


	def destroy(self, name):
		return self.exec_cmd(self.destroy_cmd(name))


	def exists(self, name):
		return name in self.list()


	def create_if_not_exists(self, name):
		if not self.exists(name):
			return self.create(name)
		return False


	def destroy_if_exists(self, name):
		if self.exists(name):
			return self.destroy(name)
		return False


	def ensure_state(self, state, name):
		if state == 'present':
			return self.create_if_not_exists(name)
		elif state == 'absent':
			return self.destroy_if_exists(name)


	def command_base(self):
		return self.plugin_name + ':'


	def with_params(self, params):
		self.params = params
		return self


class PluginEntity(Entity):
	def __init__(self):
		Entity.__init__(self, 'plugin')

	def list(self):
		return { split[0]: {
			'version': split[1],
			'status': split[2],
			'description': split[3]
		} for split in [line.strip().split(None, 3) for line in self.list_raw()] }

	def create_cmd(self, name):
		args = [self.command_base() + 'install', self.params['repository']]
		if self.params['commit'] is not None:
			args.extend(['--committish', self.params['commit']])
		args.extend(['--name', name])
		return args


	def create_if_not_exists(self, name):
		if not name in self.list():
			return self.create(name)
		else:
			if self.params['update']:
				return self.update(name)
			else:
				return False


	def destroy_cmd(self, name):
		return [self.command_base() + 'uninstall', name]


	def update(self, name):
		args = [self.command_base() + 'update', name]
		if self.params['commit'] is not None:
			args.extend([self.params['commit']])
		return self.exec_cmd(args)


class PostgresEntity(Entity):
	def __init__(self):
		Entity.__init__(self, 'postgres')


	def list(self):
		return { split[0]: {
			'version': split[1],
			'status': split[2],
			'exposed_ports': None if split[3] == '-' else split[3],
			'links': [] if split[4] == '-' else split[4].split()
		} for split in [line.strip().split(None, 4) for line in self.list_raw()] }


	def ensure_state(self, state, name):
		if state == 'present':
			if self.create_if_not_exists(name):
				return True
			elif self.params['link'] is not None:
				return self.unlink_if_linked(name, self.params['link'])
			else:
				return False
		elif state == 'absent':
			return self.destroy_and_unlink(name, self.params['link'])
		elif state == 'linked':
			if self.params['link'] is None:
				raise ValueError('Missing link name')

			changed = self.create_if_not_exists(name)
			changed = self.link_if_not_linked(name, self.params['link']) or changed
			return changed


	def link_if_not_linked(self, name, link):
		state = self.list()[name]

		if link not in state['links']:
			return self.link(name, link)

		return False


	def unlink_if_linked(self, name, link):
		state = self.list()[name]

		if link in state['links']:
			return self.unlink(name, link)

		return False


	def destroy_and_unlink(self, name, link):
		if not self.exists(name):
			# nothing already
			return False

		# unlink before destroy
		if link is not None:
			self.unlink_if_linked(name, link)

		return self.destroy(name)


	def link(self, name, link):
		return self.exec_cmd([self.command_base() + 'link', name, link])


	def unlink(self, name, link):
		return self.exec_cmd([self.command_base() + 'unlink', name, link])


class StorageEntity(Entity):
	def __init__(self):
		Entity.__init__(self, 'storage')


	def list_raw(self):
		cmd = self.command_base() + 'list'
		try:
			return self.raw_exec_cmd([cmd, self.params['app']])[1:]
		except DokkuError as ex:
			# no storage mounts returns 1
			return []


	def list(self):
		return { line: {
			'host': line.split(':')[0],
			'guest': line.split(':')[1]
		} for line in [item.strip() for item in self.list_raw()]}


	def create_cmd(self, name):
		return [self.command_base() + 'mount', self.params['app'], name]


	def destroy_cmd(self, name):
		return [self.command_base() + 'unmount', self.params['app'], name]


	def ensure_state(self, state):
		return Entity.ensure_state(self, state, "%s:%s" % (self.params['host'], self.params['guest']))


class DomainsEntity(Entity):
	def __init__(self):
		Entity.__init__(self, 'domains')


	def list_raw(self):
		cmd = self.command_base() + 'report'
		if self.params['app'] is not None:
			return self.raw_exec_cmd([cmd, self.params['app'], '--domains-app-vhosts'])[0]
		return self.raw_exec_cmd([cmd, '--domains-global-vhosts'])[0]


	def list(self):
		return self.list_raw().split()


	def create_cmd(self, name):
		if self.params['app'] is not None:
			return [self.command_base() + 'add', self.params['app'], name]
		return [self.command_base() + 'add-global', name]


	def destroy_cmd(self, name):
		if self.params['app'] is not None:
			return [self.command_base() + 'remove', self.params['app'], name]
		return [self.command_base() + 'remove-global', name]


class AppGlobalEntity(DokkuRun):
	def __init__(self, app):
		DokkuRun.__init__(self)
		self.app = app


	def require_app(self):
		if self.is_global():
			raise DokkuError("An application name is needed.")


	def is_global(self):
		return self.app is None


	def app_global_arg(self):
		if self.is_global():
			return "--global"
		else:
			return self.app


class ConfigEntity(AppGlobalEntity):
	def __init__(self, app):
		AppGlobalEntity.__init__(self, app)
		self.config = None


	def load_config(self):
		self.config = {}
		for line in self.raw_exec_cmd(['config', self.app_global_arg()])[1:]:
			(name, value) = line.split(None, 1)
			self.config[name[:-1]] = value
		return self.config


	def get_config(self):
		if self.config is None:
			self.load_config()
		return self.config


	def ensure_absent(self, parsed_params):
		config = self.get_config()

		to_unset = set()
		for key in parsed_params:
			if key in config:
				to_unset.append(key)

		if to_unset:
			args = ['config:unset', '--no-restart', self.app_global_arg()]
			args.extend(list(to_unset))
			self.raw_exec_cmd(args)
			return True
		else:
			return False


	def ensure_present(self, parsed_params):
		config = self.get_config()

		set_params = []
		for key in parsed_params:
			if key not in config or config[key] != parsed_params[key]:
				set_params.append("%s=%s" % (key, parsed_params[key]))

		if set_params:
			args = ['config:set', '--no-restart', self.app_global_arg()]
			args.extend(set_params)
			self.raw_exec_cmd(args)
			return True
		else:
			return False


	def with_params(self, params):
		self.parsed_params = parse_params(params['config'])
		return self


	def ensure_state(self, state):
		if state == 'present':
			return self.ensure_present(self.parsed_params)
		elif state == 'absent':
			return self.ensure_absent(self.parsed_params)


class PsEntity(AppGlobalEntity):
	def __init__(self, app):
		AppGlobalEntity.__init__(self, app)


	def ensure_rebuild(self):
		if self.is_global():
			self.raw_exec_cmd(['ps:rebuildall'])
		else:
			self.raw_exec_cmd(['ps:rebuild', self.app])
		return True


	def ensure_restart(self):
		if self.is_global():
			self.raw_exec_cmd(['ps:restartall'])
		else:
			output = self.raw_exec_cmd(['ps:restart', self.app])
			if 'has not been deployed' in output[0]:
				return False
		return True


	def ensure_start(self):
		output = self.raw_exec_cmd(['ps:start', self.app])
		if 'already running' in output[0]:
			return False
		return True


	def ensure_stop(self):
		output = self.raw_exec_cmd(['ps:stop', self.app])
		if 'Stopping' in output[0]:
			return True
		return False


	def ensure_scale(self, params):
		scale_params = []
		for key in params:
			scale_params.append("%s=%s" % (key, params[key]))

		args = ['ps:scale', self.app]
		args.extend(scale_params)
		self.raw_exec_cmd(args)
		return True


	def with_params(self, params):
		self.params = params
		return self


	def ensure_state(self, state):
		if state == 'rebuilt':
			return self.ensure_rebuild()
		elif state == 'restarted':
			return self.ensure_restart()
		elif state == 'started':
			self.require_app()
			return self.ensure_start()
		elif state == 'stopped':
			self.require_app()
			return self.ensure_stop()
		elif state == 'scaled':
			self.require_app()
			return self.ensure_scale(parse_params(self.params['scale']))


class SshKeysEntity(Entity):
	def __init__(self):
		Entity.__init__(self, 'ssh-keys')
		self.keys = None

	def list_raw(self):
		try:
			return self.raw_exec_cmd([self.command_base() + 'list'])
		except DokkuError as ex:
			return []

	def list(self):
		return { split[1].split('=', 1)[1].strip('"'): split[0]
				 for split in [item.split() for item in self.list_raw()] }

	def create_cmd(self, name):
		return [self.command_base() + 'add', name, '-']

	def create(self, name):
		return self.exec_cmd(self.create_cmd(name), stdin=self.params['public_key'])

	def destroy_cmd(self, name):
		return [self.command_base() + 'remove', name]
