from __future__ import annotations
import json
import requests
from requests.auth import HTTPBasicAuth
from ansible.plugins.inventory import BaseInventoryPlugin
from ansible.errors import AnsibleParserError

DOCUMENTATION = r'''
plugin: patchmon.dynamic_inventory
short_description: Dynamic inventory plugin that queries PatchMon HTTP API and exposes hosts as an Ansible inventory
description:
    - Reads hosts/groups/vars from a JSON HTTP API and exposes them as an Ansible inventory.
options:
    plugin:
        description: Name of the plugin, this should be set to 'patchmon.dynamic_inventory' in the inventory file.
        required: true
        choices: ['patchmon.dynamic_inventory']
    api_url:
        description: URL of the API endpoint that returns JSON host data.
        required: true
    api_key:
        description: API key.
        required: true
    api_secret:
        description: API secret.
        required: true
    verify_ssl:
        description: Whether to verify SSL certificates when contacting the API.
        type: bool
        default: true
author:
    - stevelibonati@yahoo.com
'''

EXAMPLES = r'''
# Example inventory file (patchmon.yml) to enable this plugin:
# ---
# plugin: patchmon.dynamic_inventory
# api_url: http://localhost:3000/api/v1/hosts/info
# api_key: my_api_key
# api_secret: my_api_secret
# verify_ssl: false
'''

class InventoryModule(BaseInventoryPlugin):
        NAME = 'patchmon.dynamic_inventory'

        def verify_file(self, path):
                if super(InventoryModule, self).verify_file(path):
                        return path.endswith('yaml') or path.endswith('yml')
                return False
                
        def parse(self, inventory, loader, path, cache=True):
                super(InventoryModule, self).parse(inventory, loader, path)
                config = loader.load_from_file(path) or {}

                api_url = config.get('api_url')
                api_key = config.get('api_key')
                api_secret = config.get('api_secret')
                verify_ssl = config.get('verify_ssl', True)

                if not api_url:
                        raise AnsibleParserError("patchmon.dynamic_inventory: 'api_url' is required in the inventory config")
                if not api_key:
                        raise AnsibleParserError("patchmon.dynamic_inventory: 'api_key' is required in the inventory config")
                if not api_secret:
                        raise AnsibleParserError("patchmon.dynamic_inventory: 'api_secret' is required in the inventory config")
                if requests is None:
                        raise AnsibleParserError("patchmon.dynamic_inventory: 'requests' library is required but not installed")
              
                headers = {}
                headers.setdefault('Accept', 'application/json')
                auth_object = HTTPBasicAuth(api_key, api_secret)

                try:
                        resp = requests.get(api_url, headers=headers, timeout=10, verify=verify_ssl, auth=auth_object)
                        resp.raise_for_status()
                except Exception as e:
                        raise AnsibleParserError("patchmon.dynamic_inventory: failed to fetch API '{}': {}".format(api_url, e))

                try:
                        payload = resp.json()
                except ValueError:
                        raise AnsibleParserError("patchmon.dynamic_inventory: API did not return valid JSON")
                
                for entry in payload.get('hosts', []):
                        
                        name = entry.get('hostname')
                        
                        if not name:
                                continue  # Skip entries without hostname
                        
                        self.inventory.add_host(name)

                        addr = entry.get('ip')
                        if addr:
                                self.inventory.set_variable(name, 'ansible_host', addr)

                        # assign to groups
                        groups = entry.get('host_groups', [])
                        
                        for grp in groups:
                                if not grp:
                                        continue
                                self.inventory.add_group(grp.get('name'))
                                self.inventory.add_host(name, group=grp.get('name'))