from config import api_key
import random
import requests
import time

def randcommit():
    return hex(random.randint(1000000000, 10000000000))[2:]

def jitter():
    return 1.0 / random.randint(75, 250)

tasks = ['task.{:d}'.format(i) for i in xrange(10)]

for i in xrange(10):
    commit = randcommit()
    tscommit = int(time.time() * 1000)
    for task in tasks:
        data = {
            'key': api_key,
            'host': 'darwin-x86_64-1',
            'task': task,

            'tags': ['group1'],
            'ts': int(time.time() * 1000),
            'perf': {
                'time': 100 * jitter(),
                'count': int(100000 * jitter()),
            },
            'commit': commit,
            'tscommit': tscommit,
        }
        print data
        requests.post('http://localhost:4999/perf/example/publish', json=data)
