# Testing SO without deploying it using CC

Goto the directory of mcn_cc_sdk & setup virtenv (Note: could be done easier):

    $ virtualenv /tmp/mcn_test_virt
    $ source /tmp/mcn_test_virt/bin/activate

Install SDK and required packages:

    $ pip install pbr six iso8601 babel requests python-heatclient python-keystoneclient
    $ python setup.py install  # in the mcn_cc_sdk directory.

Run SO:

    $ export OPENSHIFT_PYTHON_DIR=/tmp/mcn_test_virt
    $ export OPENSHIFT_REPO_DIR=<path to sample so>
    $ python ./wsgi/application

In a new terminal do get a token from keystone (token must belong to a user which has the admin role for the tenant):

    $ keystone token-get
    $ export KID='...'
    $ export TENANT='...'

You can now visit the SO interface [here](http://localhost:8051/orchestrator/default):

    $ curl -v -X GET http://localhost:8051/orchestrator/default \
          -H 'X-Auth-token: '$KID \
          -H 'X-Tenant-Name: '$TENANT
    $ curl -v -X POST "http://localhost:8051/orchestrator/default?action=init" \
          -H 'Content-Type: text/occi' \
          -H 'Category: init; scheme="http://schemas.mobile-cloud-networking.eu/occi/service#"' \
          -H 'X-Auth-Token: '$KID \
          -H 'X-Tenant-Name: '$TENANT
    $ curl -v -X POST "http://localhost:8051/orchestrator/default?action=deploy" \
          -H 'Content-Type: text/occi' \
          -H 'Category: deploy; scheme="http://schemas.mobile-cloud-networking.eu/occi/service#"' \
          -H 'X-Auth-Token: '$KID \
          -H 'X-Tenant-Name: '$TENANT
    $ curl -v -X POST "http://localhost:8051/orchestrator/default?action=provision" \
          -H 'Content-Type: text/occi' \
          -H 'Category: provision; scheme="http://schemas.mobile-cloud-networking.eu/occi/service#"' \
          -H 'X-Auth-Token: '$KID \
          -H 'X-Tenant-Name: '$TENANT
