#   Copyright (c) 2013-2015, Intel Performance Learning Solutions Ltd, Intel Corporation.
#   Copyright 2015 Zuercher Hochschule fuer Angewandte Wissenschaften
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""
Sample SO.
"""

import json
import os
import time
import threading

from bonfire.graylog_api import GraylogAPI, SearchQuery, SearchRange
import puka
from sdk.mcn import util
from sm.so import service_orchestrator
from sm.so.service_orchestrator import LOG
from sm.so.service_orchestrator import BUNDLE_DIR


class SOE(service_orchestrator.Execution):
    """
    Sample SO execution part.
    """
    def __init__(self, token, tenant, ready_event, destroy_event):
        super(SOE, self).__init__(token, tenant)
        self.token = token
        self.tenant = tenant
        self.event = ready_event
        self.destroy_event = destroy_event
        f = open(os.path.join(BUNDLE_DIR, 'data', 'rcb_cs.json'))
        self.template = f.read()
        f.close()
        self.stack_id = None
        self.deployer = util.get_deployer(self.token,
                                          url_type='public',
                                          tenant_name=self.tenant,
                                          region='ZurichCloudSigma')

    def design(self):
        """
        Do initial design steps here.
        """
        LOG.debug('Executing design logic')
        # self.resolver.design()

    def deploy(self):
        """
        deploy SICs.
        """
        LOG.debug('Executing deployment logic')
        if self.stack_id is None:
            self.stack_id = self.deployer.deploy(self.template, self.token, parameters={'UserName': 'pata@zhaw.ch',
                                                                                        'Password': 'welcome2@icclab'})
            LOG.info('Resource dependencies - stack id: ' + self.stack_id)

    def provision(self):
        """
        (Optional) if not done during deployment - provision.
        """
        LOG.debug('Executing resource provisioning logic')
        # once logic executes, deploy phase is done
        self.event.set()

    def state(self):
        """
        Report on state.
        """

        # TODO ideally here you compose what attributes should be returned to the SM
        # In this case only the state attributes are returned.
        # resolver_state = self.resolver.state()
        # LOG.info('Resolver state:')
        # LOG.info(resolver_state.__repr__())

        if self.stack_id is not None:
            tmp = self.deployer.details(self.stack_id, self.token)
            if 'output' not in tmp:
                return tmp['state'], self.stack_id, dict()
            return tmp['state'], self.stack_id, tmp['output']
        else:
            return 'Unknown', 'N/A', {}

    def update(self, old, new, extras):
        # TODO implement your own update logic - this could be a heat template update call - not to be confused
        # with provisioning
        pass

    def notify(self, entity, attributes, extras):
        super(SOE, self).notify(entity, attributes, extras)
        # TODO here you can add logic to handle a notification event sent by the CC
        # XXX this is optional

    def dispose(self):
        """
        Dispose SICs.
        """
        LOG.info('Disposing of 3rd party service instances...')
        # self.resolver.dispose()

        if self.stack_id is not None:
            LOG.info('Disposing of resource instances...')
            self.deployer.dispose(self.stack_id, self.token)
            self.stack_id = None
        # TODO on disposal, the SOE should notify the SOD to shutdown its thread
        self.destroy_event.set()


class SOD(service_orchestrator.Decision, threading.Thread):
    """
    Sample Decision part of SO.
    """

    def __init__(self, so_e, token, tenant, ready_event, destroy_event):
        super(SOD, self).__init__(so_e, token, tenant)
        threading.Thread.__init__(self)
        self.so_e = so_e
        self.token = token
        self.tenant = tenant
        self.event = ready_event
        self.destroy_event = destroy_event
        # we take events from a day ago. this will not result in duplicated
        # XXX optimisation possible here
        self.sr = SearchRange(from_time="1 day ago midnight", to_time='now')
        # TODO these params can be externalised
        self.logserver_url = 'log.cloudcomplab.ch'
        self.logserver_port = 12900
        self.logserver_user = 'admin'
        self.logserver_pass = 'admin'
        self.run_me = True
        self.sleepy = 30

    def run(self):
        """
        This logic does not need to run with the RCB SO and can be ran elsewhere
        Decision part implementation goes here.
        require the logging service
          hardcode to log.cloudcomplab.ch
        here we poll the logging server for events
        query for all services that are provision events since the start of this SO
        query for all services that are destroy events since the start of this SO
        construct messages to send to AMQP service
        start bill event:
        {
          "service_type": "dnsaas",
          "instance_id": "sodnsa97979879879",
          "tenant_id": "mcntub"
          "status": "start"
        }

        stop bill event:
        {
          "service_type": "dnsaas",
          "instance_id": "sodnsa97979879879",
          "tenant_id": "mcntub"
          "status": "start"
        }
        """

        LOG.debug('Waiting for deploy and provisioning to finish')
        self.event.wait()
        LOG.debug('Starting runtime logic...')

        _, _, stack_output = self.so_e.state()
        attributes = {}
        for kv in stack_output:
                attributes[kv['output_key']] = kv['output_value']

        amqp_url = ''  # "amqp://code:pass1234@messaging.demonstrator.info"
        if 'mcn.endpoint.rcb.mq' in attributes:
            # TODO return the username and password in the heat response
            # XXX username and password is hardcoded!
            amqp_url = 'amqp://guest:guest@' + attributes['mcn.endpoint.rcb.mq']
        else:
            LOG.error('mcn.endpoint.rcb.mq is not present in the stack output. amqp_url=' + amqp_url)
            raise RuntimeError('mcn.endpoint.rcb.mq is not present in the stack output. amqp_url=' + amqp_url)

        client, log_server = self.setup_connections(amqp_url)

        while not self.destroy_event.is_set():
            # TODO separate threads
            LOG.debug('Executing billing run...')
            self.bill_start_events(client, log_server)
            self.bill_stop_events(client, log_server)
            self.destroy_event.wait(self.sleepy)

        LOG.debug('Runtime logic ending...')
        client.close()

    def setup_connections(self, amqp_url):
        LOG.debug('Setting up graylog API...')
        attempts = 20
        log_server = GraylogAPI(self.logserver_url, self.logserver_port, self.logserver_user, self.logserver_pass)
        client = puka.Client(amqp_url)

        try:
            LOG.debug('AMQP connection to: ' + amqp_url)
            promise = client.connect()
            client.wait(promise)
        except:
            LOG.error('Cannot connect to the RCB message bus.')
            client.close()
            while attempts > 0:
                LOG.debug('Sleeping for 10 secs')
                time.sleep(10)
                LOG.debug('AMQP connection to: ' + amqp_url)
                promise = client.connect()
                client.wait(promise)
                attempts = attempts - 1
            else:
                client.close()
                LOG.error('Giving up attempting to connect to the AMQP bus after number of attempts: ' + str(attempts))
                raise RuntimeError('Giving up attempting to connect to the AMQP bus after number of attempts: ' + str(attempts))

        self.setup_amqp(amqp_url, client)

        return client, log_server

    def setup_amqp(self, amqp_url, client):

        LOG.debug('AMQP exchange declaration: mcn')
        promise = client.exchange_declare(exchange='mcn', type='topic', durable=True)
        client.wait(promise)
        LOG.debug('AMQP queue declaration: mcnevents')
        promise = client.queue_declare('mcnevents', durable=True)
        client.wait(promise)
        LOG.debug('AMQP queue/exchange binding: mcnevents->mcn Routing key: events')
        promise = client.queue_bind(queue='mcnevents', exchange='mcn', routing_key='events')
        client.wait(promise)
        return True

    def bill_stop_events(self, client, log_server):
        stop_billing_query = SearchQuery(search_range=self.sr, query='phase_event:done AND so_phase:destroy')
        try:
            stop_results = log_server.search(stop_billing_query)
            LOG.debug('Number of stop billing events found: ' + str(len(stop_results.messages)))

            for stop_event in stop_results.messages:
                rcb_message = {}
                stop_message = json.loads(stop_event.message)

                rcb_message['service_type'] = stop_message.get('sm_name', 'none')
                rcb_message['instance_id'] = stop_message.get('so_id', 'none')
                rcb_message['tenant_id'] = stop_message.get('tenant', 'mcntub')
                rcb_message['status'] = 'stop'

                LOG.info('Sending stop billing event to RCB: ' + rcb_message.__repr__())
                promise = client.basic_publish(exchange='mcn', routing_key='events', body=json.dumps(rcb_message))
                client.wait(promise)
        except Exception as e:
            LOG.error('Cannot issue query to the log service to extract stop events.')
            raise e

    def bill_start_events(self, client, log_server):
        start_billing_query = SearchQuery(search_range=self.sr, query='phase_event:done AND so_phase:provision')
        try:
            start_results = log_server.search(start_billing_query)
            LOG.debug('Number of start billing events found: ' + str(len(start_results.messages)))
            for start_event in start_results.messages:
                rcb_message = {}
                start_message = json.loads(start_event.message)

                rcb_message['service_type'] = start_message.get('sm_name', 'none')
                rcb_message['instance_id'] = start_message.get('so_id', 'none')
                rcb_message['tenant_id'] = start_message.get('tenant', 'mcntub')
                rcb_message['status'] = 'start'

                LOG.debug('Sending start billing event to RCB: ' + rcb_message.__repr__())
                promise = client.basic_publish(exchange='mcn', routing_key='events', body=json.dumps(rcb_message))
                client.wait(promise)
        except Exception as e:
            LOG.error('Cannot issue query to the log service to extract start events.')
            raise e

    def stop(self):
        pass


class ServiceOrchestrator(object):
    """
    Sample SO.
    """

    def __init__(self, token, tenant):
        # when provisioning is complete then only the run functionality can execute
        self.provision_event = threading.Event()
        # when soe.destroy is called this signals to stop the billing cycle
        self.destroy_event = threading.Event()
        self.so_e = SOE(token=token, tenant=tenant,
                        ready_event=self.provision_event, destroy_event=self.destroy_event)
        self.so_d = SOD(so_e=self.so_e, tenant=tenant, token=token,
                        ready_event=self.provision_event, destroy_event=self.destroy_event)
        LOG.debug('Starting SOD thread...')
        self.so_d.start()
