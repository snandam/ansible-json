#!/usr/bin/python
# Copyright header....

DOCUMENTATION = '''
---
module: ansible-json
short_description: json-like transforms
'''

EXAMPLES = '''
- action: ansible-json file=... key=... value=...
'''

import re
from ansible.module_utils.basic import *

# helper function to split string into multiple properties (used to index)
def splitStringByProperties(propertyString):
    regex = "\.(?=([^\"\']*[\"\'][^\"\']*[\"\'])*[^\"\']*$)"
    properties = []
    if propertyString:
        match = re.search(regex, propertyString)
        while match:
            properties.append(propertyString[:match.start()].strip('\'\"'))
            propertyString = propertyString[match.end():]
            match = re.search(regex, propertyString)
        # Our regex leaves a little bit left
        properties.append(propertyString)
    return properties

def isAnyArrayOperation(prop):
    return False if re.search("\[.*\]", prop) == None else True

def isGenericArrayOperation(prop):
    return False if re.search("\[\]", prop) == None else True

def extractKeyFromArrayString(prop):
    match = re.search("\[.*\]", prop)
    return prop[:match.start()]

def extractDereferenceKeyFromArrayString(prop):
    match = re.search("\[.*\]", prop)
    return prop[match.start():match.end()].strip('\[\]')

# Returns a list (possibly just one element) of the property query (properties)
def propertyStringToValueEnumerator(dictionary, properties):
    # Base Case, no more properties so dictionary is the object desired
    if not properties:
        return [ dictionary ]

    # Recursive step
    currentProperty = properties[:1][0]
    if isAnyArrayOperation(currentProperty):
        key = extractKeyFromArrayString(currentProperty)
        # if there are multiple derefernce things
        if isGenericArrayOperation(currentProperty):
            accumulate = []
            for array_value in dictionary[key]:
                for array_result in propertyStringToValueEnumerator(array_value, properties[1:]):
                    accumulate.append(array_result)
            return accumulate
        # if there is a specific dereference thing
        deref_key = extractDereferenceKeyFromArrayString(currentProperty)
        return propertyStringToValueEnumerator(dictionary[key][int(deref_key)], properties[1:])
    else:
        return propertyStringToValueEnumerator(dictionary[currentProperty], properties[1:])

# create, update
# function takes two arguements, the parent of the keyString and the key
def operation(function, dictionary, keyString, params=None):
    properties = splitStringByProperties(keyString)
    key = properties[-1:][0]
    properties = properties[:-1]
    for parent in propertyStringToValueEnumerator(dictionary, properties):
        yield function(parent, key, params)

def set_helper(parent, key, value):
    parent[key] = value
    return parent

def set(dictionary, keyString, value):
    return operation(set_helper, dictionary, keyString, value)

def delete(dictionary, keyString):
    return operation(lambda parent, key, params: parent.pop(key), dictionary, keyString)

def get(dictionary, keyString):
    return operation(lambda parent, key, params: parent[key], dictionary, keyString)

def main():
    module = AnsibleModule(
        argument_spec = dict(
            file   = dict(required=True),
            key    = dict(required=False, defualt=None),
            value  = dict(required=False, default=None),
            delete = dict(required=False, default=None, choices=BOOLEANS)
        )
    )

    filename = module.params['file']
    json_key_string = module.params['key']
    json_value = module.params['value']
    should_delete = module.params['delete']

    # Store the files contents
    with open(filename, 'r') as data_file:
        file_contents = json.load(data_file)

    # User gave us a Read command
    if not json_value and not should_delete:
        query = None
        if json_key_string:
            query=get(file_contents, json_key_string)
        module.exit_json(changed=False, file=file_contents, query=query)

    # User gave us a Create/Update/Delete command
    if not json_key_string:
        module.fail_json(changed=False, msg="Failed to provide json key yet value was given.")

    with open(filename, "w") as data_file:
        data_file.truncate() # if result is shorter, will have leftover from previous file version
        # Delete
        if should_delete:
            delete(file_contents, json_key_string)
        # Create or Update
        else:
            set(file_contents, json_key_string, json_value)
        json.dump(file_contents, data_file)

    module.exit_json(changed=True, file=file_contents)

if __name__ == '__main__':
    main()