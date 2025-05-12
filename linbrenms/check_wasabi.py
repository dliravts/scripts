#!/usr/bin/env python3

import datetime
from email.message import EmailMessage

import requests
import smtplib
import sys

warning = 0.8
critical = 0.9
wasabi_totals = 357840279024800

def calculate_size(size, _size_table):
    """
    This function dynamically calculates the right base unit symbol for size of the object.
    :param size: integer to be dynamically calculated.
    :param _size_table: dictionary of size in Bytes. Created in wasabi-automation.
    :return: string of converted size.
    """
    count = 0
    while size // 1024 > 0:
        size = size / 1024
        count += 1
    return str(round(size, 2)) + ' ' + _size_table[count]


if __name__ == '__main__':
    # Keys for accessing billing data.
    wasabi_access_key = ''
    wasabi_secret_key = ''
    gmail_sender = 'sender@xyz.com'
    receiver = 'receiver@xyz.com'
    # If you have 2FA then please enable application passwords for separate instance login.
    gmail_password = 'sender-password'

    # Generate a table for SI units symbol table.
    size_table = {0: 'Bs', 1: 'KBs', 2: 'MBs', 3: 'GBs', 4: 'TBs', 5: 'PBs', 6: 'EBs'}

    # request for the billing api
    try:
        response = requests.get("https://billing.wasabisys.com/utilization/bucket/",
                                headers={"Authorization": f'{wasabi_access_key}:{wasabi_secret_key}'})
    except Exception as e:
        raise e

    # get json data for billing
    json_data = response.json()

    # initialize a dict for adding up numbers
    result = {'PaddedStorageSizeBytes': 0,
              'NumBillableObjects': 0,
              'DeletedStorageSizeBytes': 0,
              'NumBillableDeletedObjects': 0
              }

    # get the initial time and check date only for this day.
    initial_time = datetime.datetime.strptime(json_data[0]['StartTime'], '%Y-%m-%dT%H:%M:%SZ')

    # for each bucket add the the data to the dict
    for bucket in json_data:
        # check the time from the last day.
        time = datetime.datetime.strptime(bucket['StartTime'], '%Y-%m-%dT%H:%M:%SZ')
        # summing logic.
        if time.date() == initial_time.date():
            result['PaddedStorageSizeBytes'] += bucket['PaddedStorageSizeBytes']
            result['DeletedStorageSizeBytes'] += bucket['DeletedStorageSizeBytes']
            result['NumBillableObjects'] += bucket['NumBillableObjects']
            result['NumBillableDeletedObjects'] += bucket['NumBillableDeletedObjects']

    body = f"Billing Summary for {initial_time.date()}" + "\n" \
           + 'Active storage: ' + calculate_size(result['PaddedStorageSizeBytes'], size_table) + "\n" \
           + 'Deleted storage: ' + calculate_size(result['DeletedStorageSizeBytes'], size_table) + "\n" \
           + 'Total Active objects: ' + str(result['NumBillableObjects']) + "\n" \
           + 'Total Deleted objects: ' + str(result['NumBillableDeletedObjects'])

    try:
       a = result['PaddedStorageSizeBytes'] + result['DeletedStorageSizeBytes']

       if a > wasabi_totals*warning:
        print('Warning: More than 80% of the wasabi is being used.')
        print('Total storage: ',calculate_size(wasabi_totals, size_table))
        print('Active storage: ',calculate_size(result['PaddedStorageSizeBytes'], size_table))
        print('Deleted storage: ',calculate_size(result['DeletedStorageSizeBytes'], size_table))
        print('Availabe storage: ',calculate_size(wasabi_totals- result['PaddedStorageSizeBytes']- result['DeletedStorageSizeBytes'], size_table))
        sys.exit(1)

       elif a > wasabi_totals*critical:
        print('Critical: More than 90% of the wasabi is being used.')
        print('Total storage: ',calculate_size(wasabi_totals, size_table))
        print('Active storage: ',calculate_size(result['PaddedStorageSizeBytes'], size_table))
        print('Deleted storage: ',calculate_size(result['DeletedStorageSizeBytes'], size_table))
        print('Availabe storage: ',calculate_size(wasabi_totals- result['PaddedStorageSizeBytes']- result['DeletedStorageSizeBytes'], size_table))
        sys.exit(2)

       else:
        print('Total storage: ',calculate_size(wasabi_totals, size_table))
        print('Active storage: ',calculate_size(result['PaddedStorageSizeBytes'], size_table))
        print('Deleted storage: ',calculate_size(result['DeletedStorageSizeBytes'], size_table))
        print('Availabe storage: ',calculate_size(wasabi_totals- result['PaddedStorageSizeBytes']- result['DeletedStorageSizeBytes'], size_table))
        sys.exit(0)
    except Exception as e:
        print(e)
