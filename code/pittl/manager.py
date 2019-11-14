from datetime import datetime, timedelta
import pickle
import socket
from threading import Thread

from pittl import logger
from pittl.driver import DriverException
from pittl.shared import PORT, Response, Request


# Constants
HOST = '0.0.0.0'


# Service
class Service(Thread):

    def __init__(self, driver_svc):
        super().__init__()
        self.name = 'manager'

        # CLI
        self.client = None

        # Driver mirror
        self.driver_svc = driver_svc

    def respond(self, msg, data=None):
        event = (msg, data)

        b = pickle.dumps(event)
        try:
            self.client.send(b)
            logger.debug('Responded {}'.format(event))
        except socket.error:
            pass

    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((HOST, PORT))
            s.listen(0)
            addr = s.getsockname()
            logger.info('Awaiting connection on {}:{}'.format(*addr))

            self.await_client(s)

    def await_client(self, s):
        while True:
            client, addr = s.accept()
            self.client = client

            logger.info('Accepted connection from {}:{}'.format(*addr))
            self.handle_client(client, addr)
            logger.info('{}:{} disconnected'.format(*addr))

    def handle_client(self, client, addr):
        with client:
            while True:
                # Get a msg please
                try:
                    data = client.recv(1024)
                except ConnectionResetError:
                    return
                if not data:
                    return
                try:
                    event = pickle.loads(data)
                    logger.debug('Received {}'.format(event))

                    rsp = self.dispatch(*event)
                    self.respond(*rsp)

                except pickle.UnpicklingError:
                    logger.error('Deserialization error')
                    self.respond(Response.FAILURE,
                                 'Deserialization error')

    def dispatch(self, msg, data):
        if msg == Request.STAGE_TIMING:
            try:
                self.driver_svc.stage_timing(data)
                return (Response.SUCCESS, None)
            except DriverException as e:
                return (Response.FAILURE, e)
        elif msg == Request.STAGE_SEQUENCE_RANDOM:
            try:
                self.driver_svc.stage_seq_rand()
                return (Response.SUCCESS, None)
            except DriverException as e:
                return (Response.FAILURE, e)
        elif msg == Request.STAGE_SEQUENCE_REGULAR:
            try:
                self.driver_svc.stage_seq_reg()
                return (Response.SUCCESS, None)
            except DriverException as e:
                return (Response.FAILURE, e)
        elif msg == Request.START_SEQUENCE:
            try:
                self.driver_svc.start_seq()
                return (Response.SUCCESS, None)
            except DriverException as e:
                return (Response.FAILURE, e)
        elif msg == Request.STOP_SEQUENCE:
            try:
                self.driver_svc.stop_seq()
                return (Response.SUCCESS, None)
            except DriverException as e:
                return (Response.FAILURE, e)
        elif msg == Request.QUERY_TIMING:
            if self.driver_svc.staged_timing is None:
                s = {}
            else:
                s = self.driver_svc.staged_timing.to_dict()
            if self.driver_svc.committed_timing is None:
                t = {}
            else:
                t = self.driver_svc.committed_timing.to_dict()

            t = {'timing': {'staged': s, 'committed': c}}
            return (Response.SUCCESS, t)
        elif msg == Request.QUERY_SEQUENCE:
            # TODO: Not active right now
            s = {'sequence': {'staged': self.driver_svc.staged_seq,
                              'committed': self.driver_svc.committed_seq}}
            return (Response.SUCCESS, s)
        elif msg == Request.QUERY_EXPERIMENT:
            progress = self.driver_svc.chain_progress()
            if progress is not None:
                progress = round(progress * 1000) / 1000
                experiment['progress'] = progress

            eta = self.driver_svc.eta()
            if eta is not None:
                eta = str(timedelta(seconds=eta))
                experiment['eta'] = eta

            started = self.driver_svc.started
            if started is not None:
                started = str(datetime.fromtimestamp(started))
                experiment['started'] = started

            d = {'experiment': experiment}
            return (Response.SUCCESS, d)
        else:
            return (Response.FAILURE, 'Unknown request')
