from bson import binary
from collections import defaultdict
from datetime import datetime, timedelta
from flask import Flask, abort, render_template, request, send_file
from flask_pymongo import PyMongo
import io
import math
import pymongo
import re
import time

from config import db_config, api_key
from plot import plot

PAGE_SIZE = 50

app = Flask('perf')
app.config.update(db_config)
mongo = PyMongo(app)

@app.before_first_request
def add_indices():
    db = mongo.db
    asc = pymongo.ASCENDING
    dsc = pymongo.DESCENDING
    db.projects.create_index('project')
    db.data.create_index('project')
    db.data.create_index([
        ('project', asc),
        ('host', asc),
        ('tags', asc),
    ])
    db.data.create_index([
        ('project', asc),
        ('host', asc),
        ('task', asc),
    ])
    db.cache.drop()
    db.cache.create_index([
        ('project', asc),
        ('host', asc),
    ])

@app.route('/perf/')
def perf_list():
    names = sorted({p['project'] for p in mongo.db.projects.find({}, {'project': 1, '_id': 0})})
    return render_template('list.html', names=names)

def getsize(size=1):
    w, h = 300, 225
    if size == '2':
        w, h = 1280, 600
    elif size == '3':
        w, h = 1920, 1080
    elif size == '4':
        w, h = 2560, 1440
    return w, h

def calc_page_size(size=1):
    if size == 1:
        return PAGE_SIZE * 4
    return max(PAGE_SIZE * (int(size) - 1), PAGE_SIZE)

def avg(l):
    return sum(l) / len(l)

@app.route('/perf/<project>/graph/<host>/<tag>/<counter>')
@app.route('/perf/<project>/graph/<host>/<tag>/<counter>/<size>')
def project_file(project, host, tag, counter, size='1'):
    page = int(request.args.get('page', 1))
    w, h = getsize(size)
    cache_key = {'project': project, 'host': host, 'tag': tag, 'counter': counter, 'width': w, 'height': h, 'page': page}
    cached = mongo.db.cache.find_one(cache_key)
    if cached and cached['file']['data']:
        # cache hit
        f = cached['file']
    else:
        # cache miss
        # grab commits for project, sort by date, and remove date
        pcommits = mongo.db.projects.find_one({'project': project}, {'commits': 1, '_id': 0})
        commits = (pcommits or {}).get('commits', {}).items()
        commits = [c[0] for c in sorted(commits, key=lambda x: x[1])]

        # paginate
        page_size = calc_page_size(int(size))
        commits = commits[-max(page, 1) * page_size:][:page_size]

        # query for matching data
        tasks = list(mongo.db.data.find(
            {'project': project, 'host': host, 'tags': tag, 'counters': counter},
            {'task': 1, 'data.{}'.format(counter): 1, '_id': 0},
        ))
        tasks = list(tasks)
        lines = defaultdict(list)
        for commit in commits:
            for task in tasks:
                # TODO: can we graph a gap in the data somehow? maybe with dots
                point = avg(task['data'][counter].get(commit, [0]))
                lines[task['task']].append(point)

        # remove (s) from counter titles and apply as y unit
        yunit = ''
        match = re.match(r'^(.*)\((.+)\)$', counter)
        if match:
            counter, yunit = match.groups()

        shortcommits = [c[:8] for c in commits]
        title = '{} - {} - {}'.format(host, tag, counter)
        image = plot(title=title, xlabel='', ylabel=counter, xtics=shortcommits, data=lines, yunit=yunit, width=w, height=h, bare=size == '1')
        f = {'mime': 'image/png', 'data': binary.Binary(image)}
        # TODO: if image is too big it might render successfully but fail to insert and throw a 500
        mongo.db.cache.update(cache_key, {'$set': {'file': f}}, upsert=True)
    return send_file(io.BytesIO(f['data']), mimetype=f['mime'])

@app.route('/perf/<project>/graph/<host>/<tag>/<counter>/view')
@app.route('/perf/<project>/graph/<host>/<tag>/<counter>/view/<size>')
def one_view(project, host, tag, counter, size='1'):
    w, h = getsize(size)
    graph = {'host': host, 'tag': tag, 'counter': counter}

    page = int(request.args.get('page', 1))
    data = mongo.db.projects.find_one({'project': project}, {'commits': 1})
    page_size = calc_page_size(int(size))
    pages = int(math.ceil(len(data['commits']) / page_size))

    ts = int(time.time())
    return render_template('view.html', project=project, graph=graph, size=size, width=w, height=h, ts=ts, page=page, pages=pages)

@app.route('/perf/<project>/')
@app.route('/perf/<project>/<size>')
def view(project, size='1'):
    w, h = getsize(size)
    data = mongo.db.data.find({'project': project}, {'host': 1, 'task': 1, 'tags': 1, 'counters': 1})
    graphs = set()
    # (host: darwin-x86_64-1, tag: coreutils-ubuntu14.4.4, counter: time_ms)
    for d in data:
        for tag in d['tags']:
            for counter in d['counters']:
                graphs.add((d['host'], tag, counter))

    # sort tuple and turn into a dict for easier template access
    graphs = [dict(zip(('host', 'tag', 'counter'), g)) for g in sorted(graphs)]
    ts = int(time.time() / 10)
    return render_template('project.html', project=project, graphs=graphs, size=size, width=w, height=h, ts=ts)

@app.route('/perf/<project>/publish', methods=['POST'])
def publish(project):
    json = request.get_json()
    if json is None:
        return abort(400)

    if json.get('key') != api_key:
        return abort(403)

    up = map(json.get, ('host', 'task', 'ts', 'tags', 'perf', 'commit', 'tscommit'))
    host, task, ts, tags, perf, commit, tscommit = up
    if not all((host, task, ts, perf, commit)):
        return abort(400)

    task = str(task)
    if ts is not None:
        ts = datetime.utcfromtimestamp(ts / 1000.0)
    tags = [str(s) for s in tags or []]
    perf = {str(k): float(v) for k, v in perf.items() or {}}
    commit = str(commit)
    if tscommit is not None:
        tscommit = datetime.utcfromtimestamp(tscommit / 1000.0)

    commit_sub = 'commits.{}'.format(commit)
    mongo.db.projects.update(
        {'project': project, 'commits': {'$nin': [commit]}},
        {'$set': {'project': project, commit_sub: tscommit},
         '$addToSet': {'tags': {'$each': tags}}},
        upsert=True)

    data_updates = {}
    counters = set()
    for counter, value in perf.items():
        for tag in tags:
            key = {'project': project, 'host': host, 'tag': tag, 'counter': counter}
            mongo.db.cache.remove(key)

        key = 'data.{}.{}'.format(counter, commit)
        data_updates[key] = value
        counters.add(counter)

    mongo.db.data.update(
        {'project': project, 'host': host, 'task': task},
        {'$push': data_updates,
         '$addToSet': {'tags': {'$each': tags},
                       'counters': {'$each': list(counters)}}},
        upsert=True)
    return ''

if __name__ == '__main__':
    app.run(port=4999, debug=True)
