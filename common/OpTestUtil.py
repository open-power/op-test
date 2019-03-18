#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/OpTestUtil.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015
# [+] International Business Machines Corp.
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.
#
# IBM_PROLOG_END_TAG

import sys
import os
import datetime
import time
import pwd
import string
import subprocess
import random
import re
import telnetlib
import socket
import select
import time
import pty
import pexpect
import commands
import requests
import traceback
from requests.adapters import HTTPAdapter
#from requests.packages.urllib3.util import Retry
from httplib import HTTPConnection
#HTTPConnection.debuglevel = 1 # this will print some additional info to stdout
import urllib3 # setUpChildLogger enables integrated logging with op-test
import json

from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError
from Exceptions import CommandFailed, RecoverFailed, ConsoleSettings
from Exceptions import HostLocker, AES, ParameterCheck, HTTPCheck, UnexpectedCase

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

sudo_responses = ["not in the sudoers",
                  "incorrect password"]

class OpTestUtil():

    def __init__(self, conf=None):
        self.conf = conf

    def setup(self, config='HostLocker'):
        # we need this called AFTER the proper configuration values have been seeded
        if config == 'AES':
          self.conf.util_server = Server(url=self.conf.args.aes_server,
                                         base_url=self.conf.args.aes_base_url,
                                         minutes=None,
                                         proxy=self.build_proxy(self.conf.args.aes_proxy,
                                             self.conf.args.aes_no_proxy_ips))
        elif config == 'REST':
          rest_server = "https://{}".format(self.conf.args.bmc_ip)
          self.conf.util_bmc_server = Server(url=rest_server,
                                         username=self.conf.args.bmc_username,
                                         password=self.conf.args.bmc_password)
        else:
          self.conf.util_server = Server(url=self.conf.args.hostlocker_server,
                                         base_url=self.conf.args.hostlocker_base_url,
                                         minutes=None,
                                         proxy=self.build_proxy(self.conf.args.hostlocker_proxy,
                                             self.conf.args.hostlocker_no_proxy_ips))

    def check_lockers(self):
      if self.conf.args.hostlocker is not None:
        self.conf.util.hostlocker_lock(self.conf.args)

      if self.conf.args.aes is not None:
        query = False
        lock = False
        unlock = False
        for i in range(len(self.conf.args.aes)):
          if self.conf.args.aes[i].lower() == 'q':
            query = True
            del self.conf.args.aes[i] # remove the q flag in case env name is also q
            break
          if self.conf.args.aes[i].lower() == 'l':
            lock = True
            del self.conf.args.aes[i] # remove the l flag in case env name is also l
            break
          if self.conf.args.aes[i].lower() == 'u':
            unlock = True
            del self.conf.args.aes[i] # remove the u flag in case env name is also u
            break

        self.conf.args.aes = list(set(self.conf.args.aes)) # removes any duplicates

        if query:
          envs, search_criteria = self.conf.util.aes_get_environments(self.conf.args)
          if envs is not None:
            self.conf.util.aes_print_environments(envs)
          else:
            print("NO environments found, (if Environment_Name added its "
                   "probably a syntax problem with --aes q, look at "
                   "--aes-search-args), we used --aes-search-args {}\n"
                   .format(' '.join(search_criteria)))
          self.conf.util.cleanup()
          exit(0)
        if lock:
          envs, search_criteria = self.conf.util.aes_get_environments(self.conf.args)
          if envs is not None and len(envs) > 0:
            if len(envs) <= 1:
              for env in envs:
                # working_id should NOT be kept to release upon exit
                working_id = self.conf.util.aes_lock_env(env=env)
                if working_id is None:
                  print ("AES shows NOT available to LOCK, "
                         "Environment_EnvId={} Environment_Name='{}' "
                         "Environment_State={} res_id={} res_email={}"
                         .format(env['env_id'], env['name'], env['state'],
                         env['res_id'], env['res_email']))
                else:
                  print ("AES LOCKED Environment_EnvId={} "
                         "Environment_Name='{}' res_id={} aes-add-locktime "
                         "(in hours, zero is Never Expires) = '{}'"
                         .format(env['env_id'], env['name'], working_id,
                         self.conf.args.aes_add_locktime))
            else:
              print ("AES LOCK limit imposed, we found {} environments "
                     "using --aes-search-args {} and we must find only "
                     "one to lock here, use --aes q with your "
                     "--aes-search-args to view what we found"
                     .format(len(envs), ' '.join(search_criteria)))
          else:
            print ("Found NO environments using --aes-search-args {}, "
                   "use --aes q with your --aes-search-args to view "
                   "what we found".format(' '.join(search_criteria)))
          self.conf.util.cleanup()
          exit(0) # exit lock branch
        if unlock:
          envs, search_criteria = self.conf.util.aes_get_environments(self.conf.args)
          if envs is not None:
            if len(envs) <= 1:
              for env in envs:
                res_id = self.conf.util.aes_release_reservation(env=env)
                if res_id is None:
                  print ("AES shows NO LOCK, so skipped UNLOCK "
                         "Environment_EnvId={} Environment_Name='{}' "
                         "Environment_State={} res_id={} res_email={}"
                         .format(env['env_id'], env['name'], env['state'],
                         env['res_id'], env['res_email']))
                else:
                  print ("AES UNLOCKed Environment_EnvId={} "
                         "Environment_Name='{}' res_id={} res_email={}"
                         .format(env['env_id'], env['name'],
                         env['res_id'], env['res_email']))
            else:
              print ("AES UNLOCK limit imposed, we found {} "
                     "environments and we must only find one to unlock "
                     "here, use --aes-search-args to limit "
                     "serach criteria".format(len(envs)))
          else:
            print ("NO AES environments found using --aes-search-args {}"
                   .format(' '.join(search_criteria)))
          self.conf.util.cleanup()
          exit(0) # exit unlock branch
        else: # we filtered out all else so now find an env and lock it
          self.conf.lock_dict = self.conf.util.aes_lock(self.conf.args,
                                  self.conf.lock_dict)
          environments = self.conf.lock_dict.get('envs')
          if self.conf.lock_dict.get('res_id') is None:
            if self.conf.aes_print_helpers is True:
              self.conf.util.aes_print_environments(environments)
            # MESSAGE 'unable to lock' must be kept in same line to be filtered
            raise AES(message="OpTestSystem AES unable to lock environment "
              "requested, try --aes q with options for --aes-search-args "
              "to view availability")
          else:
            log.info("OpTestSystem AES Reservation for Environment_Name '{}' "
              "Group_Name={} Reservation id={}"
              .format(self.conf.lock_dict.get('name'),
              self.conf.lock_dict.get('Group_Name'),
              self.conf.lock_dict.get('res_id')))
      elif self.conf.args.aes_search_args is not None:
        self.conf.lock_dict = self.conf.util.aes_lock(self.conf.args,
                                self.conf.lock_dict)
        environments = self.conf.lock_dict.get('envs')
        if self.conf.lock_dict.get('res_id') is None:
          if self.conf.aes_print_helpers is True:
            self.conf.util.aes_print_environments(environments)
          # MESSAGE 'unable to lock' must be kept in same line to be filtered
          raise AES(message="OpTestSystem AES NO available environments matching "
                        "criteria (see output earlier), unable to lock,"
                        "try running op-test with --aes q "
                        "--aes-search-args Environment_State=A "
                        "to query system availability, if trying to use "
                        "existing reservation the query must be exactly one")
        else:
          log.info("OpTestSystem AES Reservation for Environment_Name '{}' "
            "Group_Name={} Reservation id={}"
            .format(self.conf.lock_dict.get('name'),
            self.conf.lock_dict.get('Group_Name'),
            self.conf.lock_dict.get('res_id')))

    def cleanup(self):
        if self.conf.args.hostlocker is not None:
          if self.conf.args.hostlocker_keep_lock is False:
            try:
              self.hostlocker_unlock()
            except Exception as e:
              log.warning("OpTestSystem HostLocker attempted to release "
                "host '{}' hostlocker-user '{}', please manually "
                "verify and release".format(self.conf.args.hostlocker,
                self.conf.args.hostlocker_user))
            rc, lockers = self.hostlocker_locked()
            if rc == 0:
              # there can be cases during signal handler cleanup
              # where we get interrupted before the actual lock hit
              # so this message can be output even though no lock was
              # actually released, no two phase commits here :0
              # other cases exist where we confirm no locks held, but
              # the info message may say released, due to exceptions thrown
              insert_message = ", host is locked by '{}'".format(lockers)
              if len(lockers) == 0:
                insert_message = ""
              log.info("OpTestSystem HostLocker cleanup for host '{}' "
                "hostlocker-user '{}' confirms you do not hold the lock{}"
                .format(self.conf.args.hostlocker,
                self.conf.args.hostlocker_user, insert_message))
            else: # we only care if user held the lock
              log.warning("OpTestSystem HostLocker attempted to cleanup "
                "and release the host '{}' and we were unable to verify, "
                "please manually verify and release"
                .format(self.conf.args.hostlocker))
        # clear since signal handler may call and exit path
        self.conf.args.hostlocker = None

        if self.conf.args.aes is not None or self.conf.args.aes_search_args is not None:
          if self.conf.args.aes_keep_lock is False:
            if self.conf.lock_dict.get('res_id') is not None:
              temp_res_id = self.aes_release_reservation(res_id=self.conf.lock_dict.get('res_id'))
              if temp_res_id is not None:
                log.info("OpTestSystem AES releasing reservation {} "
                  "Environment_Name '{}' Group_Name {}"
                  .format(self.conf.lock_dict.get('res_id'),
                  self.conf.lock_dict.get('name'),
                  self.conf.lock_dict.get('Group_Name')))
                # clear signal handler may call and exit path
                self.conf.lock_dict['res_id'] = None
              else:
                log.info("OpTestSystem AES attempted to cleanup and release "
                  "reservation {} Environment_Name '{}' Group_Name {}"
                  " and we were unable to verify, please manually verify "
                  "and release".format(self.conf.lock_dict.get('res_id'),
                  self.conf.lock_dict.get('name'),
                  self.conf.lock_dict.get('Group_Name')))

        if self.conf.util_server is not None:
          # AES and Hostlocker skip logout
          log.debug("Closing util_server")
          self.conf.util_server.close()

        if self.conf.util_bmc_server is not None:
          log.debug("Logging out of util_bmc_server")
          self.conf.util_bmc_server.logout()
          log.debug("Closing util_bmc_server")
          self.conf.util_bmc_server.close()

        if self.conf.dump:
          self.conf.dump = False # possible for multiple passes here
          self.dump_versions()

    def dump_versions(self):
        log.info("Log Location: {}/*debug*".format(self.conf.output))
        log.info("\n----------------------------------------------------------\n"
                 "OpTestSystem Firmware Versions Tested\n"
                 "(if flashed things like skiboot.lid, may not be accurate)\n"
                 "----------------------------------------------------------\n"
                 "{}\n"
                 "----------------------------------------------------------\n"
                 "----------------------------------------------------------\n"
            .format(
            (None if self.conf.firmware_versions is None \
            else ('\n'.join(f for f in self.conf.firmware_versions)))
            ))

    def build_proxy(self, proxy, no_proxy_ips):
        if no_proxy_ips is None:
          return proxy

        for ip in no_proxy_ips:
          cmd = 'ip addr show to %s' % ip
          try:
            output = subprocess.check_output(cmd.split())
          except (subprocess.CalledProcessError, OSError) as e:
            raise HostLocker(message="Could not run 'ip' to check for no proxy?")

          if len(output):
            proxy = None
            break

        return proxy

    def get_env_name(self, x):
      return x['name']

    def aes_print_environments(self, environments):
      if environments is None:
        return
      sorted_env_list = sorted(environments, key=self.get_env_name)
      print "--------------------------------------------------------------------------------"
      for env in sorted_env_list:
        print ("--aes-search-args Environment_Name='{}' Environment_EnvId={} "
          "Group_Name='{}' Group_GroupId={} Environment_State={} <res_id={} "
          "res_email={} aes-add-locktime={}>"
          .format(env['name'], env['env_id'], env['group']['name'],
          env['group']['group_id'], env['state'], env['res_id'],
          env['res_email'], env['res_length'], ))
      print "--------------------------------------------------------------------------------"
      print ("\nHELPERS   --aes-search-args Server_VersionName=witherspoon|boston|habanero|zz|tuleta"
             "|palmetto|brazos|fleetwood|p8dtu|p9dsu|zaius|stratton|firestone|garrison|romulus|alpine")
      print "          --aes-search-args Server_HardwarePlatform=POWER8|POWER9|openpower"
      print "          --aes-search-args Group_Name=op-test"
      print "          --aes-search-args Environment_State=A|R|M|X|H|E"
      print "A=Available R=Reserved M=Maintenance X=Offline H=HealthCheck E=Exclusive"
      print "AES Environments found = {}".format(len(sorted_env_list))


    def aes_release_reservation(self, res_id=None, env=None):
        release_dict = {'result'  : None,
                        'status'  : None,
                        'message' : None,
                       }
        if res_id is None:
          if env is not None:
            res_id = env.get('res_id')
        if res_id is None:
          return None # nothing to do
        res_payload = { 'res_id': res_id }
        uri = "/release-reservation.php"
        try:
          r = self.conf.util_server.get(uri=uri, params=res_payload)
          if r.status_code != requests.codes.ok:
            raise AES(message="OpTestSystem AES attempted to release "
              "reservation '{}' but it was NOT found in AES, "
              "please update and retry".format(res_id))
        except Exception as e:
          raise AES(message="OpTestSystem AES attempted to releasing "
            "reservation '{}' but encountered an Exception='{}', "
            "please manually verify and release".format(res_id, e))

        try:
            json_data = r.json()
            release_dict['status'] = json_data.get('status')
	    release_dict['result'] = json_data.get('result')
            if json_data.get('result').get('res_id') != res_id:
                log.warning("OpTestSystem AES UNABLE to confirm the release "
                    "of the reservation '{}' in AES, please manually "
                    "verify and release if needed, see details: {}"
                    .format(res_id, release_dict))
        except Exception as e:
            # this seems to be the typical path from AES, not sure what's up
            log.debug("NO JSON object from aes_release_reservation, r.text={}".format(r.text))
            release_dict['message'] = r.text
            log.debug("OpTestSystem AES UNABLE to confirm the release "
                "of the reservation '{}' in AES, please manually "
                "verify and release if needed, see details: {}"
                .format(res_id, release_dict))

        return res_id

    def aes_get_environments(self, args):
        # this method initializes the Server request session
        get_dict = {'result'  : None,
                    'status'  : None,
                    'message' : None,
                   }
        args_dict = vars(args)
        if self.conf.util_server is None:
          self.setup(config='AES')
        if self.conf.args.aes_search_args is None:
          self.conf.args.aes_search_args = []
          if self.conf.args.aes is not None:
            for i in range(len(self.conf.args.aes)):
              # add the single env to the list of search
              self.conf.args.aes_search_args += ("Environment_Name={}"
                  .format(self.conf.args.aes[i]).splitlines())
          else:
            return None, None # we should NOT have gotten here
        else:
          if self.conf.args.aes is not None:
            for i in range(len(self.conf.args.aes)):
              self.conf.args.aes_search_args += ("Environment_Name={}"
                  .format(self.conf.args.aes[i]).splitlines())

        uri = "/get-environments.php"
        payload = { 'query_params[]': self.conf.args.aes_search_args}
        r = self.conf.util_server.get(uri=uri, params=payload)

        if r.status_code != requests.codes.ok:
          raise AES(message="OpTestSystem AES UNABLE to find the environment '{}' "
            "in AES, please update and retry".format(self.conf.args.aes))

        # SQL issues can cause various problems which come back as ok=200
        filter_list = ["have an error"]
        matching = [xs for xs in filter_list if xs in r.text]
        if len(matching):
          raise AES(message="OpTestSystem AES encountered an error,"
            " check the syntax of your query and retry, Exception={}"
            .format(r.text))

        # we need this here to set the aes_user for subsequent calls
        if self.conf.args.aes_user is None:
          self.conf.args.aes_user = pwd.getpwuid(os.getuid()).pw_name

        aes_response_json = r.json()

        get_dict['status'] = aes_response_json.get('status')
        if aes_response_json.get('status') == 0:
          get_dict['result'] = aes_response_json.get('result')
        else:
          get_dict['message'] = aes_response_json.get('message')
          raise AES(message="Something unexpected happened, "
            "see details: {}".format(get_dict))

        return get_dict.get('result'), self.conf.args.aes_search_args

    def aes_get_env(self, env):
        uri = "/get-environment-info.php"
        env_payload = { 'env_id': env['env_id'] }
        r = self.conf.util_server.get(uri=uri, params=env_payload)
        if r.status_code != requests.codes.ok:
          raise AES(message="OpTestSystem AES UNABLE to find the environment '{}' "
            "in AES, please update and retry".format(env['env_id']))

        aes_response_json = r.json()

        if aes_response_json.get('status') == 0:
          return aes_response_json['result'][0]

    def aes_add_time(self, env=None, locktime=24):
        # Sept 10, 2018 - seems to be some issue with add-res-time.php
        # even in Web UI the Add an Hour is not working
        # locktime number of hours to add
        # if aes_add_time called when AES reservation is
        # in expiration window this fails
        # not sure how that calculation is done yet
        time_dict = {'result'  : None,
                     'status'  : None,
                     'message' : None,
                    }
        if locktime == 0:
          # if default, add some time
          # allows user to specify command line override
          locktime = 24
        uri = "/add-res-time.php"
        res_payload = { 'res_id': env.get('res_id'),
                        'hours': float(locktime),
                      }
        r = self.conf.util_server.get(uri=uri, params=res_payload)
        if r.status_code != requests.codes.ok:
          raise AES(message="OpTestSystem AES UNABLE to find the reservation "
            "res_id '{}' in AES, please update and retry".format(env['res_id']))

        aes_response_json = r.json()

        time_dict['status'] = aes_response_json.get('status')
        if aes_response_json.get('status') == 0:
          time_dict['result'] = aes_response_json.get('result')
        else:
          time_dict['message'] = aes_response_json.get('message')
          raise AES(message="OpTestSystem AES UNABLE to add time to existing "
            "reservation, the reservation may be about to expire or "
            "conflict exists, see details: {}".format(time_dict))
        return time_dict

    def aes_get_creds(self, env, args):
        # version_mappings used for bmc_type
        #                        AES             op-test
        version_mappings = { 'witherspoon'   : 'OpenBMC',
                             'zaius'         : 'OpenBMC',
                             'boston'        : 'SMC',
                             'stratton'      : 'SMC',
                             'p9dsu'         : 'SMC',
                             'p8dtu'         : 'SMC',
                             'firestone'     : 'AMI',
                             'garrison'      : 'AMI',
                             'habanero'      : 'AMI',
                             'palmetto'      : 'AMI',
                             'romulus'       : 'AMI',
                             'alpine'        : 'FSP',
                             'brazos'        : 'FSP',
                             'fleetwood'     : 'FSP',
                             'tuleta'        : 'FSP',
                             'zz'            : 'FSP',
                             'unknown'       : 'unknown',
                             'qemu'          : 'qemu',
                           }

        # aes_mappings used for configuration parameters
        #                        AES             op-test
        aes_mappings = { 'os_password'       : 'host_password',
                         'os_username'       : 'host_user',
                         'os_host'           : 'host_ip',
                         'net_mask'          : 'host_submask',
                         'os_mac_address'    : 'host_mac',
                         'def_gateway'       : 'host_gateway',
                         'mac_address'       : 'bmc_mac',
                         'password'          : 'bmc_password',
                         'username'          : 'bmc_username',
                         'host_name'         : 'bmc_ip',
                         'ipmi_username'     : 'bmc_usernameipmi',
                         'ipmi_password'     : 'bmc_passwordipmi',
                         'version_name'      : 'bmc_type',
                         'hardware_platform' : 'platform',
                         'attached_disk'     : 'host_scratch_disk',
                        }

        args_dict = vars(args) # we store credentials to the args
        if len(env['servers']) != 1:
          # we may not yet have output a message about reservation
          # but we will get the release message
          self.cleanup()
          raise AES(message="AES credential problem, check AES definitions "
            "for server record, we either have no server record or more "
            "than one, check FSPs and BMCs")

        for key, value in aes_mappings.items():
          if env['servers'][0].get(key) is not None and env['servers'][0].get(key) != '':
            if key == 'version_name':
              args_dict[aes_mappings[key]] = version_mappings.get(env['servers'][0][key].lower())
            else:
              args_dict[aes_mappings[key]] = env['servers'][0][key]

    def aes_lock_env(self, env=None):
        if env is None:
          return
        new_res_id = None
        res_payload = { 'email'         : self.conf.args.aes_user,
                        'query_params[]': None,
                        'needs_claim'   : False,
                        'length'        : float(self.conf.args.aes_add_locktime),
                        'rel_on_expire' : self.conf.args.aes_rel_on_expire,
                      }
        if env.get('state') == 'A':
          uri = "/enqueue-reservation.php"
          res_payload['query_params[]'] = 'Environment_EnvId={}'.format(env.get('env_id'))
          r = self.conf.util_server.get(uri=uri, params=res_payload)
          if r.status_code != requests.codes.ok:
            raise AES(message="Problem with AES trying to enqueue a reservation "
              "for environment '{}', please retry".format(env.get('env_id')))

          # SQL issues can cause various problems which come back as ok=200
          filter_list = ["have an error"]
          matching = [xs for xs in filter_list if xs in r.text]
          if len(matching):
            raise AES(message="OpTestSystem AES encountered an error,"
              " check the syntax of your query and retry, Exception={}"
              .format(r.text))

          aes_response_json = r.json()

          if aes_response_json['status'] == 0:
            new_res_id = aes_response_json['result']
          return new_res_id # None if status not zero
        else:
          if env.get('state') == 'R' and \
            env.get('res_email') == self.conf.args.aes_user and \
            self.conf.args.aes_add_locktime != 0:
              time_dict = self.aes_add_time(env=env,
                locktime=self.conf.args.aes_add_locktime)
              return env.get('res_id')
          return new_res_id # return None, nothing works

    def aes_lock(self, args, lock_dict):
      environments, search_criteria = self.aes_get_environments(args)
      for env in environments:
        # store the new reservation id in the callers instance
        # since we need to cleanup if aes_get_creds fails
        lock_dict['res_id'] = self.aes_lock_env(env=env)
        if lock_dict['res_id'] is not None:
          # get the database join info for the env
          creds_env = self.aes_get_env(env)
          # we need lock_dict filled in here
          # in case exception thrown in aes_get_creds
          lock_dict['name'] = env.get('name')
          lock_dict['Group_Name'] = env.get('group').get('name')
          lock_dict['envs'] = environments
          self.aes_get_creds(creds_env, args)
          return lock_dict
        else: # it was not Available
          # if only one environment, was it us ?
          # if so extend the reservation
          if len(environments) == 1:
            if env.get('res_email') == self.conf.args.aes_user:
              if env.get('state') == 'R':
                if env.get('res_length') != 0:
                  lock_dict['res_id'] = env.get('res_id')
                  # aes_add_time can fail if reservation
                  # about to expire or conflicts
                  time_dict = self.aes_add_time(env=env,
                    locktime=self.conf.args.aes_add_locktime)
                creds_env = self.aes_get_env(env)
                # we need lock_dict filled in here
                # in case exception thrown in aes_get_creds
                lock_dict['res_id'] = env.get('res_id')
                lock_dict['name'] = env.get('name')
                lock_dict['Group_Name'] = env.get('group').get('name')
                lock_dict['envs'] = environments
                self.aes_get_creds(creds_env, args)
                return lock_dict
      lock_dict['res_id'] = None
      lock_dict['name'] = None
      lock_dict['Group_Name'] = None
      lock_dict['envs'] = environments
      # we did not find anything able to be reserved
      # return the list we looked thru
      return lock_dict

    def hostlocker_lock(self, args):
        args_dict = vars(args)

        # we need hostlocker_user first thing in case exceptions
        if self.conf.args.hostlocker_user is None:
            self.conf.args.hostlocker_user = pwd.getpwuid(os.getuid()).pw_name

        if self.conf.util_server is None:
            self.setup()

        uri = "/host/{}/".format(self.conf.args.hostlocker)
        try:
            r = self.conf.util_server.get(uri=uri)
        except Exception as e:
            log.debug("hostlocker_lock unable to query Exception={}".format(e))
            raise HostLocker(message="OpTestSystem HostLocker unable to query "
              "HostLocker, check that your VPN/SSH tunnel is properly"
              " configured and open, proxy configured as '{}' Exception={}"
              .format(self.conf.args.hostlocker_proxy, e))

        if r.status_code != requests.codes.ok:
            raise HostLocker(message="OpTestSystem did NOT find the host '{}' "
              "in HostLocker, please update and retry"
              .format(self.conf.args.hostlocker))

        host = r.json()[0]
        hostlocker_comment = []
        hostlocker_comment = host['comment'].splitlines()

        for key in args_dict.keys():
            for i in range(len(hostlocker_comment)):
                if key + ':'  in hostlocker_comment[i]:
                    args_dict[key] = re.sub(key + ':', "", hostlocker_comment[i]).strip()
                    break

        uri = "/lock/"
        payload = {'host'        : self.conf.args.hostlocker,
                   'user'        : self.conf.args.hostlocker_user,
                   'expiry_time' : self.conf.args.hostlocker_locktime}
        try:
            r = self.conf.util_server.post(uri=uri, data=payload)
        except Exception as e:
            raise HostLocker(message="OpTestSystem HostLocker unable to "
                    "acquire lock from HostLocker, see Exception={}".format(e))

        if r.status_code == requests.codes.locked: # 423
            rc, lockers = self.hostlocker_locked()
            # MESSAGE 'unable to lock' string must be kept in same line to be filtered
            raise HostLocker(message="OpTestSystem HostLocker unable to lock"
                " Host '{}' is locked by '{}', please unlock and retry"
                .format(self.conf.args.hostlocker, lockers))
        elif r.status_code == requests.codes.conflict: # 409
            raise HostLocker(message="OpTestSystem HostLocker Host '{}' is "
                "unusable, please pick another host and retry"
                .format(self.conf.args.hostlocker))
        elif r.status_code == requests.codes.bad_request: # 400
            raise HostLocker(message=r.text)
        elif r.status_code == requests.codes.not_found: # 404
            msg = ("OpTestSystem HostLocker unknown hostlocker_user '{}', "
                   "you need to have logged in to HostLocker via the web"
                   " at least once prior, please log in to HostLocker via the web"
                   " and then retry or check configuration."
                   .format(self.conf.args.hostlocker_user))
            raise HostLocker(message=msg)

        log.info("OpTestSystem HostLocker reserved host '{}' "
            "hostlocker-user '{}'".format(self.conf.args.hostlocker,
            self.conf.args.hostlocker_user))

    def hostlocker_locked(self):
        # if called during signal handler cleanup
        # we may not have user yet
        if self.conf.args.hostlocker_user is None:
            return 1, []
        if self.conf.util_server is None:
            self.setup()
        uri = "/host/{}/".format(self.conf.args.hostlocker)
        try:
            r = self.conf.util_server.get(uri=uri)
        except HTTPCheck as check:
            log.debug("HTTPCheck Exception={} check.message={}".format(check, check.message))
            raise HostLocker(message="OpTestSystem HostLocker unknown host '{}'"
                .format(self.conf.args.hostlocker))
        except Exception as e:
            log.debug("hostlocker_locked did NOT get any host details for '{}', "
              "please manually verify and release,  Exception={}"
              .format(self.conf.args.hostlocker, e))
            return 1, [] # if unable to confirm, flag it

        uri = "/lock/"
        payload = {"host" : self.conf.args.hostlocker}
        try:
            r = self.conf.util_server.get(uri=uri,
                params=payload)
            locks = r.json()
        except Exception as e:
            log.debug("hostlocker_locked did NOT get any lock details for "
              "host '{}', please manually verify and release, Exception={}"
              .format(self.conf.args.hostlocker, e))
            return 1, [] # if unable to confirm, flag it
        lockers = []
        log.debug("locks JSON: {}".format(locks))
        try:
            for l in locks:
                lockers.append(str(l.get('locker')))
                if l.get('locker') == self.conf.args.hostlocker_user:
                    # lockers list is incomplete but only if we don't
                    # find hostlocker_user do we care
                    return 1, lockers
            return 0, lockers
        except Exception as e:
            log.debug("LOCKERS lockers={} Exception={}".format(lockers, e))

    def hostlocker_unlock(self):
        if self.conf.util_server is None:
            self.setup()
        uri = "/lock/"
        payload = {"host" : self.conf.args.hostlocker,
                   "user" : self.conf.args.hostlocker_user}
        try:
            r = self.conf.util_server.get(uri=uri,
                params=payload)
        except HTTPCheck as check:
            log.debug("HTTPCheck Exception={} check.message={}".format(check, check.message))
            msg = ("OpTestSystem HostLocker unexpected case hostlocker-user '{}', "
                   "you would need to have logged in to HostLocker via the web"
                   " at least once prior, manually verify and release, see Exception={}"
                   .format(self.conf.args.hostlocker_user, check))
            raise HostLocker(message=msg)
        except Exception as e:
            log.info("OpTestSystem HostLocker hostlocker_unlock tried to "
                "unlock host '{}' hostlocker-user '{}' but encountered a problem, "
                "manually verify and release, see Exception={}"
                .format(self.conf.args.hostlocker,
                self.conf.args.hostlocker_user, e))
            return

        locks = r.json()
        if len(locks) == 0:
            # Host is not locked, so just return
            log.debug("hostlocker_unlock tried to delete a lock but it was "
              "NOT there, see details={}".format(locks))
            return

        if len(locks) > 1:
            # this may never happen, but it came up in debug
            # with hardcoded changes to check error paths
            log.warning("hostlocker_unlock tried to delete lock for "
                "host '{}' but we found multiple locks and we should "
                "have only received hostlocker-user '{}' we queried "
                "for, please manually verify and release"
                .format(self.conf.args.hostlocker,
                self.conf.args.hostlocker_user))
            return

        if locks[0].get('locker') != self.conf.args.hostlocker_user:
            log.debug("hostlocker_unlock found that the locker did not "
                "match the hostlocker_user '{}'".format(self.conf.args.hostlocker_user))
        uri = "/lock/{}".format(locks[0].get('id'))
        try:
            r = self.conf.util_server.delete(uri=uri)
        except HTTPCheck as check:
            log.debug("HTTPCheck hostlocker_unlock tried to delete a lock"
                      " but encountered an HTTP problem, "
                      "Exception={} check.message={}".format(check, check.message))
            raise HostLocker(message="hostlocker_unlock tried to delete a lock "
                "but it was NOT there")
        except Exception as e:
            log.debug("hostlocker_unlock tried to delete a lock but it was "
                    "NOT there, see Exception={}".format(e))

    ##
    # @brief Pings 2 packages to system under test
    #
    # @param i_ip @type string: ip address of system under test
    # @param i_try @type int: number of times the system is
    #        pinged before returning Failed
    #
    # @return   BMC_CONST.PING_SUCCESS when PASSED or
    #           raise OpTestError when FAILED
    #
    def PingFunc(self, i_ip, i_try=1, totalSleepTime=BMC_CONST.HOST_BRINGUP_TIME):
        if i_ip == None:
            raise ParameterCheck(message="PingFunc has i_ip set to 'None', "
                "check your configuration and setup")
        sleepTime = 0;
        while(i_try != 0):
            p1 = subprocess.Popen(["ping", "-c 2", str(i_ip)],
                                  stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE)
            stdout_value, stderr_value = p1.communicate()

            if(stdout_value.__contains__("2 received")):
                log.debug(i_ip + " is pinging")
                return BMC_CONST.PING_SUCCESS

            else:
                # need to print message otherwise no interactive feedback
                # and user left guessing something is not happening
                log.info("PingFunc is not pinging '{}', waited {} of {}, {} "
                         "more loop cycles remaining, you may start to check "
                         "your configuration for bmc_ip or host_ip"
                         .format(i_ip, sleepTime, totalSleepTime, i_try))
                log.debug("%s is not pinging (Waited %d of %d, %d more "
                          "loop cycles remaining)" % (i_ip, sleepTime,
                          totalSleepTime, i_try))
                time.sleep(1)
                sleepTime += 1
                if (sleepTime == totalSleepTime):
                    i_try -= 1
                    sleepTime = 0

        log.error("'{}' is not pinging and we tried many times, "
                  "check your configuration and setup.".format(i_ip))
        raise ParameterCheck(message="PingFunc fails to ping '{}', "
            "check your configuration and setup and manually "
            "verify and release any reservations".format(i_ip))

    def copyFilesToDest(self, hostfile, destid, destName, destPath, passwd):
        arglist = (
            "sshpass",
            "-p", passwd,
            "/usr/bin/scp",
            "-o","UserKnownHostsFile=/dev/null",
            "-o","StrictHostKeyChecking=no",
            hostfile,
            "{}@{}:{}".format(destid,destName,destPath))
        log.debug(' '.join(arglist))
        subprocess.check_call(arglist)

    def copyFilesFromDest(self, destid, destName, destPath, passwd, sourcepath):
        arglist = (
            "sshpass",
            "-p", passwd,
            "/usr/bin/scp",
            "-r",
            "-o","UserKnownHostsFile=/dev/null",
            "-o","StrictHostKeyChecking=no",
            "{}@{}:{}".format(destid,destName,destPath),
            sourcepath)
        log.debug(' '.join(arglist))
        subprocess.check_output(arglist)

    # It waits for a ping to fail, Ex: After a BMC/FSP reboot
    def ping_fail_check(self, i_ip):
        cmd = "ping -c 1 " + i_ip + " 1> /dev/null; echo $?"
        count = 0
        while count < 500:
            output = commands.getstatusoutput(cmd)
            if output[1] != '0':
                log.debug("IP %s Comes down" % i_ip)
                break
            count = count + 1
            time.sleep(2)
        else:
            log.debug("IP %s keeps on pinging up" % i_ip)
            return False
        return True

    def build_prompt(self, prompt=None):
        if prompt:
          built_prompt = prompt
        else:
          built_prompt = "\[console-expect\]#"

        return built_prompt

    def clear_state(self, track_obj):
        track_obj.PS1_set = 0
        track_obj.SUDO_set = 0
        track_obj.LOGIN_set = 0

    def clear_system_state(self, system_obj):
        # clears attributes of the system object
        # called when OpTestSystem transitions states
        # unique from when track_obj's need clearing
        if system_obj.cronus_capable():
            system_obj.conf.cronus.env_ready = False
            system_obj.conf.cronus.cronus_ready = False

    def try_recover(self, term_obj, counter=3):
        # callers beware that the connect can affect previous states and objects
        for i in range(counter):
          log.warning("OpTestSystem detected something, working on recovery")
          pty = term_obj.connect()
          log.debug("USING TR Expect Buffer ID={}".format(hex(id(pty))))
          pty.sendcontrol('c')
          time.sleep(1)
          try_rc = pty.expect([".*#", "Petitboot", "login: ", pexpect.TIMEOUT, pexpect.EOF], timeout=10)
          log.debug("try_rc={}".format(try_rc))
          log.debug("pty.before={}".format(pty.before))
          log.debug("pty.after={}".format(pty.after))
          if try_rc in [0,1,2]:
            log.warning("OpTestSystem recovered from temporary issue, continuing")
            return
          else:
            log.warning("OpTestSystem Unable to recover from temporary issue, calling close and continuing")
            term_obj.close()
        log.warning("OpTestSystem Unable to recover to known state, raised Exception RecoverFailed but continuing")
        raise RecoverFailed(before=pty.before, after=pty.after, msg='Unable to recover to known state, retry')

    def try_sendcontrol(self, term_obj, command, counter=3):
        pty = term_obj.get_console()
        log.debug("USING TSC Expect Buffer ID={}".format(hex(id(pty))))
        res = pty.before
        log.warning("OpTestSystem detected something, working on recovery")
        pty.sendcontrol('c')
        time.sleep(1)
        try_list = []
        rc = pty.expect([".*#", pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        if rc != 0:
          term_obj.close()
          self.try_recover(term_obj, counter)
          # if we get back here we still fail but have a working prompt to give back
          log.warning("OpTestSystem recovered from temporary issue, but the command output is unavailable,"
                  " raised Exception CommandFailed but continuing")
          raise CommandFailed(command, "run_command TIMEOUT in try_sendcontrol, we recovered the prompt,"
                  " but the command output is unavailable", -1)
        else:
          # may have lost prompt
          log.warning('OpTestSystem recovered from a temporary issue, continuing')
          try_list = res.splitlines() # give back what we do have for triage
          echo_rc = 1
        return try_list, echo_rc

    def get_versions(self, term_obj, pty, expect_prompt):
        check_list = ["No such file or directory",
                      "not found",
                     ]
        if term_obj.system.conf.firmware_versions is None:
            pty.sendline("date")
            rc = pty.expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
            pty.sendline("lsprop /sys/firmware/devicetree/base/ibm,firmware-versions")
            time.sleep(1)
            rc = pty.expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
            if rc == 0:
                term_obj.system.conf.firmware_versions = \
                    pty.before.replace("\r\r\n","\n").splitlines()
                matching = [xs for xs in check_list if any(xs in xa for xa in term_obj.system.conf.firmware_versions)]
                if len(matching):
                    term_obj.system.conf.firmware_versions = ["Firmware Versions Unavailable"]
            else:
                log.debug("OpTestSystem unable to dump firmware versions tested")

    def set_PS1(self, term_obj, pty, prompt):
        # prompt comes in as the string desired, needs to be pre-built
        # on success caller is returned 1, otherwise exception thrown
        # order of execution and commands are sensitive here to provide reliability
        if term_obj.setup_term_disable == 1:
          return -1
        expect_prompt = prompt + "$"
        pty.sendline("which bash && exec bash --norc --noprofile")
        time.sleep(0.2)
        pty.sendline('PS1=' + prompt)
        time.sleep(0.2)
        rc = pty.expect([prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        pty.sendline("which stty && stty cols 300;which stty && stty rows 30")
        time.sleep(0.2)
        rc = pty.expect([prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        # mambo echos twice so turn off
        if term_obj.system.disable_stty_echo():
            pty.sendline("which stty && stty -echo")
            time.sleep(0.2)
            rc = pty.expect([prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        pty.sendline("export LANG=C")
        rc = pty.expect([prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        time.sleep(0.2)
        pty.sendline() # needed to sync buffers later on
        time.sleep(0.2) # pause for first time setup, buffers you know, more sensitive in petitboot shell, pexpect or console buffer not sure
        rc = pty.expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        if rc == 0:
          log.debug("Shell prompt changed")
          self.get_versions(term_obj, pty, expect_prompt)
          return 1 # caller needs to save state
        else: # we don't seem to have anything so try to get something
          term_obj.close()
          try:
            # special case to allow calls back to connect which is where we probably came from
            self.orig_system_setup_term = term_obj.get_system_setup_term()
            self.orig_block_setup_term = term_obj.get_block_setup_term()
            term_obj.set_system_setup_term(1) # block so the new connect will not try to come back here
            term_obj.set_block_setup_term(1) # block so the new connect will not try to come back here
            self.try_recover(term_obj, counter=3) # if try_recover bails we leave things blocked, they'll get reset
            # if we get back here we have a new prompt and unknown console
            # in future if state can change or block flags can change this needs revisted
            pty = term_obj.connect() # need a new pty since we recovered
            term_obj.set_system_setup_term = self.orig_system_setup_term
            term_obj.set_block_setup_term = self.orig_block_setup_term
            pty.sendline("which bash && exec bash --norc --noprofile")
            time.sleep(0.2)
            pty.sendline('PS1=' + prompt)
            time.sleep(0.2)
            pty.sendline("which stty && stty cols 300;which stty && stty rows 30")
            time.sleep(0.2)
            pty.sendline("export LANG=C")
            time.sleep(0.2)
            pty.sendline() # needed to sync buffers later on
            time.sleep(0.2) # pause for first time setup, buffers you know, more sensitive in petitboot shell, pexpect or console buffer not sure
            rc = pty.expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
            if rc == 0:
              log.debug("Shell prompt changed")
              self.get_versions(term_obj, pty, expect_prompt)
              return 1 # caller needs to save state
            else:
              if term_obj.setup_term_quiet == 0:
                log.warning("OpTestSystem Change of shell prompt not completed after last final retry,"
                        " probably a connection issue, raised Exception ConsoleSettings but continuing")
                raise ConsoleSettings(before=pty.before, after=pty.after,
                        msg="Change of shell prompt not completed after last final retry, probably a connection issue, retry")
              else:
                term_obj.setup_term_disable = 1
                return -1
          except RecoverFailed as e:
            if term_obj.setup_term_quiet == 0:
              log.warning("OpTestSystem Change of shell prompt not completed after last retry,"
                      " probably a connection issue, raised Exception ConsoleSettings but continuing")
              raise ConsoleSettings(before=pty.before, after=pty.after,
                      msg="Change of shell prompt not completed after last retry, probably a connection issue, retry")
            else:
              term_obj.setup_term_disable = 1
              return -1

    def get_login(self, host, term_obj, pty, prompt):
        # prompt comes in as the string desired, needs to be pre-built
        if term_obj.setup_term_disable == 1:
          return -1, -1
        my_user = host.username()
        my_pwd = host.password()
        pty.sendline()
        rc = pty.expect(['login: ', pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        if rc == 0:
          pty.sendline(my_user)
          time.sleep(0.1)
          rc = pty.expect([r"[Pp]assword:", pexpect.TIMEOUT, pexpect.EOF], timeout=10)
          if rc == 0:
            pty.sendline(my_pwd)
            time.sleep(0.5)
            rc = pty.expect(['login: $', ".*#$", ".*# $", ".*\$", 'Petitboot', pexpect.TIMEOUT, pexpect.EOF], timeout=10)
            if rc not in [1,2,3]:
              if term_obj.setup_term_quiet == 0:
                log.warning("OpTestSystem Problem with the login and/or password prompt,"
                        " raised Exception ConsoleSettings but continuing")
                raise ConsoleSettings(before=pty.before, after=pty.after,
                        msg="Problem with the login and/or password prompt, probably a connection or credential issue, retry")
              else:
                term_obj.setup_term_disable = 1
                return -1, -1
          else:
            if term_obj.setup_term_quiet == 0:
              log.warning("OpTestSystem Problem with the login and/or password prompt, raised Exception ConsoleSettings but continuing")
              raise ConsoleSettings(before=pty.before, after=pty.after,
                      msg="Problem with the login and/or password prompt, probably a connection or credential issue, retry")
            else:
                term_obj.setup_term_disable = 1
                return -1, -1
          my_PS1_set = self.set_PS1(term_obj, pty, prompt)
          my_LOGIN_set = 1
        else: # timeout eof
          pty.sendline()
          rc = pty.expect(['login: ', pexpect.TIMEOUT, pexpect.EOF], timeout=10)
          if rc == 0:
            pty.sendline(my_user)
            time.sleep(0.1)
            rc = pty.expect([r"[Pp]assword:", pexpect.TIMEOUT, pexpect.EOF], timeout=10)
            if rc == 0:
              pty.sendline(my_pwd)
              time.sleep(0.5)
              rc = pty.expect(['login: $', ".*#$", ".*# $", ".*\$", 'Petitboot', pexpect.TIMEOUT, pexpect.EOF], timeout=10)
              if rc not in [1,2,3]:
                if term_obj.setup_term_quiet == 0:
                  log.warning("OpTestSystem Problem with the login and/or password prompt,"
                          " raised Exception ConsoleSettings but continuing")
                  raise ConsoleSettings(before=pty.before, after=pty.after,
                          msg="Problem with the login and/or password prompt, probably a connection or credential issue, retry")
                else:
                  term_obj.setup_term_disable = 1
                  return -1, -1
            else:
              if term_obj.setup_term_quiet == 0:
                log.warning("OpTestSystem Problem with the login and/or password prompt after a secondary connection issue,"
                        " raised Exception ConsoleSettings but continuing")
                raise ConsoleSettings(before=pty.before, after=pty.after,
                        msg="Problem with the login and/or password prompt after a secondary connection or credential issue, retry")
              else:
                term_obj.setup_term_disable = 1
                return -1, -1
            my_PS1_set = self.set_PS1(term_obj, pty, prompt)
            my_LOGIN_set = 1
          else: # timeout eof
            if term_obj.setup_term_quiet == 0:
              log.warning("OpTestSystem Problem with the login and/or password prompt after a previous connection issue,"
                    " raised Exception ConsoleSettings but continuing")
              raise ConsoleSettings(before=pty.before, after=pty.after,
                      msg="Problem with the login and/or password prompt last try, probably a connection or credential issue, retry")
            else:
              term_obj.setup_term_disable = 1
              return -1, -1
        return my_PS1_set, my_LOGIN_set # caller needs to save state

    def check_root(self, pty, prompt):
        # we do the best we can to verify, but if not oh well
        expect_prompt = prompt + "$"
        pty.sendline("date") # buffer kicker needed
        pty.sendline("which whoami && whoami")
        time.sleep(2)
        rc = pty.expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        log.debug("check_root rc={}".format(rc))
        log.debug("check_root before={}".format(pty.before))
        log.debug("check_root after={}".format(pty.after))
        if rc == 0:
          before = pty.before.replace("\r\r\n", "\n")
          try:
            whoami = before.splitlines()[-1]
            log.debug("check_root whoami={}".format(whoami))
          except Exception:
            pass
          pty.sendline("echo $?")
          time.sleep(1)
          rc = pty.expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
          log.debug("check_root 2 rc={}".format(rc))
          log.debug("check_root 2 before={}".format(pty.before))
          log.debug("check_root 2 after={}".format(pty.after))
          before = pty.before.replace("\r\r\n", "\n")
          if rc == 0:
            try:
              echo_rc = int(before.splitlines()[-1])
              log.debug("check_root echo_rc={}".format(echo_rc))
            except Exception as e:
              echo_rc = -1
            if echo_rc == 0:
              if whoami in "root":
                log.debug("OpTestSystem now running as root")
              else:
                log.warning("OpTestSystem should be running as root, unable to confirm root, whoami={}".format(whoami))
            else:
                log.debug("OpTestSystem should be running as root, unable to verify")

    def get_sudo(self, host, term_obj, pty, prompt):
        # prompt comes in as the string desired, needs to be pre-built
        # must have PS1 expect_prompt already set
        # must be already logged in
        if term_obj.setup_term_disable == 1:
          return -1, -1
        pty.sendline()

        try:
            # If we logged in as root or we're in the Petitboot shell we may
            # already be root.
            self.check_root(pty, prompt)
            return 1, 1
        except:
            pass

        my_pwd = host.password()
        pty.sendline("which sudo && sudo -s")
        rc = pty.expect([r"[Pp]assword for", pexpect.TIMEOUT, pexpect.EOF], timeout=5)
        # we must not add # prompt to the expect, we get false hit when complicated user login prompt and control chars,
        # we need to cleanly ignore everything but password and then we blindly next do PS1 setup, ignoring who knows what
        if rc == 0:
          pty.sendline(my_pwd)
          time.sleep(0.5) # delays for next call
          my_PS1_set = self.set_PS1(term_obj, pty, prompt)
          self.check_root(pty, prompt)
          my_SUDO_set = 1
          return my_PS1_set, my_SUDO_set # caller needs to save state
        elif rc == 1: # we must have been root, we first filter out password prompt above
          my_PS1_set = self.set_PS1(term_obj, pty, prompt)
          self.check_root(pty, prompt)
          my_SUDO_set = 1
          return my_PS1_set, my_SUDO_set # caller needs to save state
        else:
          if term_obj.setup_term_quiet == 0:
            log.warning("OpTestSystem Unable to setup root access, probably a connection issue,"
                    " raised Exception ConsoleSettings but continuing")
            raise ConsoleSettings(before=pty.before, after=pty.after,
                    msg='Unable to setup root access, probably a connection issue, retry')
          else:
            term_obj.setup_term_disable = 1
            return -1, -1

    def setup_term(self, system, pty, ssh_obj=None, block=0):
        # Login and/or setup any terminal
        # pty needs to be the opexpect object
        # This will behave correctly even if already logged in
        # Petitboot Menu is special case to NOT participate in this setup, conditionally checks if system state is PETITBOOT and skips
        # CANNOT CALL GET_CONSOLE OR CONNECT from here since get_console and connect call into setup_term
        if block == 1:
          return
        if ssh_obj is not None:
          track_obj = ssh_obj
          term_obj = ssh_obj
          system_obj = ssh_obj.system
        else:
          track_obj = system
          term_obj = system.console
          system_obj = system
        pty.sendline()
        rc = pty.expect(['login: $', ".*#$", ".*# $", ".*\$", 'Petitboot', pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        if rc == 0:
          track_obj.PS1_set, track_obj.LOGIN_set = self.get_login(system_obj.cv_HOST, term_obj, pty, self.build_prompt(system_obj.prompt))
          track_obj.PS1_set, track_obj.SUDO_set = self.get_sudo(system_obj.cv_HOST, term_obj, pty, self.build_prompt(system_obj.prompt))
          return
        if rc in [1,2,3]:
          track_obj.PS1_set = self.set_PS1(term_obj, pty, self.build_prompt(system_obj.prompt))
          track_obj.LOGIN_set = 1 # ssh port 22 can get in which uses sshpass or Petitboot, do this after set_PS1 to make sure we have something
          track_obj.PS1_set, track_obj.SUDO_set = self.get_sudo(system_obj.cv_HOST, term_obj, pty, self.build_prompt(system_obj.prompt))
          return
        if rc == 4:
          return # Petitboot so nothing to do
        if rc == 6: # EOF
          term_obj.close() # mark as bad
          raise ConsoleSettings(before=pty.before, after=pty.after,
                  msg="Getting login and sudo not successful, probably connection or credential issue, retry")
        # now just timeout
        pty.sendline()
        rc = pty.expect(['login: $', ".*#$", ".*# $", ".*\$", 'Petitboot', pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        if rc == 0:
          track_obj.PS1_set, track_obj.LOGIN_set = self.get_login(system_obj.cv_HOST, term_obj, pty, self.build_prompt(system_obj.prompt))
          track_obj.PS1_set, track_obj.SUDO_set = self.get_sudo(system_obj.cv_HOST, term_obj, pty, self.build_prompt(system_obj.prompt))
          return
        if rc in [1,2,3]:
          track_obj.LOGIN_set = track_obj.PS1_set = self.set_PS1(term_obj, pty, self.build_prompt(system_obj.prompt))
          track_obj.PS1_set, track_obj.SUDO_set = self.get_sudo(system_obj.cv_HOST, term_obj, pty, self.build_prompt(system_obj.prompt))
          return
        if rc == 4:
          return # Petitboot do nothing
        else:
          if term_obj.setup_term_quiet == 0:
            term_obj.close() # mark as bad
            raise ConsoleSettings(before=pty.before, after=pty.after,
                    msg="Getting login and sudo not successful, probably connection issue, retry")
          else:
            # this case happens when detect_target sets the quiet flag and we are timing out
            log.info("OpTestSystem detected something, checking if your system is powered off, will retry")

    def set_env(self, term_obj, pty):
        set_env_list = []
        pty.sendline("which bash && exec bash --norc --noprofile")
        expect_prompt = self.build_prompt(term_obj.prompt) + "$"
        pty.sendline('PS1=' + self.build_prompt(term_obj.prompt))
        rc = pty.expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        if rc == 0:
          combo_io = (pty.before + pty.after).replace("\r\r\n", "\n").lstrip()
          set_env_list += combo_io.splitlines()
          # remove the expect prompt since matched generic #
          del set_env_list[-1]
          return set_env_list
        else:
          raise ConsoleSettings(before=pty.before, after=pty.after,
                  msg="Setting environment for sudo command not successful, probably connection issue, retry")

    def retry_password(self, term_obj, pty, command):
        retry_list_output = []
        a = 0
        while a < 3:
          a += 1
          pty.sendline(term_obj.system.cv_HOST.password())
          rc = pty.expect([".*#", "try again.", pexpect.TIMEOUT, pexpect.EOF])
          if (rc == 0) or (rc == 1):
            combo_io = pty.before + pty.after
            retry_list_output += combo_io.replace("\r\r\n","\n").splitlines()
            matching = [xs for xs in sudo_responses if any(xs in xa for xa in pty.after.splitlines())]
            if len(matching):
              echo_rc = 1
              rc = -1 # use to flag the failure next
          if rc == 0:
            retry_list_output += self.set_env(term_obj, pty)
            echo_rc = 0
            break
          elif a == 2:
            echo_rc = 1
            break
          elif (rc == 2):
            raise CommandFailed(command, 'Retry Password TIMEOUT ' + ''.join(retry_list_output), -1)
          elif (rc == 3):
            term_obj.close()
            raise ConsoleSettings(before=pty.before, after=pty.after,
                    msg='SSH session/console issue, probably connection issue, retry')

        return retry_list_output, echo_rc

    def handle_password(self, term_obj, pty, command):
        # this is for run_command 'sudo -s' or the like
        handle_list_output = []
        failure_list_output = []
        pre_combo_io = pty.before + pty.after
        pty.sendline(term_obj.system.cv_HOST.password())
        rc = pty.expect([".*#$", "try again.", pexpect.TIMEOUT, pexpect.EOF])
        if (rc == 0) or (rc == 1):
          combo_io = pre_combo_io + pty.before + pty.after
          handle_list_output += combo_io.replace("\r\r\n","\n").splitlines()
          matching = [xs for xs in sudo_responses if any(xs in xa for xa in pty.after.splitlines())]
          if len(matching):
            # remove the expect prompt since matched generic #
            del handle_list_output[-1]
            echo_rc = 1
            rc = -1 # use this to flag the failure next
        if rc == 0:
          # with unknown prompts and unknown environment unable to capture echo $?
          echo_rc = 0
          self.set_env(term_obj, pty)
          list_output = handle_list_output
        elif rc == 1:
          retry_list_output, echo_rc = self.retry_password(term_obj, pty, command)
          list_output = (handle_list_output + retry_list_output)
        else:
          if (rc == 2) or (rc == 3):
            failure_list_output += ['Password Problem/TIMEOUT ']
            failure_list_output += pre_combo_io.replace("\r\r\n","\n").splitlines()
          # timeout path needs access to output
          # handle_list_output empty if timeout or EOF
          failure_list_output += handle_list_output
          if (rc == 3):
            term_obj.close()
            raise SSHSessionDisconnected("SSH session/console exited early!")
          else:
            raise CommandFailed(command, ''.join(failure_list_output), -1)
        return list_output, echo_rc

    def run_command(self, term_obj, command, timeout=60, retry=0):
        # retry=0 will perform one pass
        counter = 0
        while counter <= retry:
          try:
            output = self.try_command(term_obj, command, timeout)
            return output
          except CommandFailed as cf:
            log.debug("CommandFailed cf={}".format(cf))
            if counter == retry:
              raise cf
            else:
              counter += 1
              log.debug("run_command retry sleeping 2 seconds, before retry")
              time.sleep(2)
              log.debug("Retry command={}".format(command))
              log.info("\n \nOpTestSystem detected a command issue, we will retry the command,"
                    " this will be retry \"{:02}\" of a total of \"{:02}\"\n \n".format(counter, retry))

    def try_command(self, term_obj, command, timeout=60):
        running_sudo_s = False
        extra_sudo_output = False
        expect_prompt = self.build_prompt(term_obj.prompt) + "$"
        pty = term_obj.get_console() # if previous caller environment leaves buffer hung can show up here, e.g. PS2 prompt
        pty.sendline(command)
        if command == 'sudo -s':
          running_sudo_s = True
          # special case to catch loss of env
          rc = pty.expect([".*#", r"[Pp]assword for", pexpect.TIMEOUT, pexpect.EOF], timeout=timeout)
        else:
          rc = pty.expect([expect_prompt, r"[Pp]assword for", pexpect.TIMEOUT, pexpect.EOF], timeout=timeout)
        output_list = []
        output_list += pty.before.replace("\r\r\n","\n").splitlines()
        try:
          del output_list[:1] # remove command from the list
        except Exception as e:
          pass # nothing there
        # if we are running 'sudo -s' as root then catch on generic # prompt, restore env
        if running_sudo_s and (rc == 0):
          extra_sudo_output = True
          set_env_list = self.set_env(term_obj, pty)
        if rc == 0:
          if extra_sudo_output:
            output_list += set_env_list
          pty.sendline("echo $?")
          rc2 = pty.expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=timeout)
          if rc2 == 0:
            echo_output = []
            echo_output += pty.before.replace("\r\r\n","\n").splitlines()
            try:
                del echo_output[:1] # remove command from the list
            except Exception as e:
                pass # nothing there
            try:
                echo_rc = int(echo_output[-1])
            except Exception as e:
                echo_rc = -1
          else:
            raise CommandFailed(command, "run_command echo TIMEOUT, the command may have been ok,"
                    " but unable to get echo output to confirm result", -1)
        elif rc == 1:
          handle_output_list, echo_rc = self.handle_password(term_obj, pty, command)
          # remove the expect prompt since matched generic #
          del handle_output_list[-1]
          output_list = handle_output_list
        elif rc == 2: # timeout
            output_list, echo_rc = self.try_sendcontrol(term_obj, command) # original raw buffer if it holds any clues
        else:
          term_obj.close()
          raise CommandFailed(command, "run_command TIMEOUT or EOF, the command timed out or something,"
                  " probably a connection issue, retry", -1)
        res = output_list
        if echo_rc != 0:
          raise CommandFailed(command, res, echo_rc)
        return res

    # This command just runs and returns the output & ignores the failure
    # A straight copy of what's in OpTestIPMI
    def run_command_ignore_fail(self, term_obj, command, timeout=60, retry=0):
        try:
            output = self.run_command(term_obj, command, timeout, retry)
        except CommandFailed as cf:
            output = cf.output
        return output

    def mambo_run_command(self, term_obj, command, timeout=60, retry=0):
        expect_prompt = "systemsim %"
        term_obj.get_console().sendline(command)
        rc = term_obj.get_console().expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=timeout)
        output_list = []
        output_list += term_obj.get_console().before.replace("\r\r\n","\n").splitlines()
        try:
          del output_list[:1] # remove command from the list
        except Exception as e:
          pass # nothing there
        return output_list

    def mambo_enter(self, term_obj):
        term_obj.get_console().sendcontrol('c')
        rc = term_obj.get_console().expect(["systemsim %", pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        if rc != 0:
            raise UnexpectedCase(state="Mambo", message="We tried to send control-C"
                " to Mambo and we failed, probably just retry")

    def mambo_exit(self, term_obj):
        # this method will remove the mysim go from the output
        expect_prompt = self.build_prompt(term_obj.prompt) + "$"
        term_obj.get_console().sendline("mysim go")
        rc = term_obj.get_console().expect(["mysim go", pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        output_list = []
        output_list += term_obj.get_console().before.replace("\r\r\n","\n").splitlines()
        try:
          del output_list[:1] # remove command from the list
        except Exception as e:
          pass # nothing there
        return output_list

    def cronus_subcommand(self, command=None, minutes=2):
        # OpTestCronus class calls this, so be cautious on recursive calls
        assert 0 < minutes <= 120, (
            "cronus_subcommand minutes='{}' is out of the desired range of 1-120"
            .format(minutes))
        completed = False
        try:
            p1 = subprocess.Popen(["bash", "-c", command],
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
            # set the polling appropriate
            if minutes > 5:
                sleep_period = 60
                custom_range = minutes
            else:
                sleep_period = 1
                custom_range = minutes*60
            log.debug("cronus_subcommand sleep_period seconds='{}' number of periods to wait (custom_range)='{}'\n"
                      " Waiting for minutes='{}' which is seconds='{}')"
                      .format(sleep_period, custom_range, minutes, minutes*60))
            for t in range(custom_range):
                log.debug("polling t={}".format(t))
                time.sleep(sleep_period)
                if p1.poll() is not None:
                    log.debug("polling completed=True")
                    completed = True
                    break
            if not completed:
                log.warning("cronus_subcommand did NOT complete in '{}' minutes, rc={}".format(minutes, p1.returncode))
                p1.kill()
                log.warning("cronus_subcommand killed command='{}'".format(command))
                raise UnexpectedCase(message="Cronus issue rc={}".format(p1.returncode))
            else:
                log.debug("cronus_subcommand rc={}".format(p1.returncode))
                stdout_value, stderr_value = p1.communicate()
                log.debug("command='{}' p1.returncode={}"
                    .format(command, p1.returncode))
                if p1.returncode:
                    log.warning("RC={} cronus_subcommand='{}', debug log contains stdout/stderr"
                        .format(p1.returncode, command))
                log.debug("cronus_subcommand command='{}' stdout='{}' stderr='{}'"
                    .format(command, stdout_value, stderr_value))
                if stderr_value:
                    # some calls get stderr which is noise
                    log.debug("Unknown if this is a problem, Command '{}' stderr='{}'".format(command, stderr_value))
                return stdout_value
        except subprocess.CalledProcessError as e:
            tb = traceback.format_exc()
            log.debug("cronus_subcommand issue CalledProcessError={}, Traceback={}".format(e, tb))
            raise UnexpectedCase(message="Cronus issue rc={} output={}".format(e.returncode, e.output))
        except Exception as e:
            tb = traceback.format_exc()
            log.debug("cronus_subcommand issue Exception={}, Traceback={}".format(e, tb))
            raise UnexpectedCase(message="cronus_subcommand issue Exception={}, Traceback={}".format(e, tb))

    def cronus_run_command(self, command=None, minutes=2):
        # callers should assure its not too early in system life to call
        # we need a system object, OpTestConfiguration.py env_ready cronus_ready
        assert 0 < minutes <= 120, (
            "cronus_run_command minutes='{}' is out of the desired range of 1-120"
            .format(minutes))
        log.debug("env_ready={} cronus_ready={}"
            .format(self.conf.cronus.env_ready, self.conf.cronus.cronus_ready))
        if not self.conf.cronus.env_ready or not self.conf.cronus.cronus_ready:
            log.debug("Cronus not ready, calling setup")
            self.conf.cronus.setup()
            if not self.conf.cronus.env_ready or not self.conf.cronus.cronus_ready:
                log.warning("We tried to setup Cronus, either Cronus is not installed"
                    " on your op-test box or target system is NOT supported yet"
                    " (only OpenBMC so far), "
                    "or some other system problem, checking further")
                if self.conf.cronus.cv_SYSTEM is not None:
                    cronus_state = self.conf.cronus.cv_SYSTEM.get_state()
                    log.warning("cronus_state={} capable={}"
                        .format(cronus_state, self.conf.cronus.capable))
                    raise UnexpectedCase(state=cronus_state,
                        message="We tried to setup Cronus and something is "
                                "not working, check the debug log")
                else:
                    log.warning("We do not have a system object yet, it "
                        "may be too early to call cronus_run_command")
                    raise UnexpectedCase(message="We do not have a system "
                        "object yet, it may be too early to call cronus_run_command")

        if not command:
            log.warning("cronus_run_command requires a command to run")
            raise ParameterCheck(message="cronus_run_command requires a command to run")
        self.conf.cronus.dump_env()
        log.debug("cronus_run_command='{}' target='{}'"
            .format(command, self.conf.cronus.current_target))
        stdout_value = self.cronus_subcommand(command=command, minutes=minutes)
        return stdout_value

class Server(object):
    '''
    Generic Server Requests Session Object to abstract retry and error
    handling logic.  There are two common uses of the requests
    session object:
    1 - Single Request with no retry.  Create the Server instance with
    minutes set to None.  This will flag the calls to cycle once and
    return non-OK requests back to the caller for handling.
    Special case is the login needed, that case will be caught and
    login attempted and original request retried.
    2 - Request calls which need to be tolerant of communication
    glitches and possible server disconnections.  Caller must create
    the Server instance with minutes set to a value.  If the caller
    wants to modify the minutes it must be done on a call by call
    basis (create the Server instance with a default minutes value
    and if longer time needed make the change on the specific call).

    Login is done for the caller, so no need to call login, just
    make the GET/PUT/POST/DELETE call.
    '''
    def __init__(self, url=None,
                 base_url=None,
                 proxy=None,
                 username=None,
                 password=None,
                 verify=False,
                 minutes=3,
                 timeout=30):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        OpTestLogger.optest_logger_glob.setUpChildLogger("urllib3")
        self.username = username
        self.password = password
        self.session = requests.Session()
        if self.username is not None and self.password is not None:
            self.session.auth = (self.username, self.password)
        self.session.verify = verify
        self.jsonHeader = {'Content-Type' : 'application/json'}
        self.xAuthHeader = {}
        self.timeout = timeout
        self.minutes = minutes
        self.session.mount('https://', HTTPAdapter(max_retries=5))
        # value.max_retries for future debug if needed
#        for key, value in self.session.adapters.items():
#            log.debug("max_retries={}".format(value.max_retries))

        if proxy:
            self.session.proxies = {"http" : proxy}
        else:
            self.session.proxies = {}

        self.base_url = url + (base_url if base_url else "")

    def _url(self, suffix):
        return ''.join([self.base_url, suffix])

    def login(self, username=None, password=None):
        if username is None:
            username = self.username
        if password is None:
            password = self.password
        uri = "/login"
        payload = {"data": [username, password]}
        # make direct call to requests post, by-pass loop_it
        try:
            r = self.session.post(self._url(uri),
                                  headers=self.jsonHeader,
                                  json=payload)
            if r.status_code != requests.codes.ok:
                log.debug("Requests post problem with logging "
                    "in, r.status_code={} r.text={} r.headers={} "
                    "r.request.headers={}"
                    .format(r.status_code, r.text,
                     r.headers, r.request.headers))
                raise HTTPCheck(message="Requests post problem logging in,"
                    " check that your credentials are properly setup,"
                    " r.status_code={} r.text={} r.headers={} "
                    " r.request.headers={} username={} password={}"
                    .format(r.status_code, r.text, r.headers,
                     r.request.headers, username, password))
            cookie = r.headers['Set-Cookie']
            match = re.search('SESSION=(\w+);', cookie)
            if match:
                self.xAuthHeader['X-Auth-Token'] = match.group(1)
                self.jsonHeader.update(self.xAuthHeader)
            json_data = json.loads(r.text)
            log.debug("r.status_code={} json_data['status']={}"
                " r.text={} r.headers={} r.request.headers={}"
                .format(r.status_code, json_data['status'],
                 r.text, r.headers, r.request.headers))
            if (json_data['status'] != "ok"):
                log.debug("Requests COOKIE post problem logging in,"
                    " check that your credentials are properly setup,"
                    " r.status_code={} r.text={} r.headers={} "
                    " r.request.headers={} username={} password={}"
                    .format(r.status_code, r.text, r.headers,
                     r.request.headers, username, password))
                raise HTTPCheck(message="Requests COOKIE post problem logging in,"
                    " check that your credentials are properly setup,"
                    " r.status_code={} r.text={} r.headers={} "
                    " r.request.headers={} username={} password={}"
                    .format(r.status_code, r.text, r.headers,
                     r.request.headers, username, password))
        except Exception as e:
            log.debug("Requests post problem, check that your "
                "credentials are properly setup URL={} username={} "
                "password={}, Exception={}"
                .format(self._url(uri), username, password, e))
            raise HTTPCheck(message="Requests post problem, check that your "
                "credentials are properly setup URL={} username={} "
                "password={}, Exception={}"
                .format(self._url(uri), username, password, e))
        return r

    def logout(self, uri=None):
        uri = "/logout"
        payload = {"data" : []}
        try:
            # make direct call to requests post, by-pass loop_it
            r = self.session.post(self._url(uri), json=payload)
            if r.status_code != requests.codes.ok:
                log.debug("Requests post problem with logging "
                    "out, r.status_code={} r.text={} r.headers={} "
                    "r.request.headers={}"
                    .format(r.status_code, r.text,
                     r.headers, r.request.headers))
            return r
        except Exception as e:
            log.debug("Requests post problem logging out"
                       " URL={} Exception={}".format(self._url(uri), e))

    def get(self, **kwargs):
        kwargs['cmd'] = 'get'
        r = self.loop_it(**kwargs)
        return r

    def put(self, **kwargs):
        kwargs['cmd'] = 'put'
        r = self.loop_it(**kwargs)
        return r

    def post(self, **kwargs):
        kwargs['cmd'] = 'post'
        r = self.loop_it(**kwargs)
        return r

    def delete(self, **kwargs):
        kwargs['cmd'] = 'delete'
        r = self.loop_it(**kwargs)
        return r

    def loop_it(self, **kwargs):
        default_vals = {'cmd' : None, 'uri' : None, 'data' : None,
                        'json' : None, 'params' : None, 'minutes' : None,
                        'files' : None, 'stream' : False,
                        'verify' : False, 'headers' : None}
        for key in default_vals:
            if key not in kwargs.keys():
                kwargs[key] = default_vals[key]

        command_dict = { 'get'    : self.session.get,
                         'put'    : self.session.put,
                         'post'   : self.session.post,
                         'delete' : self.session.delete,
                       }
        if kwargs['minutes'] is not None:
            loop_time = time.time() + 60*kwargs['minutes']
        else:
            loop_time = time.time() + 60*5 # enough time to cycle
        while True:
            if time.time() > loop_time:
                raise HTTPCheck(message="HTTP \"{}\" problem, we timed out "
                   "trying URL={} PARAMS={} DATA={} JSON={} Files={}, we "
                   "waited {} minutes, check the debug log for more details"
                     .format(kwargs['cmd'], self._url(kwargs['uri']),
                     kwargs['params'], kwargs['data'], kwargs['json'],
                     kwargs['files'], kwargs['minutes']))
            try:
                r = command_dict[kwargs['cmd']](self._url(kwargs['uri']),
                        params=kwargs['params'],
                        data=kwargs['data'],
                        json=kwargs['json'],
                        files=kwargs['files'],
                        stream=kwargs['stream'],
                        verify=kwargs['verify'],
                        headers=kwargs['headers'],
                        timeout=self.timeout)
            except Exception as e:
                # caller did not want any retry so give them the exception
                log.debug("loop_it Exception={}".format(e))
                if kwargs['minutes'] is None:
                    raise e
                time.sleep(5)
                continue
            if r.status_code == requests.codes.unauthorized: # 401
                try:
                    log.debug("loop_it unauthorized, trying to login")
                    self.login()
                    continue
                except Exception as e:
                    log.debug("Unauthorized login failed, Exception={}".format(e))
                    if kwargs['minutes'] is None:
                        # caller did not want retry so give them the exception
                        raise e
                    time.sleep(5)
                    continue
            if r.status_code == requests.codes.ok:
                log.debug("OpTestSystem HTTP r={} r.status_code={} r.text={}"
                    .format(r, r.status_code, r.text))
                return r
            else:
                if kwargs['minutes'] is None:
                    # caller did not want any retry so give them what we have
                    log.debug("OpTestSystem HTTP (no retry) r={} r.status_code={} r.text={}"
                        .format(r, r.status_code, r.text))
                    return r
            time.sleep(5)

    def close(self):
        self.session.close()
