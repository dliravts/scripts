#!/usr/bin/env python3
import datetime
import requests
import sys

warning = 0.7
critical = 0.8

buckets = "none"
if("--buckets" in  sys.argv):
    buckets = sys.argv[sys.argv.index("--buckets") + 1]

list_buckets = buckets.split(",")


contratado = "none"
if("--contratado" in  sys.argv):
    contratado = int(sys.argv[sys.argv.index("--contratado") + 1])*1024*1024*1024*1024

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
    wasabi_access_key = 'Y5A1YRA82X76INRJR3Q4'
    wasabi_secret_key = '2smIXInCd1QiJ3GQDQiqAGNJzrhoSNTRbCPIw0v1'
    gmail_sender = 'sender@xyz.com'
    receiver = 'receiver@xyz.com'
    # If you have 2FA then please enable application passwords for separate instance login.
    gmail_password = 'sender-password'

    # Generate a table for SI units symbol table.
    size_table = {0: 'Bs', 1: 'KiBs', 2: 'MiBs', 3: 'GiBs', 4: 'TiBs', 5: 'PiBs', 6: 'EiBs'}

    # request for the billing api
    try:
        response = requests.get("https://billing.wasabisys.com/utilization/bucket/?withname=true",
                                headers={"Authorization": f'{wasabi_access_key}:{wasabi_secret_key}'})
    except Exception as e:
        raise e

    # get json data for billing
    json_data = response.json()

    # initialize a dict for adding up numbers

    # get the initial time and check date only for this day.
    initial_time = datetime.datetime.strptime(json_data[0]['StartTime'], '%Y-%m-%dT%H:%M:%SZ')

    def sizec(cbucket,json_data):
        result = {'PaddedStorageSizeBytes': 0,
                  'NumBillableObjects': 0,
                  'DeletedStorageSizeBytes': 0,
                  'NumBillableDeletedObjects': 0
                  }

        # for each bucket add the the data to the dict
        for bucket in json_data:
            if bucket['Bucket'] == cbucket:
                # check the time from the last day.
                time = datetime.datetime.strptime(bucket['StartTime'], '%Y-%m-%dT%H:%M:%SZ')
                # summing logic.
                if time.date() == initial_time.date():
                    result['PaddedStorageSizeBytes'] += bucket['PaddedStorageSizeBytes']
                    result['DeletedStorageSizeBytes'] += bucket['DeletedStorageSizeBytes']
                    result['NumBillableObjects'] += bucket['NumBillableObjects']
                    result['NumBillableDeletedObjects'] += bucket['NumBillableDeletedObjects']
                return result['PaddedStorageSizeBytes']

    try:
        total = 0
        for b in list_buckets:
            a = sizec(b,json_data)
            if a is None:
                pass
            else:
                print('Bucket name:', b)
                print('Active storage: ',calculate_size(a, size_table))
                print()
                total = a + total
        print('Total storage used by all buckets: ',calculate_size(total, size_table))
        print('Acquired space: ',calculate_size(contratado, size_table))

        if total > contratado*critical:
            print('Warning: More than 80% of the wasabi is being used.')
            sys.exit(1)

        else:
            sys.exit(0)
    except Exception as e:
        print(e)
