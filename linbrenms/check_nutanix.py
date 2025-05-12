#!/usr/bin/env python3

##############################################################################
# NUTANIX ALERT CHECK API ICINGA/NAGIOS                                      #
# PYTHON 3.X                                                                 #
# Testing on AOS , 5.8.x, 5.9.x, 5.10.x, 5.15.x                              #
# David Lira, dlira96@gmail.com                                              #
##############################################################################

import argparse
import getpass
import requests
import urllib3
import datetime
import os
import sys

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

VERSION = 'v1.4'
TIMEOUT = 30
print('NUTANIX ALARM CLUSTER HEALTH (NTACH)',VERSION)
print('Author: David Lira, dlirachile2@gmail.com)')
print('Tiemout:',TIMEOUT,'\n')

ip=''
username='librenms'
password=''
atype='CRITICAL'
status='n'

def alerts(ip, username, password, atype, status):
        state_ok = 0
        base_url = "https://"+ip+":9440"
        try:
                pe_cluster_info = requests.get(base_url + '/PrismGateway/services/rest/v2.0/cluster/', auth=(username, password), verify=False, timeout=TIMEOUT)
                if pe_cluster_info.status_code == requests.codes.ok:
                        out_json = pe_cluster_info.json()
                        raw_cluster =  out_json
                        cluster_name= raw_cluster['name']
                        #print(cluster_name)

                if status == 'y':
                        x = 'true'
                elif status == 'n':
                        x = 'false'
                else:
                        print('Insert a valid info on --status (y/n)')
                        x = 'false'
                if atype == 'CRITICAL':
                        r = requests.get(base_url + f'/PrismGateway/services/rest/v2.0/alerts/?resolved={x}&severity=CRITICAL&get_causes=true&detailed_info=true',
                         auth=(username, password),
                         verify=False,
                         timeout=TIMEOUT)

                elif atype == 'WARNING':
                        r = requests.get(base_url + f'/PrismGateway/services/rest/v2.0/alerts/?resolved={x}&severity=WARNING&get_causes=true&detailed_info=true',
                         auth=(username, password),
                         verify=False,
                         timeout=TIMEOUT)
                else:
                        print('No correct alarm selected , type "WARNING OR CRITICAL in --atype')
                if r.status_code == requests.codes.ok:
                        entities = r.json()['entities']
                        state_ok=0
                        for x in entities:
                                severity = x['severity']
                                acknowledged = x['acknowledged']
                                alert_type_uuid = x['alert_type_uuid']
                                created_time_stamp_in_usecs = x['created_time_stamp_in_usecs']
                                created_time_stamp_in_usecs_datetime = datetime.datetime.fromtimestamp(created_time_stamp_in_usecs / 1000000 )
                                last_occurrence_time_stamp_in_usecs = x['last_occurrence_time_stamp_in_usecs']
                                last_occurrence_time_stamp_in_usecs_datetime = datetime.datetime.fromtimestamp(last_occurrence_time_stamp_in_usecs / 1000000 )
                                impact_types = x['impact_types'][0]
                                classifications = x['classifications'][0]
                                acknowledged_by_username = x['acknowledged_by_username']
                                alert_title = x['alert_title']
                                message = x['message']
                                detailed_message = x['detailed_message']
                                name_ent = x['context_values']
                                nproblem=name_ent[0]
                                resolved = x['resolved']
                                for y in x['affected_entities']:
                                        entity_type = y['entity_type']
                                        entity_name = y['entity_name']
                                        uuid = y['uuid']
                                for y in x['possible_causes']:
                                        causes = y['cause']
                                        actions= y['actions']
                                if 'context_types' in x.keys():
                                        name_objetct = []
                                        objt = {}
                                        for a in range(len(x['context_types'])):
                                                objt.update({x['context_types'][a]:x['context_values'][a]})
                                                name_objetct.append(a)
                                if objt:
                                        for key in objt.keys():
                                                val = '{'+key+'}'
                                                if alert_title.find(val) > -1:
                                                        alert_title = alert_title.replace(val,str(objt[key]))
                                ###PRINT INFO
                                if severity == 'kWarning':
                                        print('-Severity:','\033[93m' + severity + '\x1b[0m')
                                elif severity == 'kCritial':
                                        print('-Severity:','\033[91m' + severity + '\x1b[0m')
                                print('-Name Cluster:',cluster_name)
                                print('-Alert Title:', alert_title)
                                if nproblem == '{}':
                                        print('-Posible name problem: ', '-')
                                else:
                                        print('-Posible name problem: ', nproblem)
                                #print('-Detailed Messages: ', detailed_message)
                                print('-Affected entities: ', entity_type)
                                print('-classifications: ', classifications)
                                print('-'+entity_type+' name: ', entity_name)
                                print('-'+entity_type+' UUID: ', uuid)
                                print('-Posbile Cause:', causes)
                                print('-Posbile Action:', actions)
                                print('-Alert Type UUID:', alert_type_uuid)
                                print('-Acknowledged: ', acknowledged)
                                print('-Acknowledged by Username: ', acknowledged_by_username)
                                print('-resolved:', resolved)
                                print('-Creation alarm: ', created_time_stamp_in_usecs_datetime)
                                print('-Last time the alarm was repeated: ', last_occurrence_time_stamp_in_usecs_datetime)
                                print('-Impact Type: ', impact_types)
                                print('-Alarm Counter:',state_ok)
                                print('-Prism Element URL:',base_url)
                                print("-Detailed info: ",name_ent )
                                print('-----------------------------------------------------------------')
                                if status == 'y':
                                        if atype == 'CRITICAL'  :
                                                state_ok = state_ok + 1
                                        elif atype == 'WARNING' :
                                                state_ok = state_ok + 1
                                        else: #####NAGIOS CODE FOR UNKNOWN
                                                #print(atype)
                                                print("UNKNOWN ALARM NUTANIX CLUSTER " + ip)
                                                sys.exit(3)
                                elif status == 'n':
                                        if atype == 'CRITICAL' and resolved == False :
                                                state_ok = state_ok + 1
                                        elif atype == 'WARNING' and resolved == False:
                                                state_ok = state_ok + 1
                                        else: #####NAGIOS CODE FOR UNKNOWN
                                                print(atype)
                                                print(resolved)
                                                print("UNKNOWN ALARM NUTANIX CLUSTER " + ip)
                                                sys.exit(3)
                                else:
                                        print('Insert a valid --status option (y/n)')
                #####NAGIOS CODE FOR CRITICAL AND WARNING
                if state_ok == 0 and atype =='CRITICAL':
                        info = "NO CRITICAL ALARM ON NUTANIX CLUSTER " + ip
                        print(info)
                        sys.exit(0)
                elif not state_ok == 0 and atype =='CRITICAL':
                        info = "YOU HAVE " + str(state_ok) + " CRITICAL ON NUTANIX CLUSTER " + ip
                        print(info)
                        sys.exit(2)
                if state_ok == 0 and atype == 'WARNING':
                        info = "NO WARNING ALARM ON NUTANIX CLUSTER " + ip
                        print(info)
                        sys.exit(0)
                elif not state_ok == 0 and atype =='WARNING':
                        info = "YOU HAVE " + str(state_ok) + " WARNING ON NUTANIX CLUSTER " + ip
                        print(info)
                        sys.exit(1)
        except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    alerts(ip,username,password,atype,status)
#    parser = argparse.ArgumentParser(description='EXAMPLE: python NUTANIX_CHECK_API_v1.4.py --ip 10.26.1.2 --username admin --password Pass1010., --atype CRITICAL.')
#
#    parser.add_argument('-v', '--version', action='version', version='%(prog)s v' + VERSION)
#    parser.add_argument('--ip', required=True,
#                        help='Nutanix REST API URL. Required. Ex: https://10.10.10.100:9440')
#    parser.add_argument('--username', required=True,
#                        help='Nutanix REST API Username. Required.')
#    parser.add_argument('--password',required=True,
#                        help='Nutanix REST API Password. Optional, is asked if it is omitted.')
#    parser.add_argument('--atype', required=True,
#                        help='Nutanix type of alarm , CRITICAL OR WARNING.')
#    parser.add_argument('--resolved', required=True,
#                        help='List resolved alarms or not (y/n).')
#    args = parser.parse_args()
#    password = args.password if args.password else getpass.getpass()
#
#    alerts(args.ip, args.username, password, args.atype, args.resolved)
