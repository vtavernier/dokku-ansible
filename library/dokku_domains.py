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
        "app": {"type": "str"},
        "domain": {"required": True, "type": "str"},
        "state": {
            "default": "present",
            "choices": ['present', 'absent'],
            "type": 'str'
        }
    }

    # return state
    meta = {"changed": False}

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
        meta['changed'] = DomainsEntity().with_params(p).ensure_state(p['state'], p['domain'])
    except DokkuError as err:
        if err.message != "not deployed\n":
          module.fail_json(msg=err.message, **meta)
        else:
          meta['msg'] = "not deployed, domain change not taken into account"

    # return result
    module.exit_json(**meta)


if __name__ == '__main__':
    main()
