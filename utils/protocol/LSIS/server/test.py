from utils.protocol.LSIS.server import StartTcpServer
from utils.datastore.context import RegistersSlaveContext, RegistersServerContext

# --------------------------------------------------------------------------- #
# configure the service logging
# --------------------------------------------------------------------------- #
import logging

FORMAT = (
    "%(asctime)-15s %(threadName)-15s"
    " %(levelname)-8s %(module)-15s:%(lineno)-8s %(message)s"
)
logging.basicConfig(format=FORMAT)
log = logging.getLogger()
log.setLevel(logging.DEBUG)


def run_server():
    store = RegistersSlaveContext(createMemory="LS_XGT_TCP")
    context = RegistersServerContext(slaves=store, single=True)
    StartTcpServer(context=context, address=("192.168.0.63", 2004))


if __name__ == "__main__":
    run_server()
