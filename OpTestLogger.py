
# This implements all the python logger setup for op-test

import os
import sys
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler

class OpTestLogger():
    '''
    This class is used as the main global logger and handler initialization module.

    See common/HelloWorld.py as an example for the usage within an op-test module.
    '''
    def __init__(self):
        '''
        Provide defaults and setup the minimal StreamHandlers
        '''
        self.parent_logger = 'op-test'
        self.maxBytes_logger_file = 2000000
        self.maxBytes_logger_debug_file = 2000000
        self.backupCount_logger_files = 5
        self.backupCount_debug_files = 5
        self.logdir = os.getcwd()
        self.logger_file = 'main.log'
        self.logger_debug_file = 'debug.log'
        self.optest_logger = logging.getLogger(self.parent_logger)
        # clear the logger of any handlers in this shell
        self.optest_logger.handlers = []
        # need to set the logger to deepest level, handlers will filter
        self.optest_logger.setLevel(logging.DEBUG)
        # we need to init stream handler as special case to keep all happy
        self.sh = logging.StreamHandler()
        # save the sh level for later refreshes
        self.sh_level = logging.ERROR
        self.sh.setLevel(self.sh_level)
        self.sh.setFormatter(logging.Formatter('\n%(asctime)s:%(name)s:%(levelname)s:%(message)s'))
        self.optest_logger.addHandler(self.sh)
        self.fh = None
        self.dh = None

    def __del__(self):
        '''
        Cleanup handlers and close files.
        '''
        handlers = self.optest_logger.handlers[:]
        for handler in handlers:
          handler.close()
          self.optest_logger.removeHandler(handler)

    def refreshLoggers(self, purgeOld=True):
        '''
        Provide a method that allows individual modules the capability to set the parent logger
        to a customized implementation and log file locations.

        :param purgeOld: Boolean to indicate to cleanup old loggers.
        '''
        # we always need to keep the stream as special case to keep all happy
        # Example usage (such as to place in HelloWorld.py)
        # OpTestLogger.optest_logger_glob.parent_logger = 'mynew-parent'
        # OpTestLogger.optest_logger_glob.logdir = '/home/myuser/op-test-framework/hello'
        # OpTestLogger.optest_logger_glob.logger_file = 'my_main.log'
        # OpTestLogger.optest_logger_glob.logger_debug_file = 'my_debug.log'
        # OpTestLogger.optest_logger_glob.refreshLoggers()

        self.optest_logger.info('Preparing to refresh location of loggers to {}'.format(self.logdir))
        if purgeOld:
          handlers = self.optest_logger.handlers[:]
          for handler in handlers:
            handler.close()
            self.optest_logger.removeHandler(handler)
          self.optest_logger.handlers = []
          self.fh = None
          self.dh = None
          # get a new optest_logger to start clean
          self.optest_logger = logging.getLogger(self.parent_logger)
          # need to set the logger to deepest level, handlers will filter
          self.optest_logger.setLevel(logging.DEBUG)
          self.sh = logging.StreamHandler()
          self.sh.setLevel(self.sh_level)
          self.sh.setFormatter(logging.Formatter('\n%(asctime)s:%(name)s:%(levelname)s:%(message)s'))
          self.optest_logger.addHandler(self.sh)
        self.setUpLoggerFile(self.logger_file)
        self.setUpLoggerDebugFile(self.logger_debug_file)
        self.optest_logger.debug('refreshLoggers done')

    def setUpLoggerFile(self, logger_file):
        '''
        Provide a method that allows setting up of a file handler with customized file rotation and formatting.

        :param logger_file: File name to use for logging the main log records.
        '''
        # need to log that location of logging may be changed
        self.optest_logger.info('Preparing to set location of Log File to {}'.format(os.path.join(self.logdir, logger_file)))
        self.logger_file = logger_file
        if (not os.path.exists(self.logdir)):
          os.makedirs(self.logdir)
        self.fh = RotatingFileHandler(os.path.join(self.logdir, self.logger_file), maxBytes=self.maxBytes_logger_file, backupCount=self.backupCount_logger_files)
        self.fh.setLevel(logging.INFO)
        self.fh.setFormatter(logging.Formatter('\n%(asctime)s:%(name)s:%(levelname)s:%(message)s'))
        self.optest_logger.addHandler(self.fh)
        self.optest_logger.debug('FileHandler settings updated')
        self.optest_logger.info('Log file: {}'.format(os.path.join(self.logdir, self.logger_file)))

    def setUpLoggerDebugFile(self, logger_debug_file):
        '''
        Provide a method that allows setting up of a debug file handler with customized file rotation and formatting.

        :param logger_debug_file: File name to use for logging the debug log records.
        '''
        self.optest_logger.info('Preparing to set location of Debug Log File to {}'.format(os.path.join(self.logdir, logger_debug_file)))
        self.logger_debug_file = logger_debug_file
        if (not os.path.exists(self.logdir)):
          os.makedirs(self.logdir)
        self.dh = RotatingFileHandler(os.path.join(self.logdir, self.logger_debug_file), maxBytes=self.maxBytes_logger_debug_file, backupCount=self.backupCount_debug_files)
        self.dh.setLevel(logging.DEBUG)
        self.dh.setFormatter(logging.Formatter('\n%(asctime)s:%(name)s:%(levelname)s:%(message)s'))
        self.optest_logger.addHandler(self.dh)
        self.optest_logger.debug('DebugHandler settings updated')
        self.optest_logger.info('Debug Log file: {}'.format(os.path.join(self.logdir, self.logger_debug_file)))

global optest_logger_glob
optest_logger_glob = OpTestLogger()
