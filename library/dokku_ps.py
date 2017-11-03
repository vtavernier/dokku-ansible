#!/usr/bin/python

ANSIBLE_METADATA = {
	'metadata_version': '1.1',
	'status': ['preview'],
	'supported_by': 'community'
}

from ansible.module_utils.basic import *
from ansible.module_utils.dokku import *

def main():
	# param spec
	module_args = {
		"app": { "type": "str" },
		"scale": { "type": "list" },
		"state": {
			"default": "start",
			"choices": ['rebuilt', 'restarted', 'started', 'stopped', 'scaled'],
			"type": 'str'
		}
	}

	# return state
	meta = { "changed": False }

	# declare module
	module = AnsibleModule(
		argument_spec=module_args,
		supports_check_mode=True
	)

	# check mode
	if module.check_mode:
		return meta

	# update app state
	try:
		p = module.params
		meta['changed'] = PsEntity(p['app']).with_params(p).ensure_state(p['state'])
	except DokkuError as err:
		module.fail_json(msg=err.message, **meta)

	# return result
	module.exit_json(**meta)

if __name__ == '__main__':
	main()
