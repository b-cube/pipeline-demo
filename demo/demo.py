# -*- coding: utf-8 -*-

import flask
from flask import Flask
from flask import Response
from flask import request
app = Flask(__name__)

import luigi
from luigi import worker
import os
from bcube_demo_pipeline import MainWorkflow
from dlib.task_helpers import clear_directory
from dlib.call_solr import pull_from_solr

import sys
import StringIO


@app.route('/pipe')
def trigger_pipeline():
    '''
    run the pipeline
    '''
    capture_logs = bool(request.args.get('debug', 'False'))
    # Raw, Identify, Parse, Triple, Query
    output_task = request.args.get('task', 'Triple')

    doc_dir = 'bcube_demo/docs'

    # capture the main luigi output
    ste = sys.stderr
    sys.stderr = pipeline_output = StringIO.StringIO()
    std = sys.stdout
    sys.stdout = pipeline_debug = StringIO.StringIO()

    pull_from_solr(doc_dir)
    task = MainWorkflow(doc_dir=doc_dir, yaml_file='configs/bcube_demo.yaml')
    luigi.interface.setup_interface_logging()
    sch = luigi.scheduler.CentralPlannerScheduler()
    w = worker.Worker(scheduler=sch)
    w.add(task)
    w.run()

    # store and reset
    piped = pipeline_output.getvalue()
    sys.stderr = ste

    debugs = pipeline_debug.getvalue()
    sys.stdout = std

    if capture_logs:
        # fake the generator
        def generate():
            for pipe in piped.split('\n'):
                yield pipe + '\n'
            yield '\n\n####################\n\n'

            for debug in debugs.split('\n'):
                yield debug + '\n'

        return Response(generate(), mimetype='text/plain')
    else:
        return ''


@app.route('/reset')
def reset():
    '''
    reset the pipeline (delete the intermediate files)
    TODO: drop from parliament?!
    '''
    dirs = ['docs', 'raw', 'identified', 'parsed', 'triples']
    for d in dirs:
        clear_directory(os.path.join('bcube_demo', d))
    return ''

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)
